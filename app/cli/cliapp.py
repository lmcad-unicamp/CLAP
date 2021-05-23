import inspect
import os
import sys
import pkgutil
import traceback
from typing import List

import click

from clap.utils import get_logger, setup_log, Singleton, path_extend

if 'CLAP_PATH' not in os.environ:
    os.environ['CLAP_PATH'] = path_extend('~', '.clap')


class ArgumentError(Exception):
    pass


class Defaults(metaclass=Singleton):
    def __init__(self):
        self.verbosity: int = 0
        self.clap_path: str = path_extend(os.environ.get('CLAP_PATH'))
        self.configs_path: str = path_extend(
            os.environ.get('CLAP_PATH'), 'configs')
        self.private_path: str = path_extend(
            os.environ.get('CLAP_PATH'), 'private')
        self.storage_path: str = path_extend(
            os.environ.get('CLAP_PATH'), 'storage')


class clap_command(click.Group):
    def __init__(self, group):
        super().__init__()
        self.__dict__ = group.__dict__.copy()


logger = get_logger(__name__)
defaults = Defaults()


def find_commands(paths: List[str] = None) -> List[clap_command]:
    """

    :param paths:
    :return:
    """
    paths = paths or [os.path.join(os.path.dirname(__file__), 'modules')]
    modules = []
    for importer, package_name, _ in pkgutil.iter_modules(paths):
        if 'pycache' in package_name or \
                '.' in package_name or package_name.startswith('__'):
            continue
        try:
            mod = importer.find_module(package_name).load_module(package_name)
            modules += [obj for _, obj in inspect.getmembers(
                mod, predicate=lambda x: type(x) is clap_command)]
        except Exception as e:
            print(f'Error importing module with name `{package_name}`')
            raise e
    return modules


@click.group()
@click.option('-v', '--verbosity', default=0, help='Increase the verbosity level', show_default=True, count=True)
@click.option('-c', '--configs', default=defaults.configs_path,
              help='Configuration Path', show_default=True)
@click.option('-s', '--storage', default=defaults.storage_path,
              help='Storage Path', show_default=True)
@click.option('-p', '--private', default=defaults.private_path,
              help='Private Path', show_default=True)
def entry_point(verbosity, configs, private, storage):
    defaults.verbosity = verbosity
    defaults.configs_path = configs
    defaults.private_path = private
    defaults.storage_path = storage
    setup_log(verbosity_level=verbosity)


def main(args):
    for module in find_commands():
        entry_point.add_command(module)
    try:
        ret = entry_point()
        sys.exit(ret)
    except Exception as e:
        traceback.print_exc()
        logger.error(f"{e.__class__.__name__}: {e}")
        sys.exit(1)


if __name__ == '__main__':
    import sys
    main(sys.argv)
