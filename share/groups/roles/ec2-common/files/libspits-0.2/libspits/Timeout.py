import logging
import traceback
import inspect
from threading import Timer
from threading import Lock

def timeout(timeout, callback, *args, **kwargs):
    if timeout is None or timeout <= 0:
        return TimeoutNoop()
    else:
        return Timeout(timeout, callback, *args, **kwargs)

class TimeoutNoop(object):
    def reset(self):
        pass
    def cancel(self):
        pass

class Timeout(object):
    def __init__(self, timeout, callback, args=[], kwargs={}):
        self.timeout = timeout
        self.callback = callback
        self._args = args
        self._kwargs = kwargs
        self._timer = None
        self._lock = Lock()

    def _callback(self):
        if self.callback(*self._args, **self._kwargs):
            self.reset()

    def reset(self):
        _frame = inspect.currentframe()
        frame = _frame.f_back
        fname = frame.f_code.co_filename
        fnum = frame.f_lineno
        self._lock.acquire()
        self._cancel()
        self._timer = Timer(self.timeout, self._callback)
        self._timer.start()
        self._lock.release()

    def _cancel(self):
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    def cancel(self):
        self._lock.acquire()
        self._cancel()
        self._lock.release()
