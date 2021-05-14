import os

from common.utils import path_extend, Singleton
from common.repository import SQLiteRepository

# Set CLAP_PATH to ~/.clap if it is not set as an environment variable
if 'CLAP_PATH' not in os.environ:
    os.environ['CLAP_PATH'] = path_extend('~', '.clap')


class Config(metaclass=Singleton):
    """Default CLAP configuration
    """
    def __init__(self):
        self.verbosity: int = 0
        self.app_name: str = 'CLAP'
        self.repository_type = SQLiteRepository
        self.repository_type_name = 'sqlite'
        self.clap_path = path_extend('$CLAP_PATH')
        self.configs_path: str = path_extend('$CLAP_PATH', 'configs')
        self.private_path: str = path_extend('$CLAP_PATH', 'private')
        self.storage_path: str = path_extend('$CLAP_PATH', 'storage')
