import argparse
import os

from typing import List

from clap.common.module import AbstractParser
from clap.common.utils import log, path_extend
from .module import cluster_create, cluster_setup, list_clusters
from .conf import ClusterDefaults

def __is_valid_file__(fpath):
    if not os.path.exists(fpath):
        raise Exception("The file at `{}` does not exist".format(fpath))
    elif not os.path.isfile(fpath):
        raise Exception("The file at `{}` is not a valid file".format(fpath))
    else:
        return fpath

def __is_valid_directory__(fpath):
    if not os.path.exists(fpath):
        raise Exception("The directory at `{}` does not exist".format(fpath))
    elif not os.path.isdir(fpath):
        raise Exception("The directiry at `{}` is not a valid directory".format(fpath))
    else:
        return fpath

class ClusterParser(AbstractParser):
    def add_parser(self, commands_parser: argparse._SubParsersAction):
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

        cluster_subcom_parser = commands_parser.add_parser('setup', help='Setup an existing cluster')
        cluster_subcom_parser.add_argument('cluster_id', action='store', 
                help='Id of the cluster to perform setup')
        cluster_subcom_parser.add_argument('--readd-group', action='store_true', default=False,
                help='Add nodes to the groups even if the nodes already belonging to it (default: False)')
        cluster_subcom_parser.add_argument('--extra', nargs=argparse.REMAINDER, metavar='arg=val',
                help="Keyworded (format: x=y) Arguments to be passed to the actions")
        cluster_subcom_parser.set_defaults(func=self.command_setup_cluster)

        cluster_subcom_parser = commands_parser.add_parser('list', help='List  clusters')
        cluster_subcom_parser.add_argument('--id', action='store',
                help='List only the cluster with desired id')
        cluster_subcom_parser.set_defaults(func=self.command_list_clusters)

        cluster_subcom_parser = commands_parser.add_parser('stop', help='Stop cluster')
        cluster_subcom_parser.set_defaults(func=self.command_stop_cluster)


    def command_start_cluster(self, namespace: argparse.Namespace):
        cluser_name = namespace.cluster_name
        extra = {arg.split('=')[0]: arg.split('=')[1] for arg in namespace.extra} if namespace.extra else {}
        
        files = []
        if namespace.file:
            files = [path_extend(namespace.file)]
        else:
            for f in os.listdir(namespace.directory):
                files += [path_extend(namespace.directory, f) for ftype in ClusterDefaults.CLUSTER_DEFAULT_FLETYPES 
                    if f.endswith(ftype)]

        cluster, nodes_info = cluster_create(files, cluser_name, extra, no_setup=namespace.no_setup)

        print("Created cluster with id `{}`. The cluster have {} node(s)".format(cluster.cluster_id, len(nodes_info)))
        for node_info in nodes_info:
            print('* ', node_info)
        return 0

    def command_setup_cluster(self, namespace: argparse.Namespace):
        cluster_id = namespace.cluster_id
        extra = {arg.split('=')[0]: arg.split('=')[1] for arg in namespace.extra} if namespace.extra else {}
        cluster_setup(cluster_id, extra, namespace.readd_group)
        print("Cluster `{}` successfully setup".format(cluster_id))
        return 0
    
    def command_list_clusters(self, namespace: argparse.Namespace):
        cluster_id = namespace.id if namespace.id else None
        #list_clusters(cluster_id)
        import json
        print(json.dumps(list_clusters(cluster_id), indent=2))
        return 0
        
    def command_stop_cluster(self, namespace: argparse.Namespace):
        raise NotImplementedError