#!/usr/bin/env python

# The MIT License (MIT)
#
# Copyright (c) 2018 Caian Benedicto <caian@ggaunicamp.com>
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

import ctypes

class Blob(object):
    """Class encapsulating large data moving inside the runtime"""

    def __init__(self, data_size=0, data_pointer=None, copy=False):
        """Construct a new object given a pointer to the data and size.
           If no data pointer is provided then the memory is allocated
           internally."""

        if data_size < 0:
            raise Exception()

        self._data_size = data_size

        if copy and (data_pointer is None):
            raise Exception()

        will_allocate = (data_pointer is None) or copy

        if will_allocate and data_size > 0:
            # Allocate the data internally
            self._inner_data = (ctypes.c_byte * data_size)()
            self._data_pointer = ctypes.cast(self._inner_data,
                ctypes.c_void_p)
            if copy:
                # Copy data
                ctypes.memmove(self._data_pointer,
                    data_pointer, data_size)
        else:
            # Keep the input data
            self._inner_data = None
            self._data_pointer = data_pointer

    def get_pointer(self):
        """Get the pointer to the stored data."""
        return self._data_pointer

    def get_size(self):
        """Get the size in bytes of the stored data."""
        return self._data_size
