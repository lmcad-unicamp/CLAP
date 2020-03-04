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

from .SocketClosed import SocketClosed
from .MessagingError import MessagingError

import select, socket


# Messaging codes

msg_send_heart = 0x0200
msg_send_task  = 0x0201
msg_send_more  = 0x0202
msg_send_full  = 0x0203
msg_send_rjct  = 0x0204

msg_read_result = 0x0101
msg_read_empty = 0x0000
msg_terminate = 0xFFFF

msg_cd_query_metrics_list = 0x401
msg_cd_query_metrics_last_values = 0x402
msg_cd_query_metrics_history = 0x403
msg_cd_nodes_append = 0x404
msg_cd_nodes_list = 0x405
msg_cd_nodes_remove = 0x406

# Signal the spitz system through the upper 32
# bits of the result variable that an error
# occurred with the function call itself
res_module_error = 0xFFFFFFFF00000000
res_module_noans = 0xFFFFFFFE00000000
res_module_ctxer = 0xFFFFFFFD00000000

# Definition of the recv method for sockets, considering
# a definite size and timeout
def recv(conn, size, timeout):
    r = None
    left = size
    while left > 0:
        ready = select.select([conn], [], [], timeout)
        if not ready[0]:
            raise socket.timeout()
        d = conn.recv(left)
        if len(d) == 0:
            raise SocketClosed()
        r = r + d if r else d
        left = size - len(r)
    return r
