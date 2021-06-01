import json
import os
import yaml
import click
from collections import defaultdict
from dataclasses import asdict
from typing import List
from clap.configs import ConfigurationDatabase
from clap.executor import ShellInvoker, SSHCommandExecutor, AnsiblePlaybookExecutor
from clap.node_manager import NodeManager, NodeRepositoryController
from clap.repository import RepositoryFactory
from clap.utils import path_extend, float_time_to_string, get_logger, \
    Singleton, defaultdict_to_dict, str_at_middle
from providers.provider_ansible_aws import AnsibleAWSProvider
from app.cli.cliapp import clap_command, Defaults

logger = get_logger(__name__)


class NodeDefaults(metaclass=Singleton):
    def __init__(self):
        self.base_defaults = Defaults()
        self.repository_type = 'sqlite'
        self.node_repository_path = path_extend(
            self.base_defaults.storage_path, 'nodes.db')
        self.providers_path = path_extend(
            self.base_defaults.configs_path, 'providers.yaml')
        self.logins_path = path_extend(
            self.base_defaults.configs_path, 'logins.yaml')
        self.instances_path = path_extend(
            self.base_defaults.configs_path, 'instances.yaml')
        self.templates_path = path_extend(
            os.path.dirname(os.path.abspath(__file__)), 'templates')


node_defaults = NodeDefaults()


def get_node_manager() -> NodeManager:
    repository = RepositoryFactory().get_repository(
        node_defaults.repository_type, node_defaults.node_repository_path,
        verbosity=node_defaults.base_defaults.verbosity)
    node_repository = NodeRepositoryController(repository)

    providers_map = dict()

    providers_map['aws'] = AnsibleAWSProvider(
        node_defaults.base_defaults.private_path,
        node_defaults.base_defaults.verbosity
    )

    node_manager = NodeManager(
        node_repository, providers_map, node_defaults.base_defaults.private_path)
    return node_manager


def get_config_db() -> ConfigurationDatabase:
    return ConfigurationDatabase(
        node_defaults.providers_path, node_defaults.logins_path,
        node_defaults.instances_path, discard_invalids=True
    )


def get_nodes(node_manager: NodeManager, node_ids: List[str], tags: List[str]) -> \
        List[str]:
    nodes = set([n.node_id for n in node_manager.get_nodes_by_id(node_ids)])
    for tag in tags:
        if '=' not in tag:
            for n in node_manager.get_nodes_with_tag(tag):
                nodes.add(n.node_id)
        else:
            for n in node_manager.get_nodes_with_tag_value(
                    tag.split('=')[0], tag.split('=')[1]):
                nodes.add(n.node_id)
    return list(nodes)


@clap_command
@click.group(help='Control and manage nodes')
@click.option('-r', '--repository', default=node_defaults.node_repository_path,
              help='Node database where nodes will be written', show_default=True)
def node(repository):
    node_defaults.node_repository_path = repository


@node.command('start')
@click.argument('instance', nargs=-1, type=str)
@click.option('-st', '--start-timeout', default=600, show_default=True,
              help='Timeout to start nodes')
@click.option('-cr', '--connection-tries', default=15, show_default=True,
              help="Number of SSH connection tries to check if node is alive. "
                   "If the value is set to zero, only the node's information is "
                   "updated and no login attempts(via SSH) is performed.")
@click.option('-rt', '--retry-delay', default=30, show_default=True,
              help='Time between an unsuccessful connection and another')
@click.option('-t', '--terminate_not_alive', default=False, show_default=True,
              is_flag=True,
              help='Terminate nodes if no SSH connection were possible. '
                   'Connection-tries parameter must be higher than 0')
