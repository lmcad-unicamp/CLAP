import json
import os
import glob
import yaml
import click
from collections import defaultdict
from dataclasses import asdict
from typing import List

from clap.cluster_manager import ClusterManager, ClusterConfigDatabase, ClusterRepositoryController
from clap.configs import ConfigurationDatabase
from clap.executor import ShellInvoker, SSHCommandExecutor, AnsiblePlaybookExecutor
from clap.node_manager import NodeManager, NodeRepositoryController
from clap.repository import RepositoryFactory
from clap.utils import path_extend, float_time_to_string, get_logger, \
    Singleton, defaultdict_to_dict
from providers.provider_ansible_aws import AnsibleAWSProvider
from app.cli.cliapp import clap_command, Defaults
from app.cli.modules.node import NodeDefaults, get_node_manager, get_config_db
from app.cli.modules.role import RoleDefaults, get_role_manager

logger = get_logger(__name__)


class ClusterDefaults(metaclass=Singleton):
    def __init__(self):
        self.base_defaults = Defaults()
        self.node_defaults = NodeDefaults()
        self.role_defaults = RoleDefaults()
        self.cluster_config_path = path_extend(
            self.base_defaults.configs_path, 'clusters')
        self.repository_type = 'sqlite'
        self.cluster_repository_path = path_extend(
            self.base_defaults.storage_path, 'clusters.db')


cluster_defaults = ClusterDefaults()


def get_cluster_config_db() -> ClusterConfigDatabase:
    files = glob.glob(os.path.join(cluster_defaults.cluster_config_path, '*.yml'))
    files += glob.glob(os.path.join(cluster_defaults.cluster_config_path, '*.yaml'))
    cluster_db = ClusterConfigDatabase(files)
    return cluster_db


def get_cluster_manager() -> ClusterManager:
    config_db = get_config_db()
    node_manager = get_node_manager()
    role_manager = get_role_manager()
    repository = RepositoryFactory().get_repository(
        'sqlite', cluster_defaults.cluster_repository_path)
    cluster_repository_controller = ClusterRepositoryController(repository)
    cluster_manager = ClusterManager(
        node_manager, role_manager, config_db, cluster_repository_controller,
        cluster_defaults.base_defaults.private_path
    )
    return cluster_manager


@clap_command
@click.group(help='Control and manage cluster of nodes')
@click.option('-r', '--roles-root', show_default=True,
              default=cluster_defaults.role_defaults.role_dir,
              help='Path where roles will be searched for')
@click.option('-n', '--node-repository', show_default=True,
              default=cluster_defaults.node_defaults.node_repository_path,
              help='Node database where nodes will be written')
@click.option('-c', '--cluster-repository', show_default=True,
              default=cluster_defaults.cluster_config_path,
              help='Cluster database where cluster will be written')
def cluster(roles_root, node_repository, cluster_repository):
    cluster_defaults.role_defaults.role_dir = roles_root
    cluster_defaults.node_defaults.node_repository_path = node_repository
    cluster_defaults.cluster_config_path = cluster_repository


@cluster.command('start')
@click.argument('cluster_template', nargs=1, required=True)
@click.option('-s', '--setup', help='Also perform setup', is_flag=True,
              default=True, show_default=True)
@click.option('-e', '--extra', multiple=True,
              help='Extra arguments to start operation. Format <key>=<value>')
def cluster_start(cluster_template, setup, extra):
    """ Start cluster based on a cluster template.

    The CLUSTER TEMPLATE is the ID of the cluster configuration at cluster
    configuration files.
    """
    cluster_manager = get_cluster_manager()
    cluster_db = get_cluster_config_db()

    extra_args = dict()
    for e in extra:
        if '=' not in e:
            raise ValueError(f"Invalid value for extra argument: {e}. "
                             f"Did you forgot '=' character?")
        extra_name, extra_value = e.split('=')[0], '='.join(e.split('=')[1:])
        extra_args[extra_name] = extra_value

    cluster_config = cluster_db.clusters.get(cluster_template, None)
    if cluster_config is None:
        raise ValueError(f"Invalid cluster templated: {cluster_template}")

    print(f"Starting cluster: {cluster_template} (perform setup: {setup})")
    cluster_id = cluster_manager.start_cluster(cluster_config)
    print(f"Cluster {cluster_id} successfully created")

    nodes = cluster_manager.get_cluster_nodes_types(cluster_id)

    for node_type, list_nodes in nodes.items():
        print(f"* {len(list_nodes)} nodes of type {node_type}: "
              f"{','.join(sorted(list_nodes))}")

    if not setup:
        return 0

    print(f"Performing setup operation in cluster {cluster_id}")
    try:
        cluster_manager.setup_cluster(cluster_id)
    except Exception as e:
        logger.error(e)
        print(f"Cluster not properly setup... You may wish perform the setup "
              f"operation again")
        return 1
    print(f"Cluster `{cluster_id}` finished setup!")
    return 0


