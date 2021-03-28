from collections import defaultdict
from dataclasses import asdict

import click
import yaml

from common.utils import get_logger
from modules.group import GroupModule, GroupDefaults
from modules.node import NodeDefaults
from app.module import clap_command

logger = get_logger(__name__)

node_defaults = NodeDefaults()
group_defaults = GroupDefaults()


@clap_command
@click.group(help='Control and manage roles')
@click.option('-p', '--platform-db', default=node_defaults.node_repository_path, help='Platform database to be used, where nodes will be written', show_default=True)
@click.option('-g', '--groups-path', default=group_defaults.groups_path, help='Path where groups will be search for', show_default=True)
def role(platform_db, groups_path):
    node_defaults.node_repository_path = platform_db
    group_defaults.groups_path = groups_path


@role.command('add')
@click.argument('group', nargs=1, type=str, required=True)
@click.option('-n', '--node', nargs=1, type=str, required=True, multiple=True,
              help='Nodes to be added. Can be a list of colon-separated nodes (<node>,<node>,...) or <group_host_name>:<node>,<node>')
@click.option('-e', '--extra', help='Extra arguments. Format <key>=<value>', multiple=True)
@click.option('-h', '--host-extra', help='Extra host arguments. Format <node_id>:<key>=<value>', multiple=True)
@click.option('-ge', '--group-extra', help='Extra group arguments. Format <group_name>:<key>=<value>', multiple=True)
def group_add(group, node, extra, host_extra, group_extra):
    """ Add a set of nodes to a role.

    The GROUP argument specify the group which the nodes will be added.
    """
    # Preprocess node
    if all(':' in n for n in node):
        hosts = defaultdict(list)
        for n in node:
            name, list_nodes = n.split(':')
            hosts[name] += list_nodes.split(',')
        hosts = dict(hosts)
    elif all(':' not in n for n in node):
        hosts = [h for n in node for h in n.split(',')]
    else:
        raise ValueError('Multiple types for node option. Specify a host or not for all node options')

    # Preprocess extra
    extra_args = dict()
    for e in extra:
        if '=' not in e:
            raise ValueError(f"Invalid value for extra argument: `{e}`. "
                             f"Did you forgot '=' character?")
        extra_name, extra_value = e.split('=')[0], '='.join(e.split('=')[1:])
        if not extra_name:
            raise ValueError(f"Invalid extra key for value `{e}`. Key is empty")
        extra_args[extra_name] = extra_value

    # Preprocess group extra
    group_args = defaultdict(dict)
    for e in group_extra:
        if ':' not in e:
            raise ValueError(f"Invalid value for group extra argument: `{e}`. "
                             f"Did you forgot ':' character?")
        group_name, group_vals = e.split(':')
        if '=' not in group_vals:
            raise ValueError(f"Invalid value for group extra argument: `{e}`. "
                             f"Did you forgot '=' character?")
        key, val = group_vals.split('=')[0], '='.join(group_vals.split('=')[1:])
        if not key:
            raise ValueError(f"Invalid group extra key for value `{e}`. Key is empty")
        group_args[group_name].update({key: val})
    group_args = dict(group_args)

    # Preprocess host extra
    host_args = defaultdict(dict)
    for e in host_extra:
        if ':' not in e:
            raise ValueError(f"Invalid value for host extra argument: `{e}`. "
                             f"Did you forgot ':' character?")
        host_name, host_vals = e.split(':')
        if '=' not in host_vals:
            raise ValueError(f"Invalid value for host extra argument: `{e}`. "
                             f"Did you forgot '=' character?")
        key, val = host_vals.split('=')[0], '='.join(host_vals.split('=')[1:])
        if not key:
            raise ValueError(f"Invalid host extra key for value `{e}`. Key is empty")
        host_args[host_name].update({key: val})
    host_args = dict(host_args)

    group_module = GroupModule.get_module()
    group_module.add_group_to_nodes(group_name=group, group_hosts_map=hosts, extra_args=extra_args,
                                    group_vars=group_args, host_vars=host_args)
    return 0


@role.command('action')
@click.argument('group', nargs=1, type=str, required=True)
@click.option('-a', '--action', nargs=1, type=str, required=True, help="Name of the group's action to perform")
@click.option('-n', '--node', nargs=1, type=str, multiple=True,
              help='Nodes to be added. Can be a list of colon-separated nodes (<node>,<node>,...) or <group_host_name>:<node>,<node>')