def node_start(instance, start_timeout, connection_tries, retry_delay,
               terminate_not_alive):
    """ Control and manage nodes.

    Start nodes based on an instance template. Instances can start with format:
    <instance_config>:<num>, where <instance_config> is the name of instance
    configuration template (in instances file) and <num> is the quantity of
    instances to start. If `num` is not provided, it is set to 1 by default')
    """
    if connection_tries < 0:
        raise ValueError("connection_tries parameter must be higher than 0")
    if retry_delay < 0:
        raise ValueError("retry_delay parameter must be higher than 0")
    if terminate_not_alive and connection_tries == 0:
        raise ValueError("terminate_not_alive parameter must have "
                         "connection_tries parameter set higher than 0")

    node_manager = get_node_manager()
    configuration_db = get_config_db()
    instances_to_start = list()
    for i in instance:
        itype = i.split(':')[0]
        qtde = int(i.split(':')[1]) if ':' in i else 1
        if qtde < 1:
            raise ValueError(f"Instances number must be higher than 0. "
                             f"Error in argument: '{i}'")
        iinfo = configuration_db.instance_descriptors.get(itype, None)
        if iinfo is None:
            raise ValueError(f"Invalid configuration named {itype}. "
                             f"Error in argument: '{i}'")
        instances_to_start.append((iinfo, qtde))

    started_nodes = node_manager.start_nodes(
        instances_to_start, start_timeout=start_timeout, max_workers=1)

    logger.info(f'{len(started_nodes)} nodes were started: '
                f'{",".join(sorted(started_nodes))}')

    if connection_tries > 0:
        logger.info(f"Checking if nodes {', '.join(started_nodes)} are alive")
        alive_nodes = node_manager.is_alive(
            started_nodes, retries=connection_tries, wait_timeout=retry_delay,
        )
        if terminate_not_alive:
            nodes_to_stop = [nid for nid, status in alive_nodes.items() if not status]
            if nodes_to_stop:
                logger.error(f"Nodes {', '.join(sorted(nodes_to_stop))} are "
                             f"being stopped. It was unable to connect to them")
                node_manager.stop_nodes(nodes_to_stop, max_workers=1)
                started_nodes = [node for node in started_nodes
                                 if node not in terminate_not_alive]
        print(f'{len(started_nodes)} nodes are alive: '
              f'{",".join(sorted(started_nodes))}')

    print("Started nodes:")
    for node in node_manager.get_nodes_by_id(started_nodes):
        print(f"* Node: {node.node_id}, type: {node.type}, "
              f"nickname: {node.nickname}, status: {node.status}, "
              f"ip: {node.ip}, tags: {node.tags}, "
              f"creation at: {float_time_to_string(node.creation_time)}")

    print(f"Started {len(started_nodes)} nodes")

    return 0


@node.command('list')
@click.argument('node_id', nargs=-1)
@click.option('-t', '--tags', default=None, type=str, multiple=True,
              help='Filter nodes by tags. There are two formats: <key> or <key>=<val>')
@click.option('-d', '--detailed', default=0, show_default=True, count=True,
              help='Show detailed node information')
@click.option('-i', '--indent', default=4, show_default=True, nargs=1, type=int,
              help="Indentation level")
@click.option('-q', '--quiet', default=False, is_flag=True, show_default=True,
              help="Show only node ids")
def node_list(node_id, tags, detailed, indent, quiet):
    """ Print nodes from a node repository.

    The NODE_ID argument is a list of strings (optional) and can filter nodes
    to print by their node ids.
    """
    if quiet and detailed > 0:
        raise ValueError(f"Options `detailed` and `quiet` are mutually exclusive")

    node_manager = get_node_manager()

    if not tags and not node_id:
        nodes = node_manager.get_all_nodes()
    else:
        node_ids = get_nodes(node_manager, node_id, tags)
        nodes = node_manager.get_nodes_by_id(node_ids)

    for node in nodes:
        if quiet:
            print(node.node_id)
            continue
        if not detailed:
            print(f"* Node: {node.node_id}, "
                  f"config: {node.configuration.instance.instance_config_id}, "
                  f"nickname: {node.nickname}, status: {node.status}, "
                  f"ip: {node.ip}, tags: {node.tags}, roles: {node.roles}, "
                  f"creation at: {float_time_to_string(node.creation_time)}")
        else:
            print(json.dumps(asdict(node), sort_keys=True, indent=indent))

    if not quiet:
        print(f"Listed {len(nodes)} nodes")

    return 0


@node.command('stop')
@click.argument('node_id', nargs=-1)
@click.option('-t', '--tags', default=None, type=str, multiple=True,
              help='Filter nodes by tags. There are two formats: <key> or <key>=<val>')
@click.option('-f', '--force', default=True, is_flag=True, show_default=True,
              help='Remove nodes from repository even if stop operation fails')