@cluster.command('list')
@click.argument('cluster_id', nargs=-1, required=False)
@click.option('-d', '--detailed', is_flag=True, default=False, show_default=True,
              help='Show detailed cluster information')
@click.option('-i', '--indent', default=4, show_default=True, nargs=1, type=int,
              help="Indentation level")
@click.option('-q', '--quiet', default=False, is_flag=True, show_default=True,
              help="Show only cluster ids")
def cluster_list(cluster_id, detailed, indent, quiet):
    """List clusters in the cluster repository.

    The CLUSTER_ID argument is an optional list of cluster ids, to fiilter cluster by their ids.
    """
    if quiet and detailed:
        raise ValueError(f"Options `detailed` and `quiet` are mutually exclusive")

    cluster_manager = get_cluster_manager()

    clusters = cluster_manager.get_all_clusters() if not cluster_id else \
        [cluster_manager.get_cluster_by_id(cid) for cid in cluster_id ]
    for c in clusters:
        if quiet:
            print(c.cluster_id)
            continue

        nodes = cluster_manager.get_cluster_nodes_types(c.cluster_id)
        c.creation_time = float_time_to_string(c.creation_time)
        c.update_time = float_time_to_string(c.update_time)
        num_nodes = sum([len(node_list) for node_list in nodes.values()])

        if not detailed:
            print(f"* Cluster: {c.cluster_id}, nickname: {c.cluster_name}, "
                  f"configuration: {c.cluster_config.cluster_config_id}, "
                  f"creation time: {c.creation_time}")
        else:
            print(f"{'-'*20} Cluster: `{c.cluster_id}` (`{c.cluster_name}`) {'-'*20}")
            print(yaml.dump(asdict(c), sort_keys=True, indent=indent))

        print(f"   Has {num_nodes} node types:")
        for node_type, node_list in nodes.items():
            print(f"    - {len(node_list)} {node_type} nodes: "
                  f"{', '.join(sorted(node_list))}")

        if detailed:
            print(f"{'-'*70}")

        print()

    if not quiet:
        print(f"Listed {len(clusters)} clusters")
    return 0


@cluster.command('list-templates')
@click.argument('template', nargs=-1, type=str, required=False)
@click.option('-d', '--detailed', is_flag=True, default=False, show_default=True,
              help='Show detailed cluster information')
@click.option('-i', '--indent', default=4, show_default=True, nargs=1, type=int,
              help="Indentation level")
@click.option('-q', '--quiet', default=False, is_flag=True, show_default=True,
              help="Show only cluster names")
def list_templates(template, detailed, indent, quiet):
    """List all cluster templates in cluster configuration path.

    The TEMPLATE argument is an optional list of template ids to filter cluster
    templates by their ids
    """
    if quiet and detailed:
        raise ValueError(f"Options `detailed` and `quiet` are mutually exclusive")

    cluster_db = get_cluster_config_db()
    templates = cluster_db.clusters if template \
        else {tname: c for tname, c in cluster_db.clusters.items()}

    for name, config in templates.items():
        if quiet:
            print(name)
            continue

        if not detailed:
            print(f"cluster name: {name}")
            print(f"    node types: {', '.join(sorted(list(config.nodes.keys())))}")
            print()
        else:
            print(f"{'-'*20} CLUSTER: `{name}` {'-'*20}")
            print(yaml.dump(asdict(config), sort_keys=True, indent=indent))
            print(f"{'-' * 70}")

    if not quiet:
        print(f"Listed {len(templates)} templates")
    return 0


@cluster.command('setup')
@click.argument('cluster_id', nargs=1, required=True, type=str)
@click.option('-a', '--at', default='before_all', type=str, show_default=True,
              help='Stage to start the setup action')
