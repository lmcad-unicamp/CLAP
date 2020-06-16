import argparse

from clap.common.module import AbstractParser
from clap.common.utils import log
from .module import add_group_to_node, add_group_to_node_2, execute_group_action, list_groups, remove_group_from_node

# TODO add even with invalid ip
# TODO remove group
# TODO remove extra from group remove

class GroupsParser(AbstractParser):
    def add_parser(self, commands_parser: argparse._SubParsersAction):
        group_subcom_parser = commands_parser.add_parser('add', help='Add nodes to a group')
        group_subcom_parser.add_argument('group', action='store', help='Name of the group to be added')
        group_subcom_parser.add_argument('node_ids', action='store', nargs='*', help='ID of the nodes to be added to the group')
        group_subcom_parser.add_argument('--tag', action='store', help='Select nodes with specified tag')
        group_subcom_parser.add_argument('--extra', nargs=argparse.REMAINDER, metavar='arg=val',
                                        help="Keyworded (format: x=y) Arguments to be passed to the action")
        group_subcom_parser.set_defaults(func=self.command_add_group_to_node)

        group_subcom_parser = commands_parser.add_parser('add2', help='Add nodes to a group')
        group_subcom_parser.add_argument('group', action='store', help='Name of the group to be added')
        group_subcom_parser.add_argument('--host', action='append', required=True, nargs='+', 
                help='Hostname follwed by the ID of the nodes to be added to the group/hostname')
        group_subcom_parser.add_argument('--extra', nargs=argparse.REMAINDER, metavar='arg=val',
                                        help="Keyworded (format: x=y) Arguments to be passed to the action")
        group_subcom_parser.set_defaults(func=self.command_add_group_to_node_2)

        group_subcom_parser = commands_parser.add_parser('list', help='List available groups')
        group_subcom_parser.set_defaults(func=self.command_list_groups)

        group_subcom_parser = commands_parser.add_parser('action', help='Perform an action in the node group')
        group_subcom_parser.add_argument('group', action='store', help='Name of the group to perform the action')
        group_subcom_parser.add_argument('action', action='store', help='Name of the action to be performed')
        group_subcom_parser.add_argument('--nodes', action='store', nargs='+', help='ID of the nodes to be perform the action')
        group_subcom_parser.add_argument('--tag', action='store', help='Select nodes with specified tag')
        group_subcom_parser.add_argument('--extra', nargs=argparse.REMAINDER, metavar='arg=val',
                                        help="Keyworded (format: x=y) Arguments to be passed to the action")
        group_subcom_parser.set_defaults(func=self.command_execute_group_action)

        group_subcom_parser = commands_parser.add_parser('remove', help='Remove nodes from a group')
        group_subcom_parser.add_argument('group', action='store', help='Name of the group to be removed')
        group_subcom_parser.add_argument('node_ids', action='store', nargs='+', help='ID of the nodes to be removed from the group')
        group_subcom_parser.add_argument('--tag', action='store', help='Select nodes with specified tag')
        group_subcom_parser.add_argument('--extra', nargs=argparse.REMAINDER, metavar='arg=val',
                                        help="Keyworded (format: x=y) Arguments to be passed to the action")
        group_subcom_parser.set_defaults(func=self.command_remove_group_from_node)


    def command_add_group_to_node(self, namespace: argparse.Namespace):
        tag = None
        extra_args = None

        if namespace.tag:
            try:
                tag = {namespace.tag.split('=')[0]: '='.join(namespace.tag.split('=')[1:])}
            except Exception:
                raise Exception("Error mounting tag parameters. Please check the tag parameters passed")

        try:
            extra_args = {arg.split('=')[0]: '='.join(arg.split('=')[1:]) for arg in namespace.extra} if namespace.extra else {}
        except Exception:
            raise Exception("Error mounting extra parameters. Are you putting spaces after `=`? "
                            "Please check the extra parameters passed")

        added_nodes = add_group_to_node(namespace.node_ids, namespace.group, group_args=extra_args, tags=tag)

        if added_nodes:
            print("Nodes `{}` were successfully added to group `{}`".format(', '.join(sorted(added_nodes)), namespace.group))
        else:
            log.error("No nodes were added to group `{}`".format(namespace.group))

        return 0

    def command_add_group_to_node_2(self, namespace: argparse.Namespace):
        extra_args = None
        try:
            extra_args = {arg.split('=')[0]: '='.join(arg.split('=')[1:]) for arg in namespace.extra} if namespace.extra else {}
        except Exception:
            raise Exception("Error mounting extra parameters. Are you putting spaces after `=`? "
                            "Please check the extra parameters passed")

        hosts = {}
        for host_nodes in namespace.host:
            if len(host_nodes) < 2:
                raise Exception("A group's host cannot be empty (without any node)")
            hosts[host_nodes[0]] = host_nodes[1:]

        added_nodes = add_group_to_node_2(hosts, namespace.group, group_args=extra_args)

        if added_nodes:
            print("Nodes `{}` were successfully added to group `{}`".format(', '.join(sorted(added_nodes)), namespace.group))
        else:
            log.error("No nodes were added to group `{}`".format(namespace.group))

        return 0



    def command_execute_group_action(self, namespace: argparse.Namespace):
        tag = None
        extra_args = None

        if namespace.tag:
            try:
                tag = {namespace.tag.split('=')[0]: '='.join(namespace.tag.split('=')[1:])}
            except Exception:
                raise Exception("Error mounting tag parameters. Please check the tag parameters passed")

        try:
            extra_args = {arg.split('=')[0]: '='.join(arg.split('=')[1:]) for arg in namespace.extra} if namespace.extra else {}
        except Exception:
            raise Exception("Error mounting extra parameters. Are you putting spaces after `=`? "
                            "Please check the extra parameters passed")

        actioned_nodes = execute_group_action(node_ids=namespace.nodes, group=namespace.group, action=namespace.action, group_args=extra_args, tags=tag)

        if actioned_nodes:
            print("Nodes `{}` successfully performed action `{}` from group `{}`".format(
                ', '.join(sorted(actioned_nodes)), namespace.action, namespace.group))
        else:
            log.error("No nodes successcully performed action `{}` from group `{}`".format(namespace.action, namespace.group))

        return 0


    def command_list_groups(self, namespace: argparse.Namespace):
        groups = list_groups()

        for group_dict in sorted(groups, key=lambda x: x['name']):
            print("* GROUP: {}".format(group_dict['name']))
            print("  hosts: {}".format(', '.join(sorted(group_dict['hosts']))if group_dict['hosts'] else "none" ))
            for action_name, action_values in group_dict['actions'].items():
                print("  > action: {}".format(action_name))
                if action_values['description']:
                    print("    description: {}".format(action_values['description']))
                print("    playbook: {}".format(action_values['playbook']))
                if action_values['vars']:
                    print("    variables:")
                    for var in action_values['vars']:
                        print("      - name: {}".format(var['name']))
                        if var['description']:
                            print("        description: {}".format(var['description']))
                        print("        optional: {}".format(var['optional']))
            print('')

        print("Listed {} group(s)".format(len(groups)))

        return 0


    def command_remove_group_from_node(self, namespace: argparse.Namespace):
        tag = None
        extra_args = None

        if namespace.tag:
            try:
                tag = {namespace.tag.split('=')[0]: '='.join(namespace.tag.split('=')[1:])}
            except Exception:
                raise Exception("Error mounting tag parameters. Please check the tag parameters passed")

        try:
            extra_args = {arg.split('=')[0]: '='.join(arg.split('=')[1:]) for arg in namespace.extra} if namespace.extra else {}
        except Exception:
            raise Exception("Error mounting extra parameters. Are you putting spaces after `=`? "
                            "Please check the extra parameters passed")

        removed_nodes = remove_group_from_node(namespace.node_ids, namespace.group, group_args=extra_args, tags=tag)

        if removed_nodes:
            print("Nodes `{}` were successfully removed from group `{}`".format(', '.join(sorted(removed_nodes)), namespace.group))
        else:
            log.error("No nodes were removed from group `{}`".format(namespace.group))

        return 0