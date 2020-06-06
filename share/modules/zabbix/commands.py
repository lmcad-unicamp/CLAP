import argparse
import json
from typing import List

from clap.common.factory import PlatformFactory
from clap.common.module import AbstractParser
from clap.common.utils import log
from .module import start_zabbix_nodes


class ZabbixParser(AbstractParser):
    def add_parser(self, commands_parser: argparse._SubParsersAction):
        template_module = PlatformFactory.get_module_interface().get_module('template')
        node_templates = list(template_module.list_templates().keys())
        
        zabbix_subcom_parser = commands_parser.add_parser('start', help='Start zabbix node')
        zabbix_subcom_parser.add_argument(
            'nodes', action='store', nargs='+', metavar='node_type:num', choices=node_templates,
            help='Type of the nodes to be instantiated (based on the cluster template). Format is <node_type>:<num>, '
                'if num is not provided, default is 1')
        zabbix_subcom_parser.add_argument('--group', action='store', nargs='+', help='Groups to add nodes after started')
        zabbix_subcom_parser.add_argument('--tag', action='store', help='Tag nodes after started. Format: key=val')
        zabbix_subcom_parser.add_argument('--extra', nargs=argparse.REMAINDER, metavar='arg=val',
                                        help="Keyworded (format: x=y) Arguments to be passed to the group setup action")
        zabbix_subcom_parser.set_defaults(func=self.command_node_start)

    def command_node_start(self, namespace: argparse.Namespace):
        nodes = dict()
        
        # Mount parameters
        for node in namespace.nodes:
            splited_values = node.split(':')
            nodes[splited_values[0]] = 1 if len(splited_values) == 1 else int(splited_values[1])

        # Mount tags:
        if namespace.tag:
            try:
                tag = {namespace.tag.split('=')[0]: '='.join(namespace.tag.split('=')[1:])}
            except Exception:
                raise Exception("Error mounting tag parameters. Are you putting spaces after `=`? "
                                "Please check the tag parameters passed")
        
        # Mount namespace
        if namespace.group:
            try:
                extra = {arg.split('=')[0]: '='.join(arg.split('=')[1:]) for arg in namespace.extra} if namespace.extra else {}
            except Exception:
                raise Exception("Error mounting group's extra parameters. Are you putting spaces after `=`? "
                                "Please check the extra parameters passed")

        # Start nodes!
        nodes_info = start_zabbix_nodes(nodes)

        if not nodes_info:
            raise Exception("No nodes could be started")

        for node_info in nodes_info:
            print('* ', node_info)
        
        print("Started {} node(s)".format(len(nodes_info)))

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
