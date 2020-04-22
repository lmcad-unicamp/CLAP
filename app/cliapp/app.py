import logging
import time
import traceback
import sys
import argparse
import inspect

from typing import List

from app.cliapp.commands import print_all_help, get_commands_parser
from clap.common.config import Defaults
from clap.common.module import AbstractParser
from clap.common.utils import log, setup_log
from clap.common.factory import PlatformFactory


def main(arguments: List[str]):
    #setup_log()
    
    parser, commands_parser = get_commands_parser()
    module_iface = PlatformFactory.get_module_interface()

    for mod_name, module in module_iface.get_modules().items():
        parsers = [ obj for name, obj in inspect.getmembers(module, 
                    predicate=lambda mod: inspect.isclass(mod) and issubclass(mod, AbstractParser))
                    if name != 'AbstractParser']
                    
        for p_class in parsers:
            try:
                p_obj = p_class()
                commands_com_parser = commands_parser.add_parser(p_obj.get_name(), help=p_obj.get_help())
                commands_subcom_parser = commands_com_parser.add_subparsers(title='commands', dest='subcommand')
                p_obj.add_parser(commands_subcom_parser)
            except Exception as e:
                log.error(e)

    try:
        args = parser.parse_args(arguments)
        Defaults.log_level = setup_log(Defaults.app_name, args.verbose)

        # Set Defaults parameters....

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
  (driver) elasticluster storage = {}
  verbosity level = {}
{}
""".format(
        time.ctime(), '-' * 80, args.driver, args.platform_db, args.repo_type, Defaults.private_path,
        Defaults.storage_path, Defaults.configs_path, Defaults.groups_path, Defaults.modules_path,
        Defaults.elasticluster_storage_path, args.verbose, '-' * 80))

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
        if args.verbose >= 2:
            traceback.print_exc()

        log.error("{}: {}".format(e.__class__.__name__, e))
        # log.error("Error executing `{} {}`".format(sys.argv[0], ' '.join(arguments)))
        return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
