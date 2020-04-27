import argparse

from pprint import pprint
from operator import attrgetter

from clap.common.config import Defaults
from clap.common.factory import PlatformFactory
from clap.common.utils import log

# TODO multi-node tags and instantiate with multiple tags
# TODO instantiate with multiple groups (in order)
# TODO More than one execute SSH and output
# TODO template commands (instantiate based on a template)
# TODO SPITS MODULE
# TODO ZABBIX MODULE


class SortingHelpFormatter(argparse.HelpFormatter):
    def add_arguments(self, actions):
        actions = sorted(actions, key=attrgetter('option_strings'))
        super(SortingHelpFormatter, self).add_arguments(actions)


def get_known_arguments_parser(add_help=False):
    parser = argparse.ArgumentParser(description='CLAP starts and manages applications on clouds',
                                     formatter_class=SortingHelpFormatter, add_help=add_help)
    parser.add_argument('--platform-db', '-p', action='store', default=Defaults.PLATFORM_REPOSITORY,
                        help='Platform database to be used (default: `{}`)'.format(Defaults.PLATFORM_REPOSITORY))
    parser.add_argument('--repo-type', '-r', action='store', default=Defaults.REPOSITORY_TYPE,
                        help='Default repository type (default: `{}`)'.format(Defaults.REPOSITORY_TYPE))
    parser.add_argument('--driver', '-d', action='store', default=Defaults.DRIVER_ID,
                        help='Cloud driver to manage instances (default: `{}`'.format(Defaults.DRIVER_ID))
    parser.add_argument('--verbose', '-v', action='count', default=0,
                        help='Increase the verbosity level. Multiple v inscrease more the verbosity. Maximum is 4')
    return parser

def get_argument_parser():
    parser = get_known_arguments_parser(add_help=True)
    parser.add_argument('--show-all-help', '-hh', help='Show help of all commands', action='store_true', default=False)
    commands_parser = parser.add_subparsers(title='modules', dest='command')
    return parser, commands_parser

def print_all_help(parser):
    print('\n ------------ Printing usage of: `{}` --------------'.format(parser.prog))
    parser.print_help()

    for a in parser._actions:
        if isinstance(a, argparse._SubParsersAction):
            for name, p in a._name_parser_map.items():
                print_all_help(p)