def node_stop(node_id, tags, force):
    """ Stop a node (terminating it) and remove it from node repository.

    The NODE_ID argument is a list of strings (optional) and can filter nodes to
    stop by their node ids
    """
    if not node_id and not tags:
        print('Stopped 0 nodes')
        return 0

    node_manager = get_node_manager()
    nodes = get_nodes(node_manager, node_id, tags)

    if not nodes:
        raise ValueError("No nodes match the criteria")

    stopped_nodes = node_manager.stop_nodes(
        nodes, max_workers=1, remove_nodes=force)

    for node_id in stopped_nodes:
        print(f"Stopped: {node_id}")
    print(f"Stopped {len(stopped_nodes)} nodes")
    return 0


@node.command('alive')
@click.argument('node_id', nargs=-1)
@click.option('-t', '--tags', default=None, type=str, multiple=True,
              help='Filter nodes by tags. There are two formats: <key> or <key>=<val>')
@click.option('-cr', '--connection-tries', default=15, show_default=True,
              help="Number of SSH connection tries to check if node is alive. "
                   "If the value is set to zero, only the node's information is "
                   "updated and no login attempts(via SSH) is performed.")
@click.option('-rt', '--retry-delay', default=30, show_default=True,
              help='Time between an unsuccessful connection and another')
def node_alive(node_id, tags, connection_tries, retry_delay):
    """ Check if nodes are alive (a successful SSH connection can be established).

    The NODE_ID argument is a list of strings (optional) and can filter nodes
    to check by aliveness by their node ids.
    """
    node_manager = get_node_manager()

    if not tags and not node_id:
        nodes = node_manager.get_all_nodes()
    else:
        node_ids = get_nodes(node_manager, node_id, tags)
        nodes = node_manager.get_nodes_by_id(node_ids)

    if not nodes:
        print(f"Checked 0 nodes")
        return 0

    alive_nodes = node_manager.is_alive(
        [n.node_id for n in nodes], retries=connection_tries,
        wait_timeout=retry_delay)
    for node_id, status in alive_nodes.items():
        print(f"{node_id}: {'alive' if status else 'not alive'}")

    print(f"Checked {len(alive_nodes)} nodes")
    return 0


@node.command('resume')
@click.argument('node_id', nargs=-1)
@click.option('-t', '--tags', default=None, type=str, multiple=True,
              help='Filter nodes by tags. There are two formats: <key> or <key>=<val>')
@click.option('-st', '--start-timeout', default=600, show_default=True,
              help='Timeout to resume nodes')
@click.option('-cr', '--connection-tries', default=15, show_default=True,
              help="Number of SSH connection tries to check if node is alive. "
                   "If the value is set to zero, only the node's information is "
                   "updated and no login attempts(via SSH) is performed.")
@click.option('-rt', '--retry-delay', default=30, show_default=True,
              help='Time between an unsuccessful connection and another')
def node_resume(node_id, tags, start_timeout, connection_tries, retry_delay):
    """ Resume nodes (if possible).

    The NODE_ID argument is a list of strings (optional) and can filter nodes to
    resume by their node ids
    """
    node_manager = get_node_manager()

    if not tags and not node_id:
        nodes = node_manager.get_all_nodes()
    else:
        node_ids = get_nodes(node_manager, node_id, tags)
        nodes = node_manager.get_nodes_by_id(node_ids)

    if not nodes:
        print(f"Resumed 0 nodes")
        return 0

    alive_nodes = node_manager.resume_nodes(
        [n.node_id for n in nodes], timeout=start_timeout,
        connection_retries=connection_tries,  retry_timeout=retry_delay)
    for node_id in alive_nodes:
        print(f"Resumed: {node_id}")

    print(f"Resumed {len(alive_nodes)} nodes")
    return 0


@node.command('pause')
@click.argument('node_id', nargs=-1)
@click.option('-t', '--tags', default=None, type=str, multiple=True,
              help='Filter nodes by tags. There are two formats: <key> or <key>=<val>')
def node_pause(node_id, tags):
    """ Pause nodes (if possible).

    The NODE_ID argument is a list of strings (optional) and can filter nodes to
    pause by their node ids
    """
    node_manager = get_node_manager()

    if not tags and not node_id:
        nodes = node_manager.get_all_nodes()
    else:
        node_ids = get_nodes(node_manager, node_id, tags)
        nodes = node_manager.get_nodes_by_id(node_ids)

    if not nodes:
        print("Paused 0 nodes")
        return 0

    paused_nodes = node_manager.pause_nodes([n.node_id for n in nodes])
    for node_id in paused_nodes:
        print(f"Paused: {node_id}")
    print(f"Paused {len(paused_nodes)} nodes")
    return 0


