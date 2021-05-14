import os
import shutil
import tempfile
import time
import logging
import random
from abc import abstractmethod
from collections import defaultdict
from typing import List
from contextlib import contextmanager

import names
import yaml
import coloredlogs

APP_NAME = 'clap'


class CLAPFilter(logging.Filter):
    def filter(self, record):
        global APP_NAME
        return record.module.startswith(f'{APP_NAME}')


class Singleton(type):
    """Creates a single instance class
    """
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        # else:
        #    cls._instances[cls].__init__(*args, **kwargs)
        return cls._instances[cls]


@contextmanager
def tmpdir(suffix=None, prefix='clap.', dir: str = None, remove: bool = True):
    dd = tempfile.mkdtemp(suffix=suffix, prefix=prefix, dir=dir)
    try:
        yield dd
    finally:
        if remove:
            shutil.rmtree(dd)


def path_extend(*args) -> str:
    return os.path.expandvars(os.path.expanduser(os.path.join(*args)))


def yaml_load(filename: str) -> dict:
    with open(filename, 'r') as file:
        return yaml.load(file, Loader=yaml.FullLoader)


def float_time_to_string(timespec: float):
    return time.strftime("%d-%m-%y %H:%M:%S", time.localtime(timespec))


def setup_log(name: str = 'clap', verbosity_level: int = 0, filename: str = None):
    # 0 -> ERROR, 1->WARNING, 2->DEBUG
    global APP_NAME
    APP_NAME = name

    formatter = '[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s'
    if verbosity_level <= 0:
        log_level = logging.WARNING
    elif verbosity_level == 1:
        log_level = logging.INFO
    else:
        log_level = logging.DEBUG

    coloredlogs.install(level=log_level)

    if filename:
        logging.basicConfig(filename=filename, filemode='a', level=log_level, format=formatter)
    else:
        logging.basicConfig(level=log_level, format=formatter)

    if verbosity_level < 3:
        for key in list(logging.Logger.manager.loggerDict.keys()) + ['sqlitedict.SqliteMultithread', 'paramiko.transport']:
            if not key.startswith(f'{APP_NAME}'):
                logging.getLogger(key).disabled = True


def get_random_name(in_use_names: List[str] = None, retries: int = 10) -> str:
    new_name = ''
    in_use_names = in_use_names or []
    for i in range(retries):
        new_name = names.get_full_name()
        if new_name not in in_use_names:
            return new_name

    for i in range(retries):
        new_new_name = f'{new_name} #{str(random.random())[10:]}'
        if new_new_name not in in_use_names:
            return new_new_name

    return ''


def default_dict_to_dict(d):
    if isinstance(d, defaultdict):
        d = {k: default_dict_to_dict(v) for k, v in d.items()}
    return d


def get_logger(name):
    return logging.getLogger(f'{APP_NAME}.{name}')


class Dictable:
    @staticmethod
    @abstractmethod
    def from_dict(d: dict):
        raise NotImplementedError()

    @abstractmethod
    def to_dict(self):
        pass

