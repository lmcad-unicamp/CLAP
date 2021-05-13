import yaml
import os
import click

from typing import List, Dict
from collections import defaultdict
from paramiko import SSHException

from common.node import NodeDescriptor
from common.utils import path_extend, float_time_to_string, get_logger
from modules.node import NodeDefaults, NodeModule
from app.module import clap_command

logger = get_logger(__name__)

node_defaults = NodeDefaults()


class TagError(Exception):
    pass


class InvalidNode(Exception):
    pass


def get_tags(tags: List[str]):
    if not tags:
        return None

    return {(tag if '=' not in tag else tag.split('=')[0]): (None if '=' not in tag else tag.split('=')[1])
            for tag in tags}


def get_nodes_filter(node_module: NodeModule, node_ids: List[str] = None, tags: Dict[str, str] = None) -> List[NodeDescriptor]:
    node_ids = node_ids or []
    tags = tags or {}
    nodes = dict()
    all_nodes = {node.node_id: node for node in node_module.get_all_nodes()}

    if not node_ids and not tags:
        return list(all_nodes.values())

    if '*' in node_ids:
        nodes = all_nodes
        node_ids.remove('*')

    for node_id in node_ids:
        try:
            nodes[node_id] = all_nodes[node_id]
        except KeyError:
            raise InvalidNode(node_id)

    for key, value in tags.items():
        nodes.update({node_id: all_nodes[node_id] for node_id, status in node_module.node_has_tag(
            key, value, list(all_nodes.keys())).items() if status})

    return list(nodes.values())


@clap_command
@click.group(help='Control and manage nodes')
@click.option('-p', '--platform-db', default=node_defaults.node_repository_path,
              help='Platform database to be used, where nodes will be written', show_default=True)
def node(platform_db):
    node_defaults.node_repository_path = platform_db


@node.command('start')
@click.argument('instance', nargs=-1, type=str)
@click.option('-st', '--start-timeout', default=600, help='Timeout to start nodes', show_default=True)
@click.option('-cr', '--connection-retries', default=15, help='Number of SSH connection retries to check if node is '
                                                              'alive', show_default=True)
@click.option('-rt', '--retry-timeout', default=30, help='Delay time to try another connection to nodes when another '
                                                         'have already failed', show_default=True)
@click.option('-t', '--terminate_not_alive', default=False, help='Terminate nodes if no SSH connection were possible',
              show_default=True, is_flag=True)
def node_start(instance, start_timeout, connection_retries, retry_timeout, terminate_not_alive):
    """ Control and manage nodes.

    Start nodes based on an instance template: Instances to start with format: <instance_config>:<num>,
    where instance_config is the name of instance configuration template (in instances file) and num is the
    quantity of instances to start. If `num` is not provided, is 1 by default')
    """
    node_module = NodeModule.get_module()
    instances_to_start = dict()
    for i in instance:
        itype = i.split(':')[0]
        value = int(i.split(':')[1]) if ':' in i else 1
        if value < 1:
            raise ValueError(f"Instances number must be larger than 0. Error in `{i}`")
        instances_to_start[itype] = value

    node_ids = node_module.start_nodes_by_instance_config_id(
        instances_to_start, start_timeout=start_timeout, connection_retries=connection_retries,
        retry_timeout=retry_timeout, terminate_not_alive=terminate_not_alive)

    if not node_ids:
        print("No nodes created")
        return 1

    print(f"Created {len(node_ids)} nodes:")
    for node in node_module.get_nodes_by_id(node_ids):
        print(node)
    return 0


@node.command('list')
@click.argument('node_id', nargs=-1)
@click.option('-t', '--tags', default=None, type=str, multiple=True,
              help='Filter nodes by tags. There are two formats: <key> or <key>=<val>')
@click.option('-d', '--detailed', help='Show detailed node information. 2x to full information including in-use configuration',
              default=0, show_default=True, count=True)
@click.option('-i', '--indent', default=4, show_default=True, nargs=1, type=int, help="Indentation level")
@click.option('-q', '--quiet', default=False, is_flag=True, show_default=True, help="Show only node ids")
def node_list(node_id, tags, detailed, indent, quiet):
    """ Print nodes from a node repository.

    The NODE_ID argument is a list of strings (optional) and can filter nodes to print by their node ids.
    """
    if quiet and detailed > 0:
        raise ValueError(f"Options `detailed` and `quiet` are mutually exclusive")

    node_module = NodeModule.get_module()
    tags = get_tags(tags)
    nodes = get_nodes_filter(node_module, list(node_id), tags)

    for node in sorted(nodes, key=lambda x: x.node_id):
        if quiet:
            print(node.node_id)
            continue
        elif detailed > 0:
            print(f"{'-' * 20} NODE: `{node.node_id}` {'-' * 20}")
            node.creation_time = float_time_to_string(node.creation_time)
            node.update_time = float_time_to_string(node.update_time)
            to_print = node.to_dict()
            if detailed == 1:
                to_print['configuration'] = to_print['configuration']['instance']['instance_config_id']

            print(f"{yaml.dump(to_print, sort_keys=True, indent=indent)}")
            print('-' * 70)
        else:
            print(node)
    if not quiet:
        print(f"Listed {len(nodes)} nodes")
    return 0