def cluster_setup(cluster_id, at):
    """Perform cluster setup operation at a cluster.

    The CLUSTER_ID argument is the id of the cluster to perform the setup
    """
    cluster_manager = get_cluster_manager()

    print(f"Performing setup operation in cluster {cluster_id}")
    try:
        cluster_manager.setup_cluster(cluster_id, start_at_stage=at)
    except Exception as e:
        logger.error(e)
        print(f"Cluster not properly setup... You may wish perform the setup "
              f"operation again")
        return 1
    print(f"Cluster `{cluster_id}` finished setup!")


@cluster.command('stop')
@click.argument('cluster_id', nargs=-1, required=True, type=str)
@click.option('-r', '--remove', help='Also remove cluster from database',
              default=True, show_default=True, is_flag=True)
def cluster_stop(cluster_id, remove):
    """Stop a cluster and terminate its nodes.

    The CLUSTER_ID argument is the id of the cluster to stop (can have multiple).
    """
    cluster_manager = get_cluster_manager()
    for c in cluster_id:
        print(f"Stopping cluster `{c}`...")
        cluster_manager.stop_cluster(c, remove_cluster=remove)
        print(f"Cluster `{c}` stopped!")
    return 0


@cluster.command('pause')
@click.argument('cluster_id', nargs=-1, required=True, type=str)
def cluster_pause(cluster_id):
    """Pause a cluster and pause nodes.

    The CLUSTER_ID argument is the id of the cluster to pause.
    """
    cluster_manager = get_cluster_manager()
    for c in cluster_id:
        print(f"Pausing cluster `{c}`...")
        cluster_manager.pause_cluster(c)
        print(f"Cluster `{c}` paused!")
    return 0


@cluster.command('resume')
@click.argument('cluster_id', nargs=-1, required=True, type=str)
def cluster_resume(cluster_id):
    """Resume a cluster.

    The CLUSTER_ID argument is the id of the cluster to resume.
    """
    cluster_manager = get_cluster_manager()
    for c in cluster_id:
        print(f"Resuming cluster `{c}`...")
        cluster_manager.resume_cluster(c)
        print(f"Cluster `{c}` resumed!")
    return 0


@cluster.command('alive')
@click.argument('cluster_id', nargs=-1, required=True, type=str)
def cluster_alive(cluster_id):
    """Check if cluster is alive (if all nodes are up).

    The CLUSTER_ID argument is the id of the cluster to check for aliveness.
    """
    cluster_manager = get_cluster_manager()
    for c in cluster_id:
        print(f"Checking if cluster {c} is alive...")
        alive_nodes = cluster_manager.is_alive(c, retries=5)
        not_alives = []
        for node_id, status in alive_nodes.items():
            print(f"{node_id}: {'alive' if status else 'not alive'}")
            if not status:
                not_alives.append(node_id)

        if not_alives:
            print(f"Cluster `{c}` is not completely alive. "
                  f"Nodes `{', '.join(sorted(not_alives))}` are unreachable...")
        else:
            print(f"Cluster `{c}` is up!")
    return 0


@cluster.command('grow')
@click.argument('cluster_id', nargs=1, required=True, type=str)
@click.option('-n', '--node', multiple=True, required=True, type=str,
              help='Type of node to start. Format: <node_type>:<num>')
@click.option('-s', '--setup', is_flag=True, default=True, show_default=True,
              help='Also perform setup',)
def cluster_grow(cluster_id, node, setup):
    """Start more nodes at a cluster by cluster node type.

    The CLUSTER_ID argument is the id of the cluster to add more nodes.
    """
    cluster_manager = get_cluster_manager()
    nodes_to_start = list()
    cluster = cluster_manager.get_cluster_by_id(cluster_id)

    for n in node:
        node_name, qtde = n.split(':')[0], int(n.split(':')[1]) if ':' in n else 1
        nodes_to_start.append((node_name, qtde))

    all_nodes = dict()
    for node_type, qtde in nodes_to_start:
        t = cluster.cluster_config.nodes[node_type].type
        instance_info = cluster_manager.config_db.instance_descriptors[t]
        nodes = cluster_manager.start_cluster_node(
            cluster_id, node_type, instance_info, qtde)
        all_nodes[node_type] = all_nodes
        if len(nodes) != qtde:
            logger.error(f"Could not start {qtde} {node_type} nodes. "
                         f"Only {len(nodes)} were started")
            continue

    for node_type, list_nodes in all_nodes.items():
        print(f"* {len(list_nodes)} nodes of type {node_type}: "
              f"{','.join(sorted(list_nodes))}")

    if not setup:
        return 0

    # TODO check a bug here...
    print(f"Performing setup operation in cluster {cluster_id}")
    try:
        cluster_manager.setup_cluster(cluster_id, nodes_types=all_nodes)
    except Exception as e:
        logger.error(e)
        print(f"Cluster not properly setup... You may wish perform the setup "
              f"operation again")
        return 1
    print(f"Cluster `{cluster_id}` finished setup!")
    return 0