@node.command('connect', help='Get a SSH connection shell to a node')
@click.argument('node_id', nargs=1)
def node_connect(node_id):
    """ Obtain an interactive shell to a node.

     The NODE_ID argument is the id of the node to obtain a SSH shell to
     """
    node_manager = get_node_manager()
    n = node_manager.get_nodes_by_id([node_id])[0]
    ShellInvoker(n, node_defaults.base_defaults.private_path).run()
    return 0


@node.command('add-tag')
@click.argument('node_id', nargs=-1, required=True)
@click.option('-t', '--tags', required=True, type=str, multiple=True,
              help='Tags to add. Format: <key>=<val>')
def node_add_tag(node_id, tags):
    """ Add tags to a set of nodes.

    The NODE_ID argument is a list of node_ids to add tags.
    """
    node_manager = get_node_manager()
    final_tags = dict()
    for t in tags:
        tag_name, tag_value = t.split('=')[0], '='.join(t.split('=')[1:])
        if not tag_name or not tag_value:
            raise ValueError(f'Tag "{t}" have an invalid format. Did you put `=`?')
        final_tags[tag_name] = tag_value

    nodes = [n.node_id for n in node_manager.get_all_nodes()] if '*' in node_id else node_id
    addeds = node_manager.add_tags(nodes, final_tags)
    print(f"Tags `{final_tags}` were added to {len(addeds)} nodes")
    return 0


@node.command('remove-tag')
@click.argument('node_id', nargs=-1, required=True)
@click.option('-t', '--tags', default=None, type=str, multiple=True, required=True,
              help='Tags to remove. Format: <key>')
def node_remove_tags(node_id, tags):
    """ Remove tags from a set of nodes.

    The NODE_ID argument is a list of node_ids to remove tags.
    """
    node_manager = get_node_manager()
    removeds = node_manager.remove_tags(node_id, tags)
    print(f"Removed tags from {len(removeds)} nodes")
    return 0


@node.command('execute', help='Execute a shell command in nodes (via SSH)')
@click.argument('node_id', nargs=-1)
@click.option('-t', '--tags', default=None, type=str, multiple=True,
              help='Filter nodes by tags. There are two formats: <key> or <key>=<val>')
@click.option('-cmd', '--command', required=True, nargs=1, type=str,
              help='Shell Command to be executed in nodes')
@click.option('--timeout', default=0, show_default=True, nargs=1, type=int,
              help='Timeout to execute command in host (0 to no timeout)')
@click.option('-a', '--additional', default=None, multiple=True, nargs=1, type=str,
              help='Additional arguments to connection. Format: <key>=<val>')
def node_execute(node_id, tags, command, additional, timeout):
    """ Execute a shell command in a set of nodes.

     The NODE_ID argument is a list of strings (optional) and can filter nodes to execute the shell command by their node ids
     """
    node_manager = get_node_manager()

    if not tags and not node_id:
        nodes = node_manager.get_all_nodes()
    else:
        node_ids = get_nodes(node_manager, node_id, tags)
        nodes = node_manager.get_nodes_by_id(node_ids)

    if not nodes:
        print("No nodes informed")
        return 0

    extra_args = dict()
    if timeout < 0:
        raise ValueError(f"Timeout must be larger than zero")
    timeout = timeout if timeout > 0 else None

    for e in additional:
        if '=' not in e:
            raise ValueError(f"Invalid value for extra argument: '{e}'. "
                             f"Did you forgot '=' character?")
        extra_name, extra_value = e.split('=')[0], '='.join(e.split('=')[1:])
        extra_args[extra_name] = extra_value

    e = SSHCommandExecutor(command, nodes, node_defaults.base_defaults.private_path,
                           connection_timeout=timeout)

    results = e.run()

    for node_id in sorted(list(results.keys())):
        result = results[node_id]
        if not result.ok:
            print(f"{node_id[:8]}: Error executing command in node. {result.error}")
            continue
        print(str_at_middle(node_id, 80, '-'))
        print(f'return code {node_id[:8]}: {result.ret_code}')
        print(f'stdout {node_id[:8]}: '.join(result.stdout_lines))
        print(f'stderr {node_id[:8]}: '.join(result.stderr_lines))

    return 0


@node.command('list-templates')
@click.argument('template', nargs=-1)
@click.option('-d', '--detailed', default=False, show_default=True, is_flag=True,
              help='Show detailed template information')
