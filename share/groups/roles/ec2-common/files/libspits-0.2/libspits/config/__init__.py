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

def_heart_timeout = 30      # Default Cloud heartbeat timeout (in seconds)
def_connection_timeout = 30   # Default connection timeout (in seconds)
def_send_timeout = 30         # Default send message timeout (in seconds)
def_receive_timeout = 30      # Default receive message timeout (in seconds)
def_idle_timeout = 36000      # Default idle timeout (in seconds)

send_backoff = 1
recv_backoff = 1

def_spitz_cm_port = 7724
def_spitz_cd_port = 7725
def_spitz_jm_port = 7726
def_spitz_tm_port = 7727

mode_tcp = 'tcp'
mode_uds = 'uds'

announce_cat_nodes = 'cat'
announce_file = 'file'
