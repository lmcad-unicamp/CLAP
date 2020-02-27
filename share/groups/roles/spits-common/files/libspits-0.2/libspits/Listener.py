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

import logging
import os
import socket
import sys
import threading
import traceback

from libspits import ClientEndpoint
from libspits import config


class Listener(object):
    """Threaded TCP/UDS listener with callback"""

    def __init__(self, mode, address, port, callback, user_args):
        """ Threaded TCP/UDS listener with callback

        :param mode: Operation mode ('tcp' or 'udp')
        :type mode: str
        :param address: IP Address to listen
        :type address: str
        :param port: Port to listen
        :type port: int
        :param callback: Callback method to be called when a connection occurs
        :type callback: method
        :param user_args: User arguments (as tuple) to be passed to callback method when a connection occurs.
            Note: the tuple must contain the same number of arguments needed by the callback method
        :type user_args: tuple
        """
        self.mode = mode
        self.addr = address
        self.port = port
        self.callback = callback
        self.user_args = user_args
        self.thread = None
        self.socket = None
        self.running = False

    def GetConnectableAddr(self):
        """ Get the connectabele address from this listener

        :return: String containing the hostname and port (format 'host:port')
        :rtype: str
        :raises Exception: if a invalid mode is provided
        """
        if self.mode == config.mode_tcp:
            return '{}:{}'.format(socket.gethostname(), self.port)
        elif self.mode == config.mode_uds:
            return '{}:{}'.format(socket.gethostname(), self.addr)
        else:
            raise Exception("Invalid listener mode '{}' provided!".format(self.mode))

    def listener(self):
        """ Server network listener. A callback thread is created for each accepted connection, passing self.user_args
            The listener thread runs indefinitely until self.running is False (checked every second)
        """

        if self.mode == config.mode_tcp:
            logging.info('Listening to network at {}:{}...'.format(self.addr, self.port))
        elif self.mode == config.mode_uds:
            logging.info('Listening to file at {}...'.format(self.addr))
        self.running = True

        while self.running:
            self.socket.settimeout(1)

            try:
                conn, addr = self.socket.accept()
            except:
                continue
            try:
                # Assign the address from the connection
                if self.mode == config.mode_tcp:
                    # TCP
                    addr, port = addr
                elif self.mode == config.mode_uds:
                    # UDS
                    addr = 'uds'
                    port = 0

                # Create the endpoint and send to a thread to
                # process the request
                endpoint = ClientEndpoint(addr, port, conn)
                threading.Thread(target=self.callback, name='NetworkListerner',
                                 args=((endpoint, addr, port) + self.user_args)).start()
            except:
                logging.debug(sys.exc_info())
                logging.debug(traceback.format_exc())

        logging.debug("Stopping Network Listener at {}:{}...".format(self.addr, self.port))

    def Start(self):
        """ Create the socket server and starts the network listeners threads

        :return:
        :rtype:
        """
        if self.socket:
            return

        if self.mode == config.mode_tcp:
            # Create a TCP socket
            socktype = socket.AF_INET
            sockaddr = (self.addr, self.port)

        elif self.mode == config.mode_uds:
            # Remove an old socket
            try:
                os.unlink(self.addr)
            except:
                pass

            # Create an Unix Data Socket instead of a
            # normal TCP socket
            try:
                socktype = socket.AF_UNIX
                sockaddr = self.addr
            except AttributeError:
                raise Exception('The system does not support Unix Domain Sockets!')

        else:
            raise Exception('Invalid listener mode {} provided!'.format(self.mode))

        try:
            self.socket = socket.socket(socktype, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        except socket.error:
            raise Exception('Failed to create listener socket!')

        try:
            self.socket.bind(sockaddr)
            self.socket.listen(1)
        except socket.error:
            raise Exception('Failed to bind listener socket!')

        # If any port is selected, get the actual port assigned by the system
        if self.mode == config.mode_tcp and self.port == 0:
            addr, port = self.socket.getsockname()
            self.port = port

        self.thread = threading.Thread(target=self.listener, name='NetworkListener')
        self.thread.start()

    def Stop(self):
        """ Stops the socket server
        """
        self.running = False

        if self.socket:
            self.socket.close()
            self.socket = None
            if self.mode == config.mode_uds:
                # Remove the socket file if it is an UDS
                try:
                    os.unlink(self.addr)
                except:
                    pass

    def Join(self):
        """ Join in the server's threads
        """
        if self.thread:
            self.thread.join()
