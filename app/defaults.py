import os
from common.utils import Singleton, path_extend

if 'CLAP_PATH' not in os.environ:
    os.environ['CLAP_PATH'] = path_extend('~', '.clap')


class Defaults(metaclass=Singleton):
    def __init__(self):
        self.verbosity: int = 0
        self.configs_path: str = path_extend(os.environ.get('CLAP_PATH'), 'configs')
        self.private_path: str = path_extend(os.environ.get('CLAP_PATH'), 'private')
        self.storage_path: str = path_extend(os.environ.get('CLAP_PATH'), 'storage')
