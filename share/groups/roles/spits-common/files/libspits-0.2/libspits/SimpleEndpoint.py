#!/usr/bin/env python

# The MIT License (MIT)
#
# Copyright (c) 2015 Caian Benedicto <caian@ggaunicamp.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to
# deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.

from .Endpoint import Endpoint
from libspits import messaging

import socket, logging

class SimpleEndpoint(Endpoint):
    """Simple message exchange class"""

    def __init__(self, address, port):
        self.address = address
        self.port = port
        self.socket = None

    def Open(self, timeout):
        if self.socket:
            return

        if self.port <= 0:
            # Create an Unix Data Socket instead of a
            # normal TCP socket
            try:
                socktype = socket.AF_UNIX
            except AttributeError:
                logging.error('The system does not support ' +
                    'Unix Domain Sockets')
                raise
            sockaddr = self.address

        else:
            # Create a TCP socket
            socktype = socket.AF_INET
            sockaddr = (self.address, self.port)
            # Validate address
            try:
                socket.gethostbyname_ex(self.address)
            except:
                logging.error('Could not resolve address for host ' +
                    self.address)
                raise

        self.socket = socket.socket(socktype, socket.SOCK_STREAM)
        self.socket.settimeout(timeout)
        self.socket.connect(sockaddr)

    def Read(self, size, timeout):
        return messaging.recv(self.socket, size, timeout)

    def Write(self, data):
        self.socket.sendall(data)

    def Close(self):
        if self.socket != None:
            self.socket.close()
            self.socket = None
