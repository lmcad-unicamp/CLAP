import logging
import time
import traceback
import sys
import argparse
import inspect

from typing import List

from app.cliapp.commands import get_known_arguments_parser, get_argument_parser, print_all_help
from clap.common.config import Defaults
from clap.common.module import AbstractParser
from clap.common.utils import log, setup_log, path_extend
from clap.common.factory import PlatformFactory


def main(arguments: List[str]):
    # Parse default parameters
    parser = get_known_arguments_parser()
    known_args = parser.parse_known_args(arguments)
    
    Defaults.DRIVER_ID = known_args[0].driver
    Defaults.PLATFORM_REPOSITORY = path_extend(known_args[0].platform_db)
    Defaults.REPOSITORY_TYPE = known_args[0].repo_type
    Defaults.verbosity = known_args[0].verbose if known_args[0].verbose < 3 else 3
    Defaults.log_level = setup_log(Defaults.app_name, Defaults.verbosity)

    # Parse all parameters
    parser, commands_parser = get_argument_parser()
    module_iface = PlatformFactory.get_module_interface()

    for mod_name, module_vals in module_iface.get_modules().items():
        parsers = [ obj for name, obj in inspect.getmembers(module_vals['module'], 
                    predicate=lambda mod: inspect.isclass(mod) and issubclass(mod, AbstractParser))
                    if name != 'AbstractParser']
                    
        for p_class in parsers:
            try:
                p_obj = p_class()
                commands_com_parser = commands_parser.add_parser(mod_name, help=module_vals['description'])
                commands_subcom_parser = commands_com_parser.add_subparsers(title='commands', dest='subcommand')
                p_obj.add_parser(commands_subcom_parser)
            except Exception as e:
                log.error(e)

    try:
        args = parser.parse_args(arguments)
    except Exception as err:
        log.error("Parsing command line arguments: {}".format(err))
        return 1

    log.debug("""CLAP start at: {}
{}
Using paths:
  in-use driver = {}
  platform repository file = {}
  repository type = {}
  private path = {}
  storage path = {}
  configs path = {}
  groups path = {}
  modules path = {}
  verbosity level = {}
  log_level = {}
{}
""".format(
        time.ctime(), '-' * 80, Defaults.DRIVER_ID, Defaults.PLATFORM_REPOSITORY, Defaults.REPOSITORY_TYPE, Defaults.private_path,
        Defaults.storage_path, Defaults.configs_path, Defaults.groups_path, Defaults.modules_path,
        Defaults.verbosity, Defaults.log_level, '-' * 80))

    if args.show_all_help is True:
        print_all_help(parser)
        return 0

    if not args.command:
        log.error("Command is required!")
        return 1

    try:
        func = args.func
    except Exception:
        print('Use `{} {} --help` for help about the command'.format(sys.argv[0], ' '.join(arguments)))
        return 1

    # Run function!
    try:
        return args.func(args)
    except Exception as e:
        if Defaults.verbosity > 1:
            traceback.print_exc()

        log.error("{}: {}".format(e.__class__.__name__, e))
        # log.error("Error executing `{} {}`".format(sys.argv[0], ' '.join(arguments)))
        return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
