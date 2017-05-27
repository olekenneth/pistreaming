#!/usr/bin/env python

import sys
import io
import os
import shutil
from subprocess import Popen, PIPE
from string import Template
from struct import Struct
from threading import Thread
from time import sleep, time
from http.server import HTTPServer, BaseHTTPRequestHandler
from wsgiref.simple_server import make_server
from fractions import Fraction
import RPi.GPIO as GPIO
import datetime as dt

import picamera
from PIL import Image

def in_between(now, start, end):
    if start <= end:
        return start <= now < end
    else: # over midnight e.g., 23:30-04:15
        return start <= now or now < end

###########################################
# CONFIGURATION # VALUES IN NIGHTMODE
if in_between(dt.datetime.now().time(), dt.time(4), dt.time(17)):
    TIME = 'Day'
    FRAMERATE = 24
    SHUTTERSPEED = 20000
    ISO = 100
else:
    TIME = 'Night'
    FRAMERATE = 5
    SHUTTERSPEED = 2000000
    ISO = 800

WIDTH = 1280
HEIGHT = 960
HTTP_PORT = 8082
WS_PORT = 8084

GPIO_PIN=21
###########################################


class StreamingHttpHandler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        if self.path == '/':
            self.send_response(301)
            self.send_header('Location', '/cam.jpg')
            self.end_headers()
            return
        elif self.path == '/cam.mjpg':
            self.send_response(200)
            self.send_header('Content-type','multipart/x-mixed-replace; boundary=--jpgboundary')
            self.end_headers()
            try:
                ok = 1
                while ok < 30:
                    stream = self.server.update_jpg_content()
                    self.wfile.write("--jpgboundary\n".encode('UTF-8'))
                    self.send_header('Content-type','image/jpeg')
                    self.send_header('Content-length', len(stream.getvalue()))
                    self.end_headers()
                    self.wfile.write(stream.getvalue())
                    sleep(2)
                    ok = ok + 1
                return
            except:
                print('Closing mjpeg')
                return
            return
        elif self.path == '/cam.jpg':
            stream = self.server.update_jpg_content()
            content_type = 'image/jpeg'
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.end_headers()
            self.wfile.write(stream.getvalue())
            return
        else:
            self.send_error(404, 'File not found')
            return
        content = content.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', len(content))
        self.send_header('Last-Modified', self.date_time_string(time()))
        self.end_headers()
        if self.command == 'GET':
            self.wfile.write(content)


class StreamingHttpServer(HTTPServer):
    def __init__(self, stream):
        self.stream = stream
        super(StreamingHttpServer, self).__init__(
                ('', HTTP_PORT), StreamingHttpHandler)
        with io.open('index.html', 'r') as f:
            self.index_template = f.read()
        with io.open('jsmpg.js', 'r') as f:
            self.jsmpg_content = f.read()

    def update_jpg_content(self):
        return self.stream;

def main():
    print('Setting up GPIO ' + str(GPIO_PIN) + ' IR LED')
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(GPIO_PIN, GPIO.OUT)    
    print('Initializing camera')
    with picamera.PiCamera() as camera:
        camera.resolution = (WIDTH, HEIGHT)
        camera.framerate = FRAMERATE
        camera.shutter_speed = SHUTTERSPEED
        camera.iso = ISO
        # camera.exposure_mode = 'off'
        camera.led = False
        #camera.vflip = True
        #camera.hflip = True
        # camera.annotate_background = picamera.Color('black')
        sleep(1) # camera warm-up time
        print('Initializing HTTP server on port %d' % HTTP_PORT)
        stream = io.BytesIO()
        http_server = StreamingHttpServer(stream)
        http_thread = Thread(target=http_server.serve_forever)
        try:
            print('Starting HTTP server thread')
            http_thread.start()
            while True:
                tempStream = io.BytesIO()
                # print('Capture from camera' + dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                GPIO.output(GPIO_PIN, 1)
                sleep(0.01)
                tempStream.seek(0)
                tempStream.truncate()
                camera.annotate_text = dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' ' + TIME
                camera.capture(tempStream, 'jpeg')
                stream.seek(0)
                stream.truncate()
                stream.write(tempStream.getvalue())
                GPIO.output(GPIO_PIN, 0)
                sleep(2)
        except KeyboardInterrupt:
            pass
        finally:
            print('Shutting down HTTP server')
            http_server.shutdown()
            print('Waiting for HTTP server thread to finish')
            http_thread.join()


if __name__ == '__main__':
    main()
