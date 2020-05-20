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
        paramount_subcom_parser = commands_parser.add_parser('start', help='Start cluster given a cluster configuration file')
        paramount_subcom_parser.add_argument('app_name', action='store', 
                help='Symbolic name of the application to run')
        paramount_subcom_parser.add_argument('node_type', action='store', 
                help='Type of the node to be created')
        paramount_subcom_parser.add_argument('sizes', action='store', nargs='+',
                help='List with the number of nodes to be executed...')
        paramount_subcom_parser.set_defaults(func=self.start_paramount_cluster)

    def start_paramount_cluster(self, namespace: argparse.Namespace):
        print(namespace)
        app_name = namespace.app_name
        node_type = namespace.node_type
        try:
            sizes = [int(value) for value in namespace.sizes]
        except ValueError as e:
            log.error(e)
            log.error("The size must be a list o integers")
            return 1
        paramount = create_paramount_cluster(app_name, node_type, sizes)
        

        return 0