import argparse
from typing import List

from clap.common.module import AbstractParser
from clap.common.utils import log, path_extend, float_time_to_string
from .module import *
from .conf import ParamountClusterDefaults



class MpiParamountParser(AbstractParser):
    def add_parser(self, commands_parser: argparse._SubParsersAction):
        # cluster start commands 
        # start
        paramount_subcom_parser = commands_parser.add_parser('cluster-from-nodes', help='Start a paramount cluster from the node list')
 
        paramount_subcom_parser.add_argument('nodes', action='store', nargs='+',
                help='List with the id of the nodes: node-01, node-02...')
       
        paramount_subcom_parser.set_defaults(func=self.start_paramount_cluster)





    def start_paramount_cluster(self, namespace: argparse.Namespace ):
        pass