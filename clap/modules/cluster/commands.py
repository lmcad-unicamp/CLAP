import argparse
import os
import yaml

from typing import List

from clap.common.module import AbstractParser
from clap.common.utils import log, path_extend, float_time_to_string
from .module import *
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

# TODO cluster resume --setup --at=after_all
# TODO cluster remove-node

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

        # cluster setup commands
        cluster_subcom_parser = commands_parser.add_parser('setup', help='Setup an existing cluster')
        cluster_subcom_parser.add_argument('cluster_id', action='store', 
                help='Id of the cluster to perform setup')
        cluster_subcom_parser.add_argument('--readd-group', action='store_true', default=False,
                help='Add nodes to the groups even if the nodes already belonging to it (default: False)')
        cluster_subcom_parser.add_argument('--nodes', action='store', nargs='+',
                help='Run setup at only specific nodes of the cluster')
        cluster_subcom_parser.add_argument('--at', action='store',
                help='Start setup at desired phase (the pipeline is: before_all, before, node, after, after_all)')
        cluster_subcom_parser.set_defaults(func=self.command_setup_cluster)

        # Add nodes to cluster
        cluster_subcom_parser = commands_parser.add_parser('add', help='Add more nodes to the cluster')
        cluster_subcom_parser.add_argument('cluster_id', action='store', 
                help='Id of the cluster to perform add nodes')
        cluster_subcom_parser.add_argument('nodes', action='store', nargs='+', metavar='node_type:num',
                help='Type of the nodes to be instantiated (based on the cluster template). Format is <node_type>:<num>, '
                'if num is not provided, default is 1')
        cluster_subcom_parser.add_argument('--readd-group', action='store_true', default=False,
                help='Add nodes to the groups even if the nodes already belonging to it (default: False)')
        cluster_subcom_parser.add_argument('--at', nargs='?', action='store', const='before_all',
                help='Start setup at desired phase (the pipeline is: before_all, before, node, after, after_all)')
        cluster_subcom_parser.add_argument('--no-setup', action='store_true', default=False,
                help='Does not setup the cluster')
        cluster_subcom_parser.set_defaults(func=self.command_add_more_nodes)

        # Add existing nodes to cluster
        cluster_subcom_parser = commands_parser.add_parser('add-existing', help='Add existing nodes to the cluster')
        cluster_subcom_parser.add_argument('cluster_id', action='store', 
                help='Id of the cluster to perform add nodes')
        cluster_subcom_parser.add_argument('node_type', action='store',
                help='Type of the cluster node that nodes will belong')
        cluster_subcom_parser.add_argument('node_ids', action='store', nargs='+',
                help='ID of the nodes to add to cluster')
        cluster_subcom_parser.add_argument('--readd-group', action='store_true', default=False,
                help='Add nodes to the groups even if the nodes already belonging to it (default: False)')
        cluster_subcom_parser.add_argument('--at', nargs='?', action='store', const='before_all',
                help='Start setup at desired phase (the pipeline is: before_all, before, node, after, after_all)')
        cluster_subcom_parser.add_argument('--no-setup', action='store_true', default=False,
                help='Does not setup the cluster')
        cluster_subcom_parser.set_defaults(func=self.command_existing_nodes)

        # cluster list
        cluster_subcom_parser = commands_parser.add_parser('list', help='List clusters')
        cluster_subcom_parser.add_argument('--id', '-i', action='store',
                help='List only the cluster with desired id')
        cluster_subcom_parser.add_argument('--full', '-f', action='store_true', default=False,
                help='Show full cluster information (including in use configuration)')
        cluster_subcom_parser.set_defaults(func=self.command_list_clusters)

        # cluster alive
        cluster_subcom_parser = commands_parser.add_parser('alive', help='Check if nodes of the cluster is alive')
        cluster_subcom_parser.add_argument('cluster_id', action='store', 
                help='Id of the cluster to check if nodes are alive')
        cluster_subcom_parser.set_defaults(func=self.command_alive_cluster_nodes)

        # cluster resume
        cluster_subcom_parser = commands_parser.add_parser('resume', help='Resume all nodes in the cluster')
        cluster_subcom_parser.add_argument('cluster_id', action='store', 
                help='Id of the cluster to resume')
        cluster_subcom_parser.add_argument('--setup', action='store_true', default=False,
                help='Setup the cluster after resume')
        cluster_subcom_parser.add_argument('--at', nargs='?', action='store', const='before_all',
                help='Start setup at desired phase (the pipeline is: before_all, before, node, after, after_all)')
        cluster_subcom_parser.set_defaults(func=self.command_resume_cluster)

        # cluster pause
        cluster_subcom_parser = commands_parser.add_parser('pause', help='Pause all nodes in the cluster')
        cluster_subcom_parser.add_argument('cluster_id', action='store', 
                help='Id of the cluster to pause')
        cluster_subcom_parser.set_defaults(func=self.command_pause_cluster)

        # cluster stop
        cluster_subcom_parser = commands_parser.add_parser('stop', help='Stop cluster')
        cluster_subcom_parser.add_argument('cluster_id', action='store', 
                help='Id of the cluster to perform add nodes')
        cluster_subcom_parser.set_defaults(func=self.command_stop_cluster)

        # cluster list-templates
        cluster_subcom_parser = commands_parser.add_parser('list-templates', help='List all cluster templates')
        cluster_subcom_parser.add_argument('--file', '-f', action='store', 
                type=lambda path: __is_valid_file__(path),
                help='File of the cluster configuration template (this option replaces the --directory option')
        cluster_subcom_parser.add_argument('--directory', '-d', default=ClusterDefaults.CLUSTER_SEARCH_PATH, 
                type=lambda path: __is_valid_directory__(path),
                help='Directory to search for cluster templates (Default is: `{}`)'.format(ClusterDefaults.CLUSTER_SEARCH_PATH))
        cluster_subcom_parser.set_defaults(func=self.commands_list_templates)

        # cluster update
        cluster_subcom_parser = commands_parser.add_parser('update', help='Update cluster configuration')
        cluster_subcom_parser.add_argument('cluster_id', action='store', 
                help='Id of the cluster to update the configuration')
        cluster_subcom_parser.add_argument('--file', '-f', action='store', 
                type=lambda path: __is_valid_file__(path),
                help='File of the cluster configuration template (this option replaces the --directory option')
        cluster_subcom_parser.add_argument('--directory', '-d', default=ClusterDefaults.CLUSTER_SEARCH_PATH, 
                type=lambda path: __is_valid_directory__(path),
                help='Directory to search for cluster templates (Default is: `{}`)'.format(ClusterDefaults.CLUSTER_SEARCH_PATH))
        cluster_subcom_parser.add_argument('--extra', nargs=argparse.REMAINDER, metavar='arg=val',
                help="Keyworded (format: x=y) Arguments to be passed to the actions")
        cluster_subcom_parser.set_defaults(func=self.commands_update_cluster)

        # cluster group
        cluster_subcom_parser = commands_parser.add_parser('group', help="Add group to cluster's nodes")
        cluster_subcom_parser.add_argument('cluster_id', action='store', help='Id of the cluster to add nodes to group')
        cluster_subcom_parser.add_argument('group', action='store', help='Name of the group to add nodes')
        cluster_subcom_parser.add_argument('--nodes', action='store', nargs='+',
                help='ID of the nodes to add to group. If none is supplied, all nodes in the cluster will be added to group')
        cluster_subcom_parser.add_argument('--readd-group', action='store_true', default=False,
                help='Add nodes to the groups even if the nodes already belonging to it (default: False)')
        cluster_subcom_parser.add_argument('--extra', nargs=argparse.REMAINDER, metavar='arg=val',
                help="Keyworded (format: x=y) Arguments to be passed to the actions")
        cluster_subcom_parser.set_defaults(func=self.commands_group_add)

        # cluster action
        cluster_subcom_parser = commands_parser.add_parser('action', help="Perform a group action in cluster's nodes")
        cluster_subcom_parser.add_argument('cluster_id', action='store',  help='Id of the cluster to perform action')
        cluster_subcom_parser.add_argument('group', action='store', help='Name of the group to perform action')
        cluster_subcom_parser.add_argument('action', action='store', help='Name of the action to perform')
        cluster_subcom_parser.add_argument('--nodes', action='store', nargs='+',
                help='ID of the nodes to perform action. If none is supplied, all nodes in the cluster will be added to group')
        cluster_subcom_parser.add_argument('--extra', nargs=argparse.REMAINDER, metavar='arg=val',
                help="Keyworded (format: x=y) Arguments to be passed to the actions")
        cluster_subcom_parser.set_defaults(func=self.commands_group_action)

        # cluster connect
        cluster_subcom_parser = commands_parser.add_parser('connect', help="Connect to cluster's nodes")
        cluster_subcom_parser.add_argument('cluster_id', action='store', help='Id of the cluster to connect')
        cluster_subcom_parser.add_argument('--node', action='store', 
                help="Id of cluster's node to connect. If none is supplied it will take the a node from cluster's ssh_to option")
        cluster_subcom_parser.set_defaults(func=self.commands_connect)

        # cluster execute
        cluster_subcom_parser = commands_parser.add_parser('execute', help='Execute a command in the node (via SSH)')
        cluster_subcom_parser.add_argument('cluster_id', action='store', help='Id of the cluster to execute the command')
        cluster_subcom_parser.add_argument('--nodes', action='store', nargs='+',
                help='ID of the nodes to execute the command. If none is supplied, all nodes in the cluster will execute the command')
        cluster_subcom_parser.add_argument('--command', '-c',  action='store', required=True, help='Command string to be executed')
        cluster_subcom_parser.set_defaults(func=self.commands_execute)

        # cluster playbook
        cluster_subcom_parser = commands_parser.add_parser('playbook', help="Execute an Ansible playbook in cluster's nodes")
        cluster_subcom_parser.add_argument('cluster_id', action='store', help='Id of the cluster to execute the playbook')
        cluster_subcom_parser.add_argument('playbook_file', action='store', help='Playbook file to be executed')
        cluster_subcom_parser.add_argument('--nodes', action='store', nargs='+',
                help='ID of the nodes to execute the playbook. If none is supplied, all nodes in the cluster will execute the playbook')
        cluster_subcom_parser.add_argument('--extra', nargs=argparse.REMAINDER, metavar='arg=val',
                                        help="Keyworded (format: x=y) Arguments to be passed to the playbook")
        cluster_subcom_parser.set_defaults(func=self.commands_playbook)

        # cluster copy
        cluster_subcom_parser = commands_parser.add_parser('copy', help="Copy files from localhost to cluster's nodes")
        cluster_subcom_parser.add_argument('cluster_id', action='store', help='Id of the cluster to copy files')
        cluster_subcom_parser.add_argument('_from', action='store', help='Path of files to copy (localhost)')
        cluster_subcom_parser.add_argument('dest', action='store', help="Destination where files will be placed (cluster's nodes")
        cluster_subcom_parser.add_argument('--nodes', action='store', nargs='+',
                help='ID of the nodes to copy files. If none is supplied, all nodes in the cluster will have the files copyied')
        cluster_subcom_parser.set_defaults(func=self.commands_copy)

        # cluster fetch
        cluster_subcom_parser = commands_parser.add_parser('fetch', help="Fetch from cluster's nodes to localhost")
        cluster_subcom_parser.add_argument('cluster_id', action='store', help='Id of the cluster to copy files')
        cluster_subcom_parser.add_argument('_from', action='store', help="Path of files to copy (cluster's nodes)")
        cluster_subcom_parser.add_argument('dest', action='store', help="Destination where files will be placed (localhost)")
        cluster_subcom_parser.add_argument('--nodes', action='store', nargs='+',
                help='ID of the nodes to fetch files. If none is supplied, all nodes in the cluster will have the files copyied')
        cluster_subcom_parser.set_defaults(func=self.commands_fetch)
        

    def command_start_cluster(self, namespace: argparse.Namespace):
        cluster_name = namespace.cluster_name
        extra = {arg.split('=')[0]: '='.join(arg.split('=')[1:]) for arg in namespace.extra} if namespace.extra else {}
        
        files = []
        if namespace.file:
            files = [path_extend(namespace.file)]
        else:
            for f in os.listdir(namespace.directory):
                files += [path_extend(namespace.directory, f) for ftype in ClusterDefaults.CLUSTER_DEFAULT_FLETYPES 
                    if f.endswith(ftype)]

        cluster, nodes_info, is_setup = cluster_create(files, cluster_name, extra, no_setup=namespace.no_setup)

        print("Created cluster with id `{}`. The cluster have {} node(s)".format(cluster.cluster_id, len(nodes_info)))
        for node_info in nodes_info:
            print('* ', node_info)
        print("Cluster `{}` was {} setup.".format(cluster.cluster_id, "sucessfully" if is_setup else "not"))
        return 0

    def command_setup_cluster(self, namespace: argparse.Namespace):
        cluster_id = namespace.cluster_id
        at = namespace.at if namespace.at else 'before_all'
        readd_group = namespace.readd_group
        nodes = namespace.nodes
        cluster_setup_in_specific_nodes(cluster_id, node_ids=nodes, re_add_to_group=readd_group, at=at)
        print("Cluster `{}` successfully setup".format(cluster_id))
        return 0
    
    def command_add_more_nodes(self, namespace: argparse.Namespace):
        cluster_id = namespace.cluster_id
        at = namespace.at if namespace.at else 'before_all'
        readd_group = namespace.readd_group
        no_setup = namespace.no_setup

        nodes = {}
        for node in namespace.nodes:
            splited_values = node.split(':')
            nodes[splited_values[0]] = 1 if len(splited_values) <= 1 else int(splited_values[1])

        add_nodes_to_cluster(cluster_id, nodes, no_setup=no_setup, re_add_to_group=readd_group, at=at)
        return 0

    def command_existing_nodes(self, namespace: argparse.Namespace):
        cluster_id = namespace.cluster_id
        at = namespace.at if namespace.at else 'before_all'
        readd_group = namespace.readd_group
        node_type = namespace.node_type
        node_ids = namespace.node_ids
        no_setup = namespace.no_setup

        add_existing_nodes_to_cluster(cluster_id, {node_type: node_ids}, no_setup=no_setup, re_add_to_group=readd_group, at=at)
        return 0

    def command_list_clusters(self, namespace: argparse.Namespace):
        cluster_id = namespace.id if namespace.id else None
        full_conf = namespace.full 
        no_clusters = 0
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
            no_clusters += 1
        
        print("Listed {} cluster(s)".format(no_clusters))
        return 0
        
    def command_stop_cluster(self, namespace: argparse.Namespace):
        cluster_id = namespace.cluster_id
        cluster_stop(cluster_id)
        print("Cluster `{}` stopped!".format(cluster_id))
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
        at = namespace.at if namespace.at else 'before_all'
        setup_cluster = namespace.setup
        node_ids = cluster_resume(cluster_id, setup=setup_cluster, at=at)
        #for node in node_ids:
        print("Nodes `{}` from cluster `{}` resumed!".format(', '.join(sorted(node_ids)), cluster_id))
        return 0

    def command_pause_cluster(self, namespace: argparse.Namespace):
        cluster_id = namespace.cluster_id
        paused_nodes, not_paused_nodes = cluster_pause(cluster_id)
        print("Nodes `{}` from cluster `{}` were paused".format(sorted(paused_nodes), cluster_id))
        if not_paused_nodes:
            print("Nodes `{}` from cluster `{}` were not paused".format(sorted(not_paused_nodes), cluster_id))
        return 0

    def commands_list_templates(self, namespace: argparse.Namespace):
        files = []
        if namespace.file:
            files = [path_extend(namespace.file)]
        else:
            for f in os.listdir(namespace.directory):
                files += [path_extend(namespace.directory, f) for ftype in ClusterDefaults.CLUSTER_DEFAULT_FLETYPES 
                    if f.endswith(ftype)]
        
        clusters, _ = list_templates(files)
        no_clusters = 0

        for cluster_name, cluster_vals in clusters.items():
            try:
                print("------- Cluster: `{}` -------".format(cluster_name))
                if cluster_vals['before_all']:
                    print("* before_all: {}".format(', '.join(cluster_vals['before_all'])))
                if cluster_vals['before']:
                    print("* before: {}".format(', '.join(cluster_vals['before'])))
                if cluster_vals['after']:
                    print("* after: {}".format(', '.join(cluster_vals['after'])))
                if cluster_vals['after_all']:
                    print("* after_all: {}".format(', '.join(cluster_vals['after_all'])))

                for node_name, node_vals in cluster_vals['nodes'].items():
                    print("* node name: `{}`".format(node_name))
                    print("  type: {}".format(node_vals['type']))
                    print("  setups: {}".format(', '.join(node_vals['setups'])))
                print()
                no_clusters += 1
            except Exception as e:
                log.error(e)
                log.error("Error at cluster `{}`, skipping...".format(cluster_name))
            

        print("Listed {} cluster template(s)".format(no_clusters))
        return 0

    def commands_update_cluster(self, namespace: argparse.Namespace):
        cluster_id = namespace.cluster_id
        extra = {arg.split('=')[0]: '='.join(arg.split('=')[1:]) for arg in namespace.extra} if namespace.extra else {}

        files = []
        if namespace.file:
            files = [path_extend(namespace.file)]
        else:
            for f in os.listdir(namespace.directory):
                files += [path_extend(namespace.directory, f) for ftype in ClusterDefaults.CLUSTER_DEFAULT_FLETYPES 
                    if f.endswith(ftype)]

        cluster = update_cluster_config(files, cluster_id, extra)
        print("Updated configuration for cluster `{}`".format(cluster.cluster_id))
        return 0

    def commands_group_add(self, namespace: argparse.Namespace):
        cluster_id = namespace.cluster_id
        group_name = namespace.group
        readd_group = namespace.readd_group
        nodes = namespace.nodes
        extra = {arg.split('=')[0]: '='.join(arg.split('=')[1:]) for arg in namespace.extra} if namespace.extra else {}
        node_ids = cluster_group_add(cluster_id, group_name=group_name, node_ids=nodes, re_add_to_group=readd_group, extra_args=extra)
        print("Nodes `{}` from cluster `{}` were added to group `{}`".format(', '.join(sorted(node_ids)), cluster_id, group_name))
        return 0

    def commands_group_action(self, namespace: argparse.Namespace):
        cluster_id = namespace.cluster_id
        group_name = namespace.group
        action_name = namespace.action
        nodes = namespace.nodes
        extra = {arg.split('=')[0]: '='.join(arg.split('=')[1:]) for arg in namespace.extra} if namespace.extra else {}
        node_ids = perform_group_action(cluster_id, group_name=group_name, action_name=action_name, node_ids=nodes, extra_args=extra)
        print("Nodes `{}` from cluster `{}` successfully perfored action `{}`".format(', '.join(sorted(node_ids)), cluster_id, action_name))
        return 0

    def commands_connect(self, namespace: argparse.Namespace):
        cluster_id = namespace.cluster_id
        node_id = namespace.node
        cluster_connect(cluster_id, node_id)
        return 0

    def commands_execute(self, namespace: argparse.Namespace):
        cluster_id = namespace.cluster_id
        node_ids = namespace.nodes
        command = namespace.command
        execute_command(cluster_id, command=command, node_ids=node_ids)
        return 0

    def commands_playbook(self, namespace: argparse.Namespace):
        cluster_id = namespace.cluster_id
        playbook_path = namespace.playbook_file
        nodes = namespace.nodes
        extra = {arg.split('=')[0]: '='.join(arg.split('=')[1:]) for arg in namespace.extra} if namespace.extra else {}
        executeds = execute_playbook(cluster_id, playbook_path=playbook_path, node_ids=nodes, extra_args=extra)
        print("Nodes `{}` from cluster `{}` successfully executed playbook `{}`".format(
            sorted([node_id for node_id, status in executeds.items() if status]), cluster_id, playbook_path))
        return 0

    def commands_copy(self, namespace: argparse.Namespace):
        cluster_id = namespace.cluster_id
        copy_from = namespace._from
        copy_dest = namespace.dest
        nodes = namespace.nodes
        cluster_copy_files(cluster_id, copy_from=copy_from, copy_to=copy_dest, node_ids=nodes)
        return 0

    def commands_fetch(self, namespace: argparse.Namespace):
        cluster_id = namespace.cluster_id
        copy_from = namespace._from
        copy_dest = namespace.dest
        nodes = namespace.nodes
        cluster_fetch_files(cluster_id, copy_from=copy_from, copy_to=copy_dest, node_ids=nodes)
        return 0