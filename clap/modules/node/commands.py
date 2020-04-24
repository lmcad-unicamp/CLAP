import argparse
import json
from typing import List

from clap.common.factory import PlatformFactory
from clap.common.module import AbstractParser
from clap.common.utils import log
from .interactive import interactive_shell
from .module import (start_nodes, list_nodes, is_alive, stop_nodes, 
                    resume_nodes, pause_nodes, execute_playbook, get_ssh_connections)

class NodeParser(AbstractParser):
    def add_parser(self, commands_parser: argparse._SubParsersAction):
        node_subcom_parser = commands_parser.add_parser('start', help='Start nodes in the cluster (based on the template)')
        node_subcom_parser.add_argument(
            'nodes', action='store', nargs='+', metavar='node_type:num',
            help='Type of the nodes to be instantiated (based on the cluster template). Format is <node_type>:<num>, '
                'if num is not provided, default is 1')
        node_subcom_parser.add_argument('--group', action='store', nargs='+', help='Groups to add nodes after started')
        node_subcom_parser.add_argument('--tag', action='store', help='Tag nodes after started. Format: key=val')
        node_subcom_parser.add_argument('--extra', nargs=argparse.REMAINDER, metavar='arg=val',
                                        help="Keyworded (format: x=y) Arguments to be passed to the group setup action")
        node_subcom_parser.set_defaults(func=self.command_node_start)

        node_subcom_parser = commands_parser.add_parser('list', help='List nodes')
        node_subcom_parser.add_argument('--tag', action='store', help='Select nodes with specified tag')
        node_subcom_parser.set_defaults(func=self.command_node_list)

        node_subcom_parser = commands_parser.add_parser('show', help='Show detailed information of the nodes')
        node_subcom_parser.add_argument('node_ids', action='store', nargs='*', help='ID of the nodes to be displayed')
        node_subcom_parser.add_argument('--tag', action='store', help='Select nodes with specified tag')
        node_subcom_parser.set_defaults(func=self.command_node_show)

        node_subcom_parser = commands_parser.add_parser('alive', help='Check if nodes are alive')
        node_subcom_parser.add_argument('node_ids', action='store', nargs='*', help='ID of the nodes to be checked')
        node_subcom_parser.add_argument('--tag', action='store', help='Select nodes with specified tag')
        node_subcom_parser.set_defaults(func=self.command_node_alive)

        node_subcom_parser = commands_parser.add_parser('stop', help='Stop and terminate nodes')
        node_subcom_parser.add_argument('node_ids', action='store', nargs='*', help='ID of the nodes to be stopped')
        node_subcom_parser.add_argument('--tag', action='store', help='Select nodes with specified tag')
        node_subcom_parser.set_defaults(func=self.command_node_stop)

        node_subcom_parser = commands_parser.add_parser('pause', help='Pause nodes')
        node_subcom_parser.add_argument('node_ids', action='store', nargs='+', help='ID of the nodes to be paused')
        node_subcom_parser.add_argument('--tag', action='store', help='Select nodes with specified tag')
        node_subcom_parser.set_defaults(func=self.command_node_pause)
        
        node_subcom_parser = commands_parser.add_parser('resume', help='Resume nodes')
        node_subcom_parser.add_argument('node_ids', action='store', nargs='+', help='ID of the nodes to be resumed')
        node_subcom_parser.add_argument('--tag', action='store', help='Select nodes with specified tag')
        node_subcom_parser.set_defaults(func=self.command_node_resume)

        node_subcom_parser = commands_parser.add_parser('playbook', help='Execute playbook in nodes')
        node_subcom_parser.add_argument('playbook_file', action='store', help='Playbook file to be executed')
        node_subcom_parser.add_argument('node_ids', action='store', nargs='+', help='ID of the nodes to be stopped')
        node_subcom_parser.add_argument('--extra', nargs=argparse.REMAINDER, metavar='arg=val',
                                        help="Keyworded (format: x=y) Arguments to be passed to the playbook")
        node_subcom_parser.set_defaults(func=self.command_node_playbook)

        node_subcom_parser = commands_parser.add_parser('execute', help='Execute a command in the node (via SSH)')
        node_subcom_parser.add_argument('node_id', action='store', help='ID of the node to get an SSH connection')
        node_subcom_parser.add_argument('cmd', nargs=argparse.REMAINDER, metavar='"cmd"',
                                        help='Command to be executed')
        node_subcom_parser.set_defaults(func=self.command_node_exec_command)

        node_subcom_parser = commands_parser.add_parser('connect', help='Connect via SSH to a node')
        node_subcom_parser.add_argument('node_id', action='store', help='ID of the node to get an SSH connection')
        node_subcom_parser.set_defaults(func=self.command_node_connect)

    def command_node_start(self, namespace: argparse.Namespace):
        nodes = dict()
        
        # Mount parameters
        for node in namespace.nodes:
            splited_values = node.split(':')
            nodes[splited_values[0]] = 1 if len(splited_values) == 1 else int(splited_values[1])

        # Mount tags:
        if namespace.tag:
            try:
                tag = {namespace.tag.split('=')[0]: namespace.tag.split('=')[1]}
            except Exception:
                raise Exception("Error mounting tag parameters. Are you putting spaces after `=`? "
                                "Please check the tag parameters passed")
        
        # Mount namespace
        if namespace.group:
            try:
                extra = {arg.split('=')[0]: arg.split('=')[1] for arg in namespace.extra} if namespace.extra else {}
            except Exception:
                raise Exception("Error mounting group's extra parameters. Are you putting spaces after `=`? "
                                "Please check the extra parameters passed")

        # Start nodes!
        nodes_info = start_nodes(nodes)

        if not nodes_info:
            raise Exception("No nodes could be started")

        print("Started {} node(s)".format(len(nodes_info)))
        for node_info in nodes_info:
            print('* ', node_info)

        if namespace.tag:
            try:
                tag_module = PlatformFactory.get_module_interface().get_module('tag')
                tagged_nodes = tag_module.node_add_tag([n.node_id for n in nodes_info], tag)
                print("Added tag `{}` to {} nodes".format(namespace.tag, ', '.join(tagged_nodes)))
            except Exception as e:
                log.error("Error adding tag to nodes: {}".format(e))
                raise

        if namespace.group:
            try:
                group_module = PlatformFactory.get_module_interface().get_module('group')
                for group in namespace.group:
                    started_nodes = [n.node_id for n in nodes_info]
                    print("Adding nodes `{}` to group: `{}`".format(', '.join(started_nodes), group))
                    added_nodes = group_module.add_group_to_node(started_nodes, group, group_args=extra)
                    
                    if added_nodes:
                        print("Nodes `{}` were successfully added to group `{}`".format(', '.join(added_nodes), group))
                    else:
                        log.error("No nodes were added to group `{}`".format(group))

            except Exception as e:
                log.error("Error adding nodes to group: {}".format(e))
                raise 

        return 0

    def command_node_list(self, namespace: argparse.Namespace):
        if namespace.tag:
            try:
                tag = {namespace.tag.split('=')[0]: namespace.tag.split('=')[1]}
            except Exception:
                raise Exception("Error mounting tag parameters. Are you putting spaces after `=`? "
                                "Please check the tag parameters passed")
        else:
            tag = {}

        nodes = list_nodes(node_ids=None, tags=tag)

        for node_info in nodes:
            print('* ', node_info)

        print("Listed {} node(s)".format(len(nodes)))

        return 0

    def command_node_show(self, namespace: argparse.Namespace):
        node_ids = list(set(namespace.node_ids))

        if namespace.tag:
            try:
                tag = {namespace.tag.split('=')[0]: namespace.tag.split('=')[1]}
            except Exception:
                raise Exception("Error mounting tag parameters. Are you putting spaces after `=`? "
                                "Please check the tag parameters passed")
        else:
            tag = {}

        nodes = list_nodes(node_ids=node_ids, tags=tag)

        for node_info in nodes:
            print('------- `{}` --------'.format(node_info.node_id))
            print(json.dumps(node_info.__dict__, indent=4))

        print("Listed {} node(s)".format(len(nodes)))

        return 0

    def command_node_alive(self, namespace: argparse.Namespace):
        node_ids = list(set(namespace.node_ids))

        if namespace.tag:
            try:
                tag = {namespace.tag.split('=')[0]: namespace.tag.split('=')[1]}
            except Exception:
                raise Exception("Error mounting tag parameters. Are you putting spaces after `=`? "
                                "Please check the tag parameters passed")
        else:
            tag = {}

        alive_nodes = is_alive(node_ids, tag)

        print(' ------ ALIVE NODES ------ ')
        for k in sorted(alive_nodes.keys()):
            print("* {} --> {}".format(k, 'alive' if alive_nodes[k] else 'not reachable'))

        print('Checked {} node(s)'.format(len(alive_nodes)))

        return 0

    def command_node_stop(self, namespace: argparse.Namespace):
        node_ids = list(set(namespace.node_ids))

        if namespace.tag:
            try:
                tag = {namespace.tag.split('=')[0]: namespace.tag.split('=')[1]}
            except Exception:
                raise Exception("Error mounting tag parameters. Are you putting spaces after `=`? "
                                "Please check the tag parameters passed")
        else:
            tag = {}

        node_ids = stop_nodes(node_ids=node_ids, tags=tag)

        if not node_ids:
            print("No nodes were stopped")
        else:
            print("Nodes `{}` stopped".format(', '.join(node_ids)))

        return 0

    def command_node_resume(self, namespace: argparse.Namespace):
        node_ids = list(set(namespace.node_ids))

        if namespace.tag:
            try:
                tag = {namespace.tag.split('=')[0]: namespace.tag.split('=')[1]}
            except Exception:
                raise Exception("Error mounting tag parameters. Are you putting spaces after `=`? "
                                "Please check the tag parameters passed")
        else:
            tag = {}

        node_ids = resume_nodes(node_ids=node_ids, tags=tag)

        if not node_ids:
            print("No nodes were resumed")
        else:
            print("Nodes `{}` resumed".format(', '.join(node_ids)))

        return 0

    def command_node_pause(self, namespace: argparse.Namespace):
        node_ids = list(set(namespace.node_ids))

        if namespace.tag:
            try:
                tag = {namespace.tag.split('=')[0]: namespace.tag.split('=')[1]}
            except Exception:
                raise Exception("Error mounting tag parameters. Are you putting spaces after `=`? "
                                "Please check the tag parameters passed")
        else:
            tag = {}

        node_ids = pause_nodes(node_ids=node_ids, tags=tag)

        if not node_ids:
            print("No nodes were paused")
        else:
            print("Nodes `{}` paused".format(', '.join(node_ids)))

        return 0

    def command_node_playbook(self, namespace: argparse.Namespace):
        node_ids = list(set(namespace.node_ids))

        try:
            extra = {arg.split('=')[0]: arg.split('=')[1] for arg in namespace.extra} if namespace.extra else {}
        except Exception:
            raise Exception("Error mounting extra parameters. Are you putting spaces after `=`? "
                            "Please check the tag parameters passed")

        execute_playbook(namespace.playbook_file, node_ids, extra_args=extra)

        return 0

    def command_node_exec_command(self, namespace: argparse.Namespace):
        command = ' '.join(namespace.cmd)
        ssh_client = get_ssh_connections([namespace.node_id])

        if not ssh_client:
            raise Exception("Connection to `{}` was unsuccessful. "
                            "Check you internet connection or if the node is up and alive".format(namespace.node_id))

        print('Executing in node `{}` the command (via SSH): `{}`'.format(namespace.node_id, command))

        ssh_client = ssh_client[namespace.node_id]
        _, stdout, stderr = ssh_client.exec_command(command)
        print("{} STD OUTPUT {}".format('-'*40, '-'*40))
        print(''.join(stdout.readlines()))
        print("{} ERR OUTPUT {}".format('-'*40, '-'*40))
        print(''.join(stderr.readlines()))
        print('-' * 80)

        ssh_client.close()

        return 0

    def command_node_connect(self, namespace: argparse.Namespace):
        print('Connecting to node `{}` (via SSH)'.format(namespace.node_id))

        # Not the best way...
        if list_nodes([namespace.node_id])[0].driver_id == 'ansible':
            get_ssh_connections([namespace.node_id], open_shell=True)

        else:
            ssh_client = get_ssh_connections([namespace.node_id])[namespace.node_id]
            if not ssh_client:
                raise Exception("Connection to `{}` was unsuccessful. "
                                "Check you internet connection or if the node is up and alive".format(namespace.node_id))
            channel = ssh_client.get_transport().open_session()
            channel.get_pty()
            channel.invoke_shell()
            interactive_shell(channel)
            ssh_client.close()
        
        print("Connection to `{}` closed".format(namespace.node_id))
        return 0