@node.command('add-tag')
@click.argument('node_id', nargs=-1, required=True)
@click.option('-t', '--tags', required=True, type=str, multiple=True, help='Tags to add. Format: <key>=<val>')
def node_add_tag(node_id, tags):
    """ Add tags to a set of nodes.

    The NODE_ID argument is a list of strings (optional) and can filter nodes to add tags by their node ids
    """
    node_module = NodeModule.get_module()
    final_tags = dict()
    for t in tags:
        try:
            tag_name, tag_value = t.split('=')[0], '='.join(t.split('=')[1:])
            if not tag_name or not tag_value:
                raise ValueError
            final_tags[tag_name] = tag_value
        except ValueError:
            raise TagError(f'Tag `{t}` have an invalid format. Did you put `=`?')

    nodes = [node.node_id for node in node_module.get_all_nodes()] if '*' in node_id else node_id
    ret = node_module.add_tag_to_nodes(tags=final_tags, node_ids=nodes)
    print(f"Tags `{final_tags}` were added to {len(ret)} nodes")
    return 0


@node.command('remove-tag')
@click.argument('node_id', nargs=-1, required=True)
@click.option('-t', '--tags', default=None, type=str, multiple=True, required=True,
              help='Tags to remove. There are two formats: <key> or <key>=<val>')
def node_remove_tags(node_id, tags):
    """ Remove tags from a set of nodes.

    The NODE_ID argument is a list of strings (optional) and can filter nodes to remove tags by their node ids
    """
    node_module = NodeModule.get_module()
    tags = get_tags(tags)
    nodes = [node.node_id for node in get_nodes_filter(node_module, list(node_id), tags)]
    ret = node_module.remove_tag_from_nodes(tags=tags, node_ids=nodes)
    print(f"Removed tags from {len(ret)} nodes")
    return 0


@node.command('alive')
@click.argument('node_id', nargs=-1)
              # help='Nodes to be checked. If not provided, check all nodes in repository')
@click.option('-t', '--tags', default=None, type=str, multiple=True,
              help='Filter nodes by tags. There are two formats: <key> or <key>=<val>')
@click.option('-cr', '--connection-retries', default=5,
              help='Number of SSH connection retries to check if node is alive', show_default=True)
@click.option('-rt', '--retry-timeout', default=30,
              help='Delay time to try another connection to nodes when another have already failed', show_default=True)
def node_alive(node_id, tags, connection_retries, retry_timeout):
    """ Check if nodes are alive (if an successful SSH connection can be established).

    The NODE_ID argument is a list of strings (optional) and can filter nodes to check by aliveness by their node ids
    """
    node_module = NodeModule.get_module()
    tags = get_tags(tags)
    nodes = [node.node_id for node in get_nodes_filter(node_module, node_ids=list(node_id), tags=tags)]
    if not nodes:
        raise Exception("No nodes provided")

    alive_nodes = node_module.is_alive(nodes, retries=connection_retries, wait_timeout=retry_timeout)
    for node_id, status in alive_nodes.items():
        print(f"{node_id}: {'alive' if status else 'not alive'}")

    print(f"Checked {len(alive_nodes)} nodes")
    return 0


@node.command('stop')
@click.argument('node_id', nargs=-1)
@click.option('-t', '--tags', default=None, type=str, multiple=True,
              help='Filter nodes by tags. There are two formats: <key> or <key>=<val>')
@click.option('-f', '--force', default=True, help='Remove nodes from repository even if fails', show_default=True,
              is_flag=True)
def node_stop(node_id, tags, force):
    """ Stop a node (terminating it) and remove it from node repository.

    The NODE_ID argument is a list of strings (optional) and can filter nodes to stop by their node ids
    """
    if not node_id and not tags:
        raise Exception("No nodes informed")

    node_module = NodeModule.get_module()
    tags = get_tags(tags)
    nodes = [node.node_id for node in get_nodes_filter(node_module, node_ids=list(node_id), tags=tags)]
    if not nodes:
        raise Exception("No nodes informed")

    stopped_nodes = node_module.stop_nodes(node_ids=nodes, force=force)
    for node_id in stopped_nodes:
        print(f"{node_id} stopped")
    print(f"Stopped {len(stopped_nodes)} nodes")
    return 0


