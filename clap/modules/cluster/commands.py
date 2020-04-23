import argparse

from typing import List

from clap.common.module import AbstractParser
from clap.common.utils import log
from .module import cluster_create

class ClusterParser(AbstractParser):
    def add_parser(self, commands_parser: argparse._SubParsersAction):
        cluster_subcom_parser = commands_parser.add_parser('start', help='Start cluster given a cluster configuration file')
        cluster_subcom_parser.set_defaults(func=self.command_start_cluster)

        cluster_subcom_parser = commands_parser.add_parser('stop', help='Stop cluster')
        cluster_subcom_parser.set_defaults(func=self.command_stop_cluster)


    def command_start_cluster(self, namespace: argparse.Namespace):
        raise NotImplementedError

    def command_stop_cluster(self, namespace: argparse.Namespace):
        raise NotImplementedError