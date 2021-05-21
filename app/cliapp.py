import traceback
import sys

import click

from .module import ModuleInterface
from common.config import Config
from common.utils import setup_log, get_logger

logger = get_logger(__name__)
defaults = Config()


@click.group()
@click.option('-v', '--verbosity', default=0, help='Increase the verbosity level', show_default=True, count=True)
@click.option('-c', '--configs', default=defaults.configs_path, help='Configuration Path', show_default=True)
@click.option('-s', '--storage', default=defaults.storage_path, help='Storage Path', show_default=True)
@click.option('-p', '--private', default=defaults.private_path, help='Private Path', show_default=True)
def entry_point(verbosity, configs, private, storage):
    defaults.verbosity = verbosity
    defaults.configs_path = configs
    defaults.private_path = private
    defaults.storage_path = storage
    setup_log(verbosity_level=verbosity)


def main(args):
    module_interface = ModuleInterface()
    for module in module_interface.find_modules():
        entry_point.add_command(module)
    try:
        ret = entry_point()
        sys.exit(ret)
    except Exception as e:
        traceback.print_exc()
        logger.error(f"{e.__class__.__name__}: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main(sys.argv)

