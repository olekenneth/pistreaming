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

import picamera
from PIL import Image

###########################################
# CONFIGURATION
WIDTH = 1280
HEIGHT = 960
FRAMERATE = 24
HTTP_PORT = 8082
WS_PORT = 8084
COLOR = u'#444'
BGCOLOR = u'#000'
JSMPEG_MAGIC = b'jsmp'
JSMPEG_HEADER = Struct('>4sHH')
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
                while True:
                    sleep(0.1)
                    stream = self.server.update_jpg_content()
                    self.wfile.write("--jpgboundary\n".encode('UTF-8'))
                    self.send_header('Content-type','image/jpeg')
                    self.send_header('Content-length', len(stream.getvalue()))
                    self.end_headers()
                    self.wfile.write(stream.getvalue())
                    stream.seek(0)
                    stream.truncate()
                    sleep(0.5)
            except:
                pass
            return
        elif self.path == '/cam.jpg':
            stream = self.server.update_jpg_content()
            content_type = 'image/jpeg'
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.end_headers()
            self.wfile.write(stream.getvalue())
            stream.truncate()
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
    def __init__(self, camera):
        self.camera = camera
        super(StreamingHttpServer, self).__init__(
                ('', HTTP_PORT), StreamingHttpHandler)
        with io.open('index.html', 'r') as f:
            self.index_template = f.read()
        with io.open('jsmpg.js', 'r') as f:
            self.jsmpg_content = f.read()

    def update_jpg_content(self):
        stream = io.BytesIO()
        self.camera.capture(stream, 'jpeg')
        return stream

def main():
    print('Initializing camera')
    with picamera.PiCamera() as camera:
        camera.resolution = (WIDTH, HEIGHT)
        camera.framerate = FRAMERATE
        camera.led = False
        #camera.vflip = True
        sleep(1) # camera warm-up time
        print('Initializing HTTP server on port %d' % HTTP_PORT)
        http_server = StreamingHttpServer(camera)
        http_thread = Thread(target=http_server.serve_forever)
        try:
            print('Starting HTTP server thread')
            http_thread.start()
            while True:
                sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            print('Shutting down HTTP server')
            http_server.shutdown()
            print('Waiting for HTTP server thread to finish')
            http_thread.join()


if __name__ == '__main__':
    main()
