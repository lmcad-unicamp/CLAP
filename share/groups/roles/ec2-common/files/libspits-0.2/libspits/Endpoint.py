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

import struct

class Endpoint(object):
    """Interface for Network endpoint to exchange messages"""

    def Open(self):
        raise NotImplementedError('Please specialize this class to make a custom endpoint')

    def Read(self, size, timeout):
        raise NotImplementedError('Please specialize this class to make a custom endpoint')

    def Write(self, data):
        raise NotImplementedError('Please specialize this class to make a custom endpoint')

    def ReadInt64(self, timeout):
        return struct.unpack('!q', self.Read(8, timeout))[0]

    def WriteInt64(self, value):
        self.Write(struct.pack('!q', value))

    def ReadString(self, timeout):
        sz = struct.unpack('!I', self.Read(4, timeout))[0]
        if sz > 0:
            data = struct.unpack(str(sz)+'s', self.Read(sz, timeout))[0]
            return data.decode('utf8')
        else:
            return ''

    def WriteString(self, value):
        s = value.encode('utf8')
        l = len(s)
        self.Write(struct.pack('!I', l))
        if len(s) > 0:
            self.Write(struct.pack(str(l)+'s', s))

    def Close(self):
        raise NotImplementedError('Please specialize this class to make a custom endpoint')
