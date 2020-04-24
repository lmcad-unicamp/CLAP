import argparse
import os

from typing import List

from clap.common.module import AbstractParser
from clap.common.utils import log
from .module import cluster_create

def __is_valid_file__(fpath):
    if not os.path.exists(fpath):
        raise Exception("The file at `{}` does not exist".format(fpath))
    elif not os.path.isfile(fpath):
        raise Exception("The file at `{}` is not a valid file".format(fpath))
    else:
        return fpath

class ClusterParser(AbstractParser):
    def add_parser(self, commands_parser: argparse._SubParsersAction):
        cluster_subcom_parser = commands_parser.add_parser('start', help='Start cluster given a cluster configuration file')
        cluster_subcom_parser.add_argument('cluster_file', action='store', type=lambda fpath: __is_valid_file__(fpath),
                help='Path of the file with the cluster information')
        cluster_subcom_parser.set_defaults(func=self.command_start_cluster)

        cluster_subcom_parser = commands_parser.add_parser('stop', help='Stop cluster')
        cluster_subcom_parser.set_defaults(func=self.command_stop_cluster)


    def command_start_cluster(self, namespace: argparse.Namespace):
        cluster = cluster_create(namespace.cluster_file)
        return cluster

    def command_stop_cluster(self, namespace: argparse.Namespace):
        raise NotImplementedError