@node.command('pause')
@click.argument('node_id', nargs=-1)
@click.option('-t', '--tags', default=None, type=str, multiple=True,
              help='Filter nodes by tags. There are two formats: <key> or <key>=<val>')
def node_pause(node_id, tags):
    """ Pause nodes (if possible).

    The NODE_ID argument is a list of strings (optional) and can filter nodes to pause by their node ids
    """
    if not node_id and not tags:
        raise Exception("No nodes informed")

    node_module = NodeModule.get_module()
    tags = get_tags(tags)
    nodes = [node.node_id for node in get_nodes_filter(node_module, node_ids=list(node_id), tags=tags)]
    if not nodes:
        raise Exception("No nodes informed")

    paused_nodes = node_module.pause_nodes(node_ids=nodes)
    for node_id in paused_nodes:
        print(f"{node_id} paused")
    print(f"Paused {len(paused_nodes)} nodes")
    return 0

@node.command('resume')
@click.argument('node_id', nargs=-1)
@click.option('-t', '--tags', default=None, type=str, multiple=True,
              help='Filter nodes by tags. There are two formats: <key> or <key>=<val>')
@click.option('-st', '--resume-timeout', default=600, help='Timeout to resume nodes', show_default=True)
@click.option('-cr', '--connection-retries', default=15,
              help='Number of SSH connection retries to check if node is alive', show_default=True)
@click.option('-rt', '--retry-timeout', default=30,
              help='Delay time to try another connection to nodes when another have already failed', show_default=True)
def node_resume(node_id, tags, resume_timeout, connection_retries, retry_timeout):
    """ Resume nodes (if possible).

    The NODE_ID argument is a list of strings (optional) and can filter nodes to resume by their node ids
    """
    if not node_id and not tags:
        raise Exception("No nodes informed")

    node_module = NodeModule.get_module()
    tags = get_tags(tags)
    nodes = [node.node_id for node in get_nodes_filter(node_module, node_ids=list(node_id), tags=tags)]
    if not nodes:
        raise Exception("No nodes informed")

    resumed_nodes = node_module.resume_nodes(node_ids=nodes, resume_timeout=resume_timeout,
                                             connection_retries=connection_retries,
                                             connection_retry_timeout=retry_timeout)
    for node_id in sorted(resumed_nodes):
        print(f"{node_id} resumed")
    print(f"Resumed {len(resumed_nodes)} nodes")
    return 0


@node.command('playbook')
@click.argument('node_id', nargs=-1)
@click.option('-p', '--playbook', required=True, type=str, help='Path of the playbook to be executed')
@click.option('-t', '--tags', default=None, type=str, multiple=True,
              help='Filter nodes by tags. There are two formats: <key> or <key>=<val>')
@click.option('-e', '--extra', default=None, type=str, multiple=True,
              help='Extra variables to be passed. Format: <key>=<val>', show_default=True)
@click.option('-h', '--host', default=None, type=str, multiple=True,
              help='Host variables to be passed. Format: <node_id>:<key>=<val>', show_default=True)
def node_playbook(node_id, playbook, tags, extra, host):
    """ Execute an Ansible playbook in a set of nodes.

    The NODE_ID argument is a list of strings (optional) and can filter nodes to execute the playbook by their node ids
    """
    if not node_id and not tags:
        logger.error("No nodes to execute the playbook")
        return 1

    playbook = path_extend(playbook)
    if not os.path.isfile(playbook):
        raise ValueError(f"Invalid playbook at `{playbook}`")

    node_module = NodeModule.get_module()
    tags = get_tags(tags)
    nodes = [node.node_id for node in get_nodes_filter(node_module, node_ids=list(node_id), tags=tags)]

    if not nodes:
        raise Exception("No nodes to execute the playbook")

    extra_args = dict()
    for e in extra:
        if '=' not in e:
            raise ValueError(f"Invalid value for extra argument: `{e}`. "
                             f"Did you forgot '=' character?")
        extra_name, extra_value = e.split('=')[0], '='.join(e.split('=')[1:])
        extra_args[extra_name] = extra_value

    host_args = defaultdict(dict)
    for h in host:
        if ':' not in h:
            raise ValueError(f"Invalid value for host argument: `{h}`. "
                             f"Did you forgot ':' character?")
        node_id, host_extra_args = h.split(':')[0], ':'.join(h.split(':')[1:])
        extra_name, extra_value = host_extra_args.split('=')[0], '='.join(host_extra_args.split('=')[1:])
        host_args[node_id].update({extra_name: extra_value})

    host_args = dict(host_args)
    ret_val = node_module.execute_playbook_in_nodes(playbook, group_hosts_map=nodes, extra_args=extra_args,
                                                    host_vars=host_args, quiet=False)

    if not ret_val.ok:
        logger.error(f"Playbook `{playbook}` did not executed successfully...")
        return 1

    print(f"{'-' * 20} Execution summary {'-' * 20}")
    for node_id in sorted(list(ret_val.hosts.keys())):
        result = ret_val.hosts[node_id]
        print(f"{node_id}: {'ok' if result else 'not ok'}")

    print(f"Playbook at `{playbook}` were executed in {len(ret_val.hosts)} nodes")
    return 0