@click.option('-i', '--indent', default=4, show_default=True, nargs=1, type=int,
              help="Indentation level")
@click.option('-q', '--quiet', default=False, show_default=True, is_flag=True,
              help='Show only instance template names')
def list_instance_templates(template, detailed, indent, quiet):
    """ List instance templates (used to start nodes) at CLAP's configs path.

    The TEMPLATE argument is an optional list of templates id to filter
    templates to print.
    """
    if quiet and detailed:
        raise ValueError(f"Options `detailed` and `quiet` are mutually exclusive")

    config_db = get_config_db()

    if template:
        templates = {t: config_db.instance_descriptors[t] for t in template}
    else:
        templates = config_db.instance_descriptors

    for name, descriptor in templates.items():
        if quiet:
            print(name)
            continue
        if not detailed:
            print(f"* name: {name}")
            print(f"    provider config id:` {descriptor.provider.provider_config_id}`")
            print(f"    login config id: `{descriptor.login.login_config_id}`")
        else:
            print(f"{'-' * 20} INSTANCE CONFIG: `{name}` {'-' * 20}")
            print(f"{yaml.dump(asdict(descriptor), sort_keys=True, indent=indent)}")
            print(f"{'-' * 80}")
        print()

    if not quiet:
        print(f"Listed {len(config_db.instance_descriptors)} instance configs")
    return 0


@node.command('playbook')
@click.argument('node_id', nargs=-1)
@click.option('-p', '--playbook', required=True, type=str,
              help='Path of the playbook to be executed')
@click.option('-t', '--tags', default=None, type=str, multiple=True,
              help='Filter nodes by tags. There are two formats: <key> or <key>=<val>')
@click.option('-e', '--extra', default=None, type=str, multiple=True,
              help='Extra variables to be passed. Format: <key>=<val>',
              show_default=False)
@click.option('-nv', '--node-vars', default=None, type=str, multiple=True,
              help='Host variables to be passed. Format: <node_id>:<key>=<val>',
              show_default=False)
def node_playbook(node_id, playbook, tags, extra, node_vars):
    """ Execute an Ansible playbook in a set of nodes.

    The NODE_ID argument is a list of strings (optional) and can filter nodes
    to execute the playbook by their node ids
    """
    node_manager = get_node_manager()

    if not tags and not node_id:
        nodes = node_manager.get_all_nodes()
    else:
        node_ids = get_nodes(node_manager, node_id, tags)
        nodes = node_manager.get_nodes_by_id(node_ids)

    if not nodes:
        print("No nodes informed")
        return 0

    playbook = path_extend(playbook)
    if not os.path.isfile(playbook):
        raise ValueError(f"Invalid playbook file `{playbook}`")

    extra_args = dict()
    for e in extra:
        if '=' not in e:
            raise ValueError(f"Invalid value for extra argument: `{e}`. "
                             f"Did you forgot '=' character?")
        extra_name, extra_value = e.split('=')[0], '='.join(e.split('=')[1:])
        extra_args[extra_name] = extra_value

    node_variables = defaultdict(dict)
    for nvar in node_vars:
        if ':' not in nvar:
            raise ValueError(f"Invalid value for node argument: `{nvar}`. "
                             f"Did you forgot ':' character?")
        node_id, node_extra_args = nvar.split(':')[0], ':'.join(nvar.split(':')[1:])
        for narg in node_extra_args.split(','):
            if '=' not in narg:
                raise ValueError(f"Invalid value for extra argument: '{narg}'. "
                                 f"Did you forgot '=' character?")
            extra_name, extra_value = narg.split('=')[0], '='.join(narg.split('=')[1:])
            node_variables[node_id].update({extra_name: extra_value})

    node_variables = defaultdict_to_dict(node_variables)
    inventory = AnsiblePlaybookExecutor.create_inventory(
        nodes, node_defaults.base_defaults.private_path, {}, node_variables)
    executor = AnsiblePlaybookExecutor(
        playbook, node_defaults.base_defaults.private_path, inventory, extra_args)
    result = executor.run()

    if not result.ok:
        logger.error(f"Playbook {playbook} did not executed successfully...")
        return 1

    print(str_at_middle("Execution Summary", 80))
    for node_id in sorted(list(result.hosts.keys())):
        r = result.hosts[node_id]
        print(f"{node_id}: {'ok' if r else 'not ok'}")

    print(f"Playbook at `{playbook}` were executed in {len(result.hosts)} nodes")
    return 0