@click.option('-e', '--extra', help='Extra arguments. Format <key>=<value>', multiple=True)
@click.option('-h', '--host-extra', help='Extra host arguments. Format <node_id>:<key>=<value>', multiple=True)
@click.option('-ge', '--group-extra', help='Extra group arguments. Format <group_name>:<key>=<value>', multiple=True)
def group_action(group, action, node, extra, host_extra, group_extra):
    """ Perform an group action at a set of nodes.

    The GROUP argument specify the group which the action will be performed.
    """

    # Preprocess node
    if not node:
        hosts = None
    elif all(':' in n for n in node):
        hosts = defaultdict(list)
        for n in node:
            name, list_nodes = n.split(':')
            hosts[name] += list_nodes.split(',')
        hosts = dict(hosts)
    elif all(':' not in n for n in node):
        hosts = [h for n in node for h in n.split(',')]
    else:
        raise ValueError('Multiple types for node option. Specify a host or not for all node options')

    # Preprocess extra
    extra_args = dict()
    for e in extra:
        if '=' not in e:
            raise ValueError(f"Invalid value for extra argument: `{e}`. "
                             f"Did you forgot '=' character?")
        extra_name, extra_value = e.split('=')[0], '='.join(e.split('=')[1:])
        if not extra_name:
            raise ValueError(f"Invalid extra key for value `{e}`. Key is empty")
        extra_args[extra_name] = extra_value

    # Preprocess group extra
    group_args = defaultdict(dict)
    for e in group_extra:
        if ':' not in e:
            raise ValueError(f"Invalid value for group extra argument: `{e}`. "
                             f"Did you forgot ':' character?")
        group_name, group_vals = e.split(':')
        if '=' not in group_vals:
            raise ValueError(f"Invalid value for group extra argument: `{e}`. "
                             f"Did you forgot '=' character?")
        key, val = group_vals.split('=')[0], '='.join(group_vals.split('=')[1:])
        if not key:
            raise ValueError(f"Invalid group extra key for value `{e}`. Key is empty")
        group_args[group_name].update({key: val})
    group_args = dict(group_args)

    # Preprocess host extra
    host_args = defaultdict(dict)
    for e in host_extra:
        if ':' not in e:
            raise ValueError(f"Invalid value for host extra argument: `{e}`. "
                             f"Did you forgot ':' character?")
        host_name, host_vals = e.split(':')
        if '=' not in host_vals:
            raise ValueError(f"Invalid value for host extra argument: `{e}`. "
                             f"Did you forgot '=' character?")
        key, val = host_vals.split('=')[0], '='.join(host_vals.split('=')[1:])
        if not key:
            raise ValueError(f"Invalid host extra key for value `{e}`. Key is empty")
        host_args[host_name].update({key: val})
    host_args = dict(host_args)

    group_module = GroupModule.get_module()
    group_module.execute_group_action(group_name=group, action_name=action, node_ids=hosts, extra_args=extra_args,
                                      group_vars=group_args, host_vars=host_args)
    return 0


@role.command('list')
@click.argument('group', nargs=-1, type=str)
@click.option('-d', '--detailed', help='Show detailed cluster information', is_flag=True, default=False, show_default=True)
@click.option('-i', '--indent', default=4, show_default=True, nargs=1, type=int, help="Indentation level")
@click.option('-q', '--quiet', default=False, is_flag=True, show_default=True, help="Show only template ids")
def group_list(group, detailed, indent, quiet):
    """Print roles in role path.

    The ROLE argument specify the groups which the action will be performed.
    """

    if quiet and detailed:
        raise ValueError(f"Options `detailed` and `quiet` are mutually exclusive")

    group_module = GroupModule.get_module()
    groups = group_module.list_groups()
    # Perform filter
    groups = groups if not group else {g: groups[g] for g in group}

    for name in sorted(groups.keys()):
        group_info = groups[name]
        if quiet:
            print(name)
            continue

        if detailed:
            print(f"{'-' * 20} GROUP: `{name}` {'-' * 20}")
            group_dict = asdict(group_info)
            print(yaml.dump(group_dict, sort_keys=True, indent=indent))
            print(f"{'-' * 70}")
        else:
            print(f"name: `{name}`")
            if group_info.actions:
                print(f"  actions: {', '.join(sorted(list(group_info.actions.keys())))}")
            if group_info.hosts:
                print(f"  hosts: {', '.join(sorted(group_info.hosts))}")
            print()

    if not quiet:
        print(f"Listed {len(groups)} groups")
    return 0


def group_remove():
    pass
