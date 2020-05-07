import hashlib
import logging
import os.path
import yaml
import tempfile
import shutil
import time
from contextlib import contextmanager
from collections.abc import MutableMapping

log = logging.getLogger()

@contextmanager
def tmpdir(suffix=None, prefix='clap.', dir=None):
    dd = tempfile.mkdtemp(suffix=suffix, prefix=prefix, dir=dir)
    try:
        yield dd
    finally:
        shutil.rmtree(dd)


def setup_log(log_name: str = None, verbosity_level: int = 0, filename: str = ''):
    global log
    # 0 -> ERROR, 1->WARNING, 2->DEBUG
    formatter = '[%(asctime)s] [%(levelname)s] %(threadName)s: %(message)s'
    log_level = 0
    if verbosity_level == 0:
        log_level = logging.ERROR
    elif verbosity_level == 1:
        log_level = logging.INFO
    elif verbosity_level >= 2:
        log_level = logging.DEBUG
    else:
        log_level = logging.ERROR

    if filename:
        logging.basicConfig(filename=filename, filemode='a', level=verbosity_level, format=formatter)
    else:
        logging.basicConfig(level=log_level, format=formatter)

    log = logging.getLogger(log_name)
    
    return log_level
    

class Struct(MutableMapping, object):
    def __init__(self, initializer=None, **kwargs):
        if initializer is not None:
            try:
                # initializer is `dict`-like?
                for name, value in initializer.items():
                    self[name] = value
            except AttributeError:
                # initializer is a sequence of (name,value) pairs?
                for name, value in initializer:
                    self[name] = value
        for name, value in kwargs.items():
            self[name] = value

    def copy(self):
        """Return a (shallow) copy of this `Struct` instance."""
        return Struct(self)

    def __delitem__(self, name):
        del self.__dict__[name]

    def __getitem__(self, name):
        return self.__dict__[name]

    def __setitem__(self, name, val):
        self.__dict__[name] = val

    def __iter__(self):
        return iter(self.__dict__)

    def __len__(self):
        return len(self.__dict__)

    def keys(self):
        return list(self.__dict__.keys())


def path_extend(*args) -> str:
    return os.path.expandvars(os.path.expanduser(os.path.join(*args)))


def get_file_checksum(file_path: str) -> str:
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def yaml_load(filename: str) -> dict:
    with open(filename, 'r') as file:
        return yaml.load(file, Loader=yaml.FullLoader)


def float_time_to_string(timespec: float):
    return time.strftime("%d-%m-%y %H:%M:%S", time.localtime(timespec))