#
#
# @cluster.command('shrink')
# @click.argument('cluster_id', nargs=1, required=True, type=str)
# @click.option('-n', '--node', help='Type of node to terminate. Format: <node_type>:<num>', multiple=True, required=True, type=str)
# @click.option('-s', '--stop', help='Also stop the nodes', is_flag=True, default=True, show_default=True)
# @click.option('-r', '--remove', help='Remove cluster if no nodes in cluster', is_flag=True, default=True, show_default=True)
# def cluster_shrink(cluster_id, node, stop, remove):
#     """Stop more nodes from a cluster by cluster node type.
#
#     The CLUSTER_ID argument is the id of the cluster to stop nodes.
#     """
#     cluster_module = ClusterModule.get_module()
#     node_types = dict()
#     try:
#         for n in node:
#             node_name, qtde = n.split(':')[0], int(n.split(':')[1])
#             node_types[node_name] = qtde
#     except Exception as e:
#         logger.error(f"Invalid node format string")
#         raise e
#     print(f"Removing nodes of types `{node_types}` from cluster `{cluster_id}`")
#     nodes = cluster_module.remove_nodes_from_cluster_by_type(cluster_id, node_types, stop_nodes=stop, remove_cluster=remove)
#     print(f"Removed nodes {', '.join(sorted(nodes))}")
#     return 0
#
#
# @cluster.command('add-nodes')
# @click.argument('cluster_id', nargs=1, required=True, type=str)
# @click.option('-n', '--node', help='Type of node to start. Format: <node_id>:<node_type>', multiple=True, required=True, type=str)
# @click.option('-s', '--setup', help='Also perform setup', is_flag=True, default=True, show_default=True)
# def cluster_add_nodes(cluster_id, node, setup):
#     """Add existing nodes to a cluster by their ids.
#
#     The CLUSTER_ID argument is the id of the cluster to add more nodes.
#     """
#     cluster_module = ClusterModule.get_module()
#     node_types = defaultdict(list)
#
#     for n in node:
#         node_id, node_type = n.split(':')[0], n.split(':')[1]
#         node_types[node_type].append(node_id)
#
#     node_types = dict(node_types)
#     nodes = cluster_module.add_existing_node_to_cluster(cluster_id, node_types)
#
#     for node_type, list_nodes in nodes.items():
#         print(f'Added {len(list_nodes)} nodes of type `{node_type}` to cluster `{cluster_id}`:')
#         for n in list_nodes:
#             print(' ' * 4, n)
#
#     if not setup:
#         return 0
#
#     print(f"Performing setup operation in cluster `{cluster_id}`...")
#     try:
#         cluster_module.cluster_setup(cluster_id, nodes_type=nodes)
#     except Exception as e:
#         logger.error(e)
#         print(f"Cluster not properly setup... You may wish perform the setup operation again")
#         raise e
#     print(f"Cluster `{cluster_id}` finished setup!")
#     return 0
#
#
# @cluster.command('remove-nodes')
# @click.argument('cluster_id', nargs=1, required=True, type=str)
# @click.option('-n', '--node', help='Id of the nodes to remove from the cluster', multiple=True, required=True, type=str)
# @click.option('-s', '--stop', help='Also stop the nodes', is_flag=True, default=True, show_default=True)
# @click.option('-r', '--remove', help='Remove cluster if no nodes in cluster', is_flag=True, default=True, show_default=True)
# def cluster_remove_nodes(cluster_id, node, stop, remove):
#     """Remove nodes from a cluster based on the node id.
#
#     The CLUSTER_ID argument is the id of the cluster to remove nodes.
#     """
#     cluster_module = ClusterModule.get_module()
#     print(f"Removing nodes `{', '.join(sorted(node))}` from cluster `{cluster_id}`")
#     nodes = cluster_module.remove_nodes_from_cluster_by_id(
#         cluster_id, node_ids=list(node), stop_nodes=stop, remove_cluster=remove)
#     print(f"Removed nodes {', '.join(sorted(nodes))}")
#     return 0
#
#
#
#
#
#
# @cluster.command('update')
# @click.argument('cluster_id', nargs=1, required=True, type=str)
# @click.option('-e', '--extra', help='Extra arguments to cluster configuration. Format <key>=<value>', multiple=True)
# def cluster_update(cluster_id, extra):
#     """Update a cluster config with the same as in the configuration files.
#
#     The CLUSTER_ID argument is the id of the cluster to update its configuration.
#     """
#     cluster_module = ClusterModule.get_module()
#     extra_args = dict()
#     for e in extra:
#         if '=' not in e:
#             raise ValueError(f"Invalid value for extra argument: `{e}`. "
#                              f"Did you forgot '=' character?")
#         extra_name, extra_value = e.split('=')[0], '='.join(e.split('=')[1:])
#         extra_args[extra_name] = extra_value
#
#     cluster_module.update_cluster_config(cluster_id, extra_args=extra_args)
#     return 0
#
#
# def cluster_group_add():
#     pass
#
#
# def cluster_group_action():
#     pass
#
#
# def cluster_group_remove():
#     pass
#
#
# @cluster.command('connect')
# @click.argument('cluster_id', nargs=1, required=True, type=str)
# def cluster_connect(cluster_id):
#     """Obtain an interactive SSH shell to a cluster node.
#
#     The CLUSTER_ID argument is the id of the cluster to obtain an interactive shell.
#     """
#     cluster_module = ClusterModule.get_module()
#     cluster_module.connect(cluster_id)
#     return 0
#
#
# @cluster.command('execute')
# @click.argument('cluster_id', nargs=1, required=True, type=str)
# @click.option('-cmd', '--command', help='Command string to execute', required=True, type=str)
# def cluster_execute(cluster_id, command):
#     """Execute an shell command in all cluster nodes.
#
#     The CLUSTER_ID argument is the id of the cluster to execute the shell command.
#     """
#     cluster_module = ClusterModule.get_module()
#     executions = cluster_module.execute_command(cluster_id, command)
#     for node_id in sorted(list(executions.keys())):
#         result = executions[node_id]
#         if not result:
#             print(f"Error executing command in node `{node_id}`")
#             continue
#         print(f"{'-' * 20} STDOUT: `{node_id}` {'-' * 20}")
#         print(''.join(result.stdout_lines))
#         print(f"\n{'-' * 20} STDERR: `{node_id}` {'-' * 20}")
#         print(''.join(result.stderr_lines))
#         print(f"\n{'-' * 70}")
#
#     return 0
#
#
# @cluster.command('playbook')
# @click.argument('cluster_id', nargs=1, required=True, type=str)
# @click.option('-p', '--playbook', help='Path to the Ansible Playbook file', required=True, type=str)
# @click.option('-e', '--extra', help='Extra arguments to cluster configuration. Format <key>=<value>', multiple=True)
# def cluster_playbook(cluster_id, playbook, extra):
#     """Execute an Ansible Playbook in all cluster nodes.
#
#     The CLUSTER_ID argument is the id of the cluster to execute the Ansible Playbook.
#     """
#     cluster_module = ClusterModule.get_module()
#     extra_args = dict()
#     for e in extra:
#         if '=' not in e:
#             raise ValueError(f"Invalid value for extra argument: `{e}`. "
#                              f"Did you forgot '=' character?")
#         extra_name, extra_value = e.split('=')[0], '='.join(e.split('=')[1:])
#         extra_args[extra_name] = extra_value
#
#     playbook = path_extend(playbook)
#     if not os.path.isfile(playbook):
#         raise ValueError(f"Invalid playbook at `{playbook}`")
#
#     results = cluster_module.execute_playbook(cluster_id, playbook, extra_args)
#     if results.ok:
#         print(f"Playbook `{playbook}` was successfully executed in cluster `{cluster_id}`")
#         return 0
#     else:
#         print(f"Playbook {playbook} was not executed correctly...")
#         return 1
#
#
# def cluster_copy():
#     pass
#
#
# def cluster_fetch():
#     pass