@node.command('execute', help='Execute a shell command in nodes (via SSH)')
@click.argument('node_id', nargs=-1)
@click.option('-t', '--tags', default=None, type=str, multiple=True,
              help='Filter nodes by tags. There are two formats: <key> or <key>=<val>')
@click.option('-cmd', '--command', required=True, nargs=1, type=str, help='Shell Command to be executed in nodes')
@click.option('--timeout', default=0, show_default=True, nargs=1, type=int,
              help='Timeout to execute command in host (0 to no timeout)')
@click.option('-a', '--additional', default=None, multiple=True, nargs=1, type=str,
              help='Additional arguments to connection. Format: <key>=<val>')
def node_execute(node_id, tags, command, additional, timeout):
    """ Execute a shell command in a set of nodes.

     The NODE_ID argument is a list of strings (optional) and can filter nodes to execute the shell command by their node ids
     """
    if not node_id and not tags:
        raise Exception("No nodes informed")

    node_module = NodeModule.get_module()
    tags = get_tags(tags)
    nodes = [node.node_id for node in get_nodes_filter(node_module, node_ids=list(node_id), tags=tags)]

    if not nodes:
        raise Exception("No nodes informed")

    extra_args = dict()

    if timeout < 0:
        raise ValueError(f"Timeout must be larger than zero")
    timeout = timeout if timeout > 0 else None

    for e in additional:
        if '=' not in e:
            raise ValueError(f"Invalid value for extra argument: `{e}`. "
                             f"Did you forgot '=' character?")
        extra_name, extra_value = e.split('=')[0], '='.join(e.split('=')[1:])
        extra_args[extra_name] = extra_value

    executions = node_module.execute_command_in_nodes(command=command, node_ids=nodes, execution_timeout=timeout)

    for node_id in sorted(list(executions.keys())):
        result = executions[node_id]
        if not result:
            print(f"Error executing command in node `{node_id}`")
            continue
        print(f"{'-' * 20} STDOUT: `{node_id}` {'-' * 20}")
        print(''.join(result.stdout_lines))
        print(f"\n{'-' * 20} STDERR: `{node_id}` {'-' * 20}")
        print(''.join(result.stderr_lines))
        print(f"\n{'-' * 70}")

    return 0


@node.command('connect', help='Get a SSH connection shell to a node')
@click.argument('node_id', nargs=1)
def node_connect(node_id):
    """ Obtain an interactive shell to a node.

     The NODE_ID argument is the id of the node to obtain a SSH shell to
     """
    node_module = NodeModule.get_module()
    node_module.connect_to_node(node_id)
    return 0


@node.command('list-templates')
@click.argument('template', nargs=-1)
@click.option('-d', '--detailed', default=False, show_default=True, is_flag=True,
              help='Show only instance template names')
@click.option('-i', '--indent', default=4, show_default=True, nargs=1, type=int, help="Indentation level")
@click.option('-q', '--quiet', default=False, show_default=True, is_flag=True, help='Show only instance template names')
def list_instance_templates(template, detailed, indent, quiet):
    """ List instance templates (used to start nodes) at CLAP's configs path.

    The TEMPLATE argument is an optional list of templates id to filter templates to print.
    """
    if quiet and detailed:
        raise ValueError(f"Options `detailed` and `quiet` are mutually exclusive")

    node_module = NodeModule.get_module()
    templates = node_module.get_all_instance_descriptors() if not template else {
        i: node_module.get_instance_descriptor(i) for i in template}
    for name, descriptor in templates.items():
        if quiet:
            print(name)
            continue
        if not detailed:
            print(f"name: `{name}`")
            print(f"    provider config id:` {descriptor.provider.provider_config_id}`")
            print(f"    login config id: `{descriptor.login.login_config_id}`")
        else:
            print(f"{'-' * 20} INSTANCE: `{name}` {'-' * 20}")
            print(f"{yaml.dump(descriptor.to_dict(), sort_keys=True, indent=indent)}")
            print(f"{'-' * 70}")
        print()

    if not quiet:
        print(f"Listed {len(templates)} instance templates")
    return 0
