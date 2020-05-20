import argparse
import os
import yaml

from typing import List

from clap.common.module import AbstractParser
from clap.common.utils import log, path_extend, float_time_to_string
from .module import *
from .conf import ParamountClusterDefaults

class ClusterParser(AbstractParser):
    def add_parser(self, commands_parser: argparse._SubParsersAction):
        # cluster start commands 
        cluster_subcom_parser = commands_parser.add_parser('start', help='Start cluster given a cluster configuration file')
        cluster_subcom_parser.add_argument('cluster_name', action='store', 
                help='Name of the cluster to create')
        cluster_subcom_parser.add_argument('--file', '-f', action='store', 
                type=lambda path: __is_valid_file__(path),
                help='File of the cluster configuration template (this option replaces the --directory option')
        cluster_subcom_parser.add_argument('--directory', '-d', default=ClusterDefaults.CLUSTER_SEARCH_PATH, 
                type=lambda path: __is_valid_directory__(path),
                help='Directory to search for cluster templates (Default is: `{}`)'.format(ClusterDefaults.CLUSTER_SEARCH_PATH))
        cluster_subcom_parser.add_argument('--no-setup', action='store_true', default=False,
                help='Does not setup the cluster')
        cluster_subcom_parser.add_argument('--extra', nargs=argparse.REMAINDER, metavar='arg=val',
                help="Keyworded (format: x=y) Arguments to be passed to the actions")
        cluster_subcom_parser.set_defaults(func=self.command_start_cluster)