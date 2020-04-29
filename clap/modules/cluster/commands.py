import argparse
import os
import yaml

from typing import List

from clap.common.module import AbstractParser
from clap.common.utils import log, path_extend, float_time_to_string
from .module import cluster_create, cluster_setup, list_clusters, add_nodes_to_cluster, cluster_stop, cluster_alive, cluster_pause, cluster_resume
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
        cluster_subcom_parser.add_argument('--nodes', action='store_true', default=False,
                help='Setup only determined nodes of the cluster')
        cluster_subcom_parser.add_argument('--readd-group', action='store_true', default=False,
                help='Add nodes to the groups even if the nodes already belonging to it (default: False)')
        cluster_subcom_parser.add_argument('--extra', nargs=argparse.REMAINDER, metavar='arg=val',
                help="Keyworded (format: x=y) Arguments to be passed to the actions")
        cluster_subcom_parser.set_defaults(func=self.command_setup_cluster)

        cluster_subcom_parser = commands_parser.add_parser('add', help='Add more nodes to the cluster')
        cluster_subcom_parser.add_argument('cluster_id', action='store', 
                help='Id of the cluster to perform add nodes')
        cluster_subcom_parser.add_argument(
            'nodes', action='store', nargs='+', metavar='node_type:num',
            help='Type of the nodes to be instantiated (based on the cluster template). Format is <node_type>:<num>, '
                'if num is not provided, default is 1')
        cluster_subcom_parser.add_argument('--existing', '-e', action='store_true', default=False,
                help='Add existing nodes instead of instantiate new ones')
        cluster_subcom_parser.add_argument('--extra', nargs=argparse.REMAINDER, metavar='arg=val',
                help="Keyworded (format: x=y) Arguments to be passed to the actions")
        cluster_subcom_parser.set_defaults(func=self.command_add_more_nodes)

        cluster_subcom_parser = commands_parser.add_parser('list', help='List clusters')
        cluster_subcom_parser.add_argument('--id', '-i', action='store',
                help='List only the cluster with desired id')
        cluster_subcom_parser.add_argument('--full', '-f', action='store_true', default=False,
                help='Show full cluster information (including in use configuration)')
        cluster_subcom_parser.set_defaults(func=self.command_list_clusters)

        cluster_subcom_parser = commands_parser.add_parser('alive', help='Check if nodes of the cluster is alive')
        cluster_subcom_parser.add_argument('cluster_id', action='store', 
                help='Id of the cluster to check if nodes are alive')
        cluster_subcom_parser.set_defaults(func=self.command_alive_cluster_nodes)

        cluster_subcom_parser = commands_parser.add_parser('resume', help='Resume all nodes in the cluster')
        cluster_subcom_parser.add_argument('cluster_id', action='store', 
                help='Id of the cluster to resume')
        cluster_subcom_parser.set_defaults(func=self.command_resume_cluster)

        cluster_subcom_parser = commands_parser.add_parser('pause', help='Pause all nodes in the cluster')
        cluster_subcom_parser.add_argument('cluster_id', action='store', 
                help='Id of the cluster to pause')
        cluster_subcom_parser.set_defaults(func=self.command_pause_cluster)

        cluster_subcom_parser = commands_parser.add_parser('stop', help='Stop cluster')
        cluster_subcom_parser.add_argument('cluster_id', action='store', 
                help='Id of the cluster to perform add nodes')
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

        cluster, nodes_info = cluster_create(files, 
        cluser_name, 
        extra, 
        no_setup=namespace.no_setup)

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
    
    def command_add_more_nodes(self, namespace: argparse.Namespace):
        cluster_id = namespace.cluster_id
        existing = namespace.existing
        extra = {arg.split('=')[0]: arg.split('=')[1] for arg in namespace.extra} if namespace.extra else {}
        if not existing:
            # Mount parameters
            nodes = {}
            for node in namespace.nodes:
                splited_values = node.split(':')
                nodes[splited_values[0]] = 1 if len(splited_values) == 1 else int(splited_values[1])
            add_nodes_to_cluster(cluster_id, nodes)
        else:
            raise NotImplementedError
        return 0

    def command_list_clusters(self, namespace: argparse.Namespace):
        cluster_id = namespace.id if namespace.id else None
        full_conf = namespace.full 
        #list_clusters(cluster_id)
        for cluster_id, cluster_vals in list_clusters(cluster_id).items():
            cluster = {
                'id': cluster_id, 
                'name': cluster_vals['cluster']['cluster_name'],
                'state': cluster_vals['cluster']['cluster_state'],
                'creation time': float_time_to_string(cluster_vals['cluster']['creation_time']),
                'update time': float_time_to_string(cluster_vals['cluster']['update_time']),
                'nodes': cluster_vals['nodes']
            }

            if full_conf:
                cluster['in-use config'] = cluster_vals['cluster']['cluster_config']

            print(yaml.dump(cluster, indent=4))

        return 0
        
    def command_stop_cluster(self, namespace: argparse.Namespace):
        cluster_id = namespace.cluster_id
        cluster_stop(cluster_id)
        return 0
    
    def command_alive_cluster_nodes(self, namespace: argparse.Namespace):
        cluster_id = namespace.cluster_id
        alive_nodes = cluster_alive(cluster_id)
        if all(alive_nodes.values()):
            print("All nodes in the cluster are alive! Cluster is up!")
        else:
            print("The cluster may be paused. Nodes `{}` are not alive".format(', '.join(sorted(
                [node for node, aliveness in alive_nodes.items() if not aliveness]))))
        return 0

    def command_resume_cluster(self, namespace: argparse.Namespace):
        cluster_id = namespace.cluster_id
        ret = cluster_resume(cluster_id)
        return 0

    def command_pause_cluster(self, namespace: argparse.Namespace):
        cluster_id = namespace.cluster_id
        paused_nodes, not_paused_nodes = cluster_pause(cluster_id)
        return 0

    def commands_show_cluster(self, namespace: argparse.Namespace):
        raise NotImplementedError

    def commands_list_templates(self, namespace: argparse.Namespace):
        raise NotImplementedError