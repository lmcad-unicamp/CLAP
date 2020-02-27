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

import threading, sys, logging

try:
    import Queue as queue # Python 2
except:
    import queue # Python 3

class TaskPool(object):
    '''
    This class implements a pool of workers to process tasks
    '''

    def __init__(self, max_threads, overfill, initializer, worker, user_args):
        '''
        Create and initialize spits workers (threads) to process incoming tasks in the Pool

        :param max_threads: Number of threads to create
        :type max_threads: int
        :param overfill: Extra space in the task queue
        :type overfill: int
        :param initializer: Initializer routine for the worker
        :type initializer: method(**kwargs)
        :param worker: Routine used to execute the task using the job module
        :type worker: method(**kwargs)
        :param user_args: User parameters to initializer and worker methods
        :type user_args: tuple
        '''
        self.max_threads = max_threads
        self.user_args = user_args
        self.initializer = initializer
        self.worker = worker
        self.tasks = queue.Queue(maxsize=max_threads + overfill)
        self.threads = [threading.Thread(target=self.runner, name='Worker-{i}'.format(i=i)) for
            i in range(max_threads)]

    def start(self):
        for t in self.threads:
            t.start()

    def runner(self):
        state = None
        try:
            # Initialize the module worker
            state = self.initializer(*self.user_args)
        except:
            # TODO better exception handling
            pass
        while True:
            # Pick a task from the queue and execute it
            # TODO better tm kill
            taskid, jobid, task = self.tasks.get()
            try:
                self.worker(state, taskid, jobid, task, *self.user_args)
            except:
                logging.error('The worker crashed while processing ' +
                    'the task %d', taskid)

    def Put(self, taskid, jobid, task):
        try:
            self.tasks.put_nowait((taskid, jobid, task))
        except queue.Full:
            return False
        return True

    def Full(self):
        return self.tasks.full()

    def Empty(self):
        return self.tasks.empty()
