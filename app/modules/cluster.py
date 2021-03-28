import glob
import os
from collections import defaultdict
from dataclasses import asdict

import click
import yaml

from common.utils import get_logger, path_extend, float_time_to_string
from modules.cluster import ClusterModule, ClusterDefaults, ClusterConfigReader
from modules.node import NodeDefaults, NodeModule
from app.module import clap_command

logger = get_logger(__name__)

node_defaults = NodeDefaults()
cluster_defaults = ClusterDefaults()


@clap_command
@click.group(help='Control and manage cluster of nodes')
@click.option('-p', '--platform-db', default=node_defaults.node_repository_path, help='Platform database to be used, where nodes will be written', show_default=True)
@click.option('-d', '--cluster-db', default=cluster_defaults.cluster_repository_path, help='Cluster database to be used, where cluster information will be written', show_default=True)
@click.option('-c', '--config', default=cluster_defaults.cluster_config_path, type=str, help='Path where cluster configurations will be search', show_default=True)
def cluster(platform_db, cluster_db, config):
    node_defaults.node_repository_path = platform_db
    cluster_defaults.cluster_repository_path = cluster_db
    cluster_defaults.cluster_config_path = config


@cluster.command('start')
@click.argument('cluster_id', nargs=1, required=True)
@click.option('-s', '--setup', help='Also perform setup', is_flag=True, default=True, show_default=True)
@click.option('-e', '--extra', help='Extra arguments to start operation. Format <key>=<value>', multiple=True)
def cluster_start(cluster_id, setup, extra):
    """ Start cluster based on a cluster template.

    The CLUSTER is the ID of the cluster configuration at cluster configuration files.
    """
    cluster_module = ClusterModule.get_module()
    node_module = NodeModule.get_module()

    extra_args = dict()
    for e in extra:
        if '=' not in e:
            raise ValueError(f"Invalid value for extra argument: `{e}`. "
                             f"Did you forgot '=' character?")
        extra_name, extra_value = e.split('=')[0], '='.join(e.split('=')[1:])
        extra_args[extra_name] = extra_value

    print(f"Starting cluster `{cluster_id}` (perform setup: {setup})")
    cluster_id = cluster_module.create_cluster(cluster_id, extra_args=extra_args)
    print(f"Cluster `{cluster_id}` successfully created")

    nodes = cluster_module.get_nodes_from_cluster_by_type(cluster_id)

    for node_type, list_nodes in nodes.items():
        _nodes = node_module.get_nodes_by_id(node_ids=list_nodes)
        print(f'Added {len(list_nodes)} nodes of type `{node_type}` to cluster `{cluster_id}`:')
        for n in _nodes:
            print(' '*4, n)

    if not setup:
        return 0

    print(f"Performing setup operation in cluster `{cluster_id}`...")
    try:
        cluster_module.cluster_setup(cluster_id)
    except Exception as e:
        logger.error(e)
        print(f"Cluster not properly setup... You may wish perform the setup operation again")
        raise e
    print(f"Cluster `{cluster_id}` finished setup!")
    return 0


@cluster.command('list')
@click.argument('cluster_id', nargs=-1, required=False)
@click.option('-d', '--detailed', help='Show detailed cluster information', is_flag=True, default=False, show_default=True)
@click.option('-i', '--indent', default=4, show_default=True, nargs=1, type=int, help="Indentation level")
@click.option('-q', '--quiet', default=False, is_flag=True, show_default=True, help="Show only cluster ids")
def cluster_list(cluster_id, detailed, indent, quiet):
    """List clusters in the cluster repository.

    The CLUSTER_ID argument is an optional list of cluster ids, to fiilter cluster by their ids.
    """
    if quiet and detailed:
        raise ValueError(f"Options `detailed` and `quiet` are mutually exclusive")

    cluster_module = ClusterModule.get_module()
    clusters = cluster_module.get_all_clusters() if not cluster_id else cluster_module.get_clusters(list(cluster_id))
    for c in clusters:
        if quiet:
            print(c.cluster_id)
            continue

        nodes = cluster_module.get_nodes_from_cluster_by_type(c.cluster_id)

        print(f"{'-'*20} Cluster: `{c.cluster_id}` (`{c.cluster_name}`) {'-'*20}")
        c.creation_time = float_time_to_string(c.creation_time)
        c.update_time = float_time_to_string(c.update_time)
        print(c)
        print(f"Has {len(nodes)} node types:")
        all_nodes = set()
        for node_type, list_nodes in nodes.items():
            all_nodes.update(list_nodes)
            nodes = []
            for node in cluster_module.node_module.get_nodes_by_id(list_nodes):
                for tag in node.tags[f"{c.cluster_id}_setup"]:
                    if tag.split(':')[0] == node_type:
                        nodes.append((node.node_id, 'setup' if tag.split(':')[1] == 'yes' else 'not setup'))

            print(" "*4, f"{node_type} ({len(nodes)} nodes): `{', '.join(sorted([f'{node_id} ({setup})' for node_id, setup in nodes]))}`")

        if detailed:
            print("In-Use Configuration:")
            print(yaml.dump(c.to_dict(), sort_keys=True, indent=indent))

        print(f"Cluster `{c.cluster_id}` has {len(all_nodes)} nodes")

        print(f"{'-'*70}")
        print()

    if not quiet:
        print(f"Listed {len(clusters)} clusters")
    return 0


@cluster.command('list-templates')
@click.argument('template', nargs=-1, type=str, required=False)
@click.option('-d', '--detailed', help='Show detailed cluster information', is_flag=True, default=False, show_default=True)
@click.option('-i', '--indent', default=4, show_default=True, nargs=1, type=int, help="Indentation level")
@click.option('-q', '--quiet', default=False, is_flag=True, show_default=True, help="Show only cluster names")
def list_templates(template, detailed, indent, quiet):
    """List all cluster templates in cluster configuration path.

    The TEMPLATE argument is an optional list of template ids to filter cluster templates by their ids
    """
    if quiet and detailed:
        raise ValueError(f"Options `detailed` and `less` are mutually exclusive")

    cluster_files = glob.glob(path_extend(cluster_defaults.cluster_config_path, '*'))
    config_reader = ClusterConfigReader(cluster_files)
    templates = config_reader.get_all_clusters()
    templates = templates if not template else {t: templates[t] for t in template}

    for name, config in templates.items():
        if quiet:
            print(name)
            continue

        if not detailed:
            print(f"cluster name: {name}")
            print(f"    nodes: `{', '.join(sorted(list(config.nodes.keys())))}`")
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
@click.option('-a', '--at', default='before_all', type=str, show_default=True, help='Step to start the setup action at')
def cluster_setup(cluster_id, at):
    """Perform cluster setup operation at a cluster.

    The CLUSTER_ID argument is the id of the cluster to perform the setup
    """
    cluster_module = ClusterModule.get_module()
    try:
        cluster_module.cluster_setup(cluster_id, at=at)
    except Exception as e:
        logger.error(e)
        logger.error(f"Cluster {cluster_id} not properly setup... You may wish perform the setup operation again")
        raise e
    print(f"Cluster `{cluster_id}` finished setup!")
    return 0


@cluster.command('grow')
@click.argument('cluster_id', nargs=1, required=True, type=str)
@click.option('-n', '--node', help='Type of node to start. Format: <node_type>:<num>', multiple=True, required=True, type=str)
@click.option('-s', '--setup', help='Also perform setup', is_flag=True, default=True, show_default=True)
def cluster_grow(cluster_id, node, setup):
    """Start more nodes at a cluster by cluster node type.

    The CLUSTER_ID argument is the id of the cluster to add more nodes.
    """
    cluster_module = ClusterModule.get_module()
    node_module = NodeModule.get_module()
    node_types = dict()

    for n in node:
        node_name, qtde = n.split(':')[0], int(n.split(':')[1]) if ':' in n else 1
        node_types[node_name] = (qtde, qtde)

    nodes = cluster_module.add_nodes_to_cluster(cluster_id, node_types)

    for node_type, list_nodes in nodes.items():
        _nodes = node_module.get_nodes_by_id(node_ids=list_nodes)
        print(f'Added {len(list_nodes)} nodes of type `{node_type}` to cluster `{cluster_id}`:')
        for n in _nodes:
            print(' ' * 4, n)

    if not setup:
        return 0

    print(f"Performing setup operation in cluster `{cluster_id}`...")
    try:
        cluster_module.cluster_setup(cluster_id, nodes_type=nodes)
    except Exception as e:
        logger.error(e)
        print(f"Cluster not properly setup... You may wish perform the setup operation again")
        raise e
    print(f"Cluster `{cluster_id}` finished setup!")
    return 0


@cluster.command('shrink')
@click.argument('cluster_id', nargs=1, required=True, type=str)
@click.option('-n', '--node', help='Type of node to terminate. Format: <node_type>:<num>', multiple=True, required=True, type=str)
@click.option('-s', '--stop', help='Also stop the nodes', is_flag=True, default=True, show_default=True)
@click.option('-r', '--remove', help='Remove cluster if no nodes in cluster', is_flag=True, default=True, show_default=True)
def cluster_shrink(cluster_id, node, stop, remove):
    """Stop more nodes from a cluster by cluster node type.

    The CLUSTER_ID argument is the id of the cluster to stop nodes.
    """
    cluster_module = ClusterModule.get_module()
    node_types = dict()
    try:
        for n in node:
            node_name, qtde = n.split(':')[0], int(n.split(':')[1])
            node_types[node_name] = qtde
    except Exception as e:
        logger.error(f"Invalid node format string")
        raise e
    print(f"Removing nodes of types `{node_types}` from cluster `{cluster_id}`")
    nodes = cluster_module.remove_nodes_from_cluster_by_type(cluster_id, node_types, stop_nodes=stop, remove_cluster=remove)
    print(f"Removed nodes {', '.join(sorted(nodes))}")
    return 0


@cluster.command('add-nodes')
@click.argument('cluster_id', nargs=1, required=True, type=str)
@click.option('-n', '--node', help='Type of node to start. Format: <node_id>:<node_type>', multiple=True, required=True, type=str)
@click.option('-s', '--setup', help='Also perform setup', is_flag=True, default=True, show_default=True)
def cluster_add_nodes(cluster_id, node, setup):
    """Add existing nodes to a cluster by their ids.

    The CLUSTER_ID argument is the id of the cluster to add more nodes.
    """
    cluster_module = ClusterModule.get_module()
    node_types = defaultdict(list)

    for n in node:
        node_id, node_type = n.split(':')[0], n.split(':')[1]
        node_types[node_type].append(node_id)

    node_types = dict(node_types)
    nodes = cluster_module.add_existing_node_to_cluster(cluster_id, node_types)

    for node_type, list_nodes in nodes.items():
        print(f'Added {len(list_nodes)} nodes of type `{node_type}` to cluster `{cluster_id}`:')
        for n in list_nodes:
            print(' ' * 4, n)

    if not setup:
        return 0

    print(f"Performing setup operation in cluster `{cluster_id}`...")
    try:
        cluster_module.cluster_setup(cluster_id, nodes_type=nodes)
    except Exception as e:
        logger.error(e)
        print(f"Cluster not properly setup... You may wish perform the setup operation again")
        raise e
    print(f"Cluster `{cluster_id}` finished setup!")
    return 0


@cluster.command('remove-nodes')
@click.argument('cluster_id', nargs=1, required=True, type=str)
@click.option('-n', '--node', help='Id of the nodes to remove from the cluster', multiple=True, required=True, type=str)
@click.option('-s', '--stop', help='Also stop the nodes', is_flag=True, default=True, show_default=True)
@click.option('-r', '--remove', help='Remove cluster if no nodes in cluster', is_flag=True, default=True, show_default=True)
def cluster_remove_nodes(cluster_id, node, stop, remove):
    """Remove nodes from a cluster based on the node id.

    The CLUSTER_ID argument is the id of the cluster to remove nodes.
    """
    cluster_module = ClusterModule.get_module()
    print(f"Removing nodes `{', '.join(sorted(node))}` from cluster `{cluster_id}`")
    nodes = cluster_module.remove_nodes_from_cluster_by_id(
        cluster_id, node_ids=list(node), stop_nodes=stop, remove_cluster=remove)
    print(f"Removed nodes {', '.join(sorted(nodes))}")
    return 0


@cluster.command('stop')
@click.argument('cluster_id', nargs=-1, required=True, type=str)
@click.option('-t', '--terminate', help='Also terminate nodes', default=True, show_default=True, is_flag=True)
def cluster_stop(cluster_id, terminate):
    """Stop a cluster and terminate its nodes.

    The CLUSTER_ID argument is the id of the cluster to stop (can have multiple).
    """
    cluster_module = ClusterModule.get_module()
    for c in cluster_id:
        print(f"Stopping cluster `{c}`...")
        cluster_module.stop_cluster(c, stop_nodes=terminate)
        print(f"Cluster `{c}` stopped!")
    return 0


@cluster.command('pause')
@click.argument('cluster_id', nargs=-1, required=True, type=str)
@click.option('-f', '--force', help='Pause nodes even if it belong to another running cluster', default=False, show_default=True, is_flag=True)
def cluster_pause(cluster_id, force):
    """Pause a cluster and terminate its nodes.

    The CLUSTER_ID argument is the id of the cluster to stop.
    """
    cluster_module = ClusterModule.get_module()
    for c in cluster_id:
        print(f"Pausing cluster `{c}`...")
        cluster_module.pause_cluster(c, force_pause=force)
        print(f"Cluster `{c}` paused!")
    return 0


@cluster.command('resume')
@click.argument('cluster_id', nargs=-1, required=True, type=str)
def cluster_resume(cluster_id):
    """Resume a cluster.

    The CLUSTER_ID argument is the id of the cluster to resume.
    """
    cluster_module = ClusterModule.get_module()
    for c in cluster_id:
        print(f"Resuming cluster `{c}`...")
        cluster_module.resume_cluster(c)
        print(f"Cluster `{c}` resumed!")
    return 0


@cluster.command('alive')
@click.argument('cluster_id', nargs=-1, required=True, type=str)
def cluster_alive(cluster_id):
    """Check if cluster is alive (if all nodes are up).

    The CLUSTER_ID argument is the id of the cluster to check for aliveness.
    """
    cluster_module = ClusterModule.get_module()
    for c in cluster_id:
        print(f"Checking if cluster `{c}` is alive...")
        alive_nodes = cluster_module.alive_cluster(c)
        not_alives = []
        for node_id, status in alive_nodes.items():
            print(f"{node_id}: {'alive' if status else 'not alive'}")
            if not status:
                not_alives.append(node_id)

        if not_alives:
            print(f"Cluster `{c}` is not completely alive. Nodes `{', '.join(sorted(not_alives))}` are unreachable...")
        else:
            print(f"Cluster `{c}` is up!")

    return 0


@cluster.command('update')
@click.argument('cluster_id', nargs=1, required=True, type=str)
@click.option('-e', '--extra', help='Extra arguments to cluster configuration. Format <key>=<value>', multiple=True)
def cluster_update(cluster_id, extra):
    """Update a cluster config with the same as in the configuration files.

    The CLUSTER_ID argument is the id of the cluster to update its configuration.
    """
    cluster_module = ClusterModule.get_module()
    extra_args = dict()
    for e in extra:
        if '=' not in e:
            raise ValueError(f"Invalid value for extra argument: `{e}`. "
                             f"Did you forgot '=' character?")
        extra_name, extra_value = e.split('=')[0], '='.join(e.split('=')[1:])
        extra_args[extra_name] = extra_value

    cluster_module.update_cluster_config(cluster_id, extra_args=extra_args)
    return 0


def cluster_group_add():
    pass


def cluster_group_action():
    pass


def cluster_group_remove():
    pass


@cluster.command('connect')
@click.argument('cluster_id', nargs=1, required=True, type=str)
def cluster_connect(cluster_id):
    """Obtain an interactive SSH shell to a cluster node.

    The CLUSTER_ID argument is the id of the cluster to obtain an interactive shell.
    """
    cluster_module = ClusterModule.get_module()
    cluster_module.connect(cluster_id)
    return 0


@cluster.command('execute')
@click.argument('cluster_id', nargs=1, required=True, type=str)
@click.option('-cmd', '--command', help='Command string to execute', required=True, type=str)
def cluster_execute(cluster_id, command):
    """Execute an shell command in all cluster nodes.

    The CLUSTER_ID argument is the id of the cluster to execute the shell command.
    """
    cluster_module = ClusterModule.get_module()
    executions = cluster_module.execute_command(cluster_id, command)
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


@cluster.command('playbook')
@click.argument('cluster_id', nargs=1, required=True, type=str)
@click.option('-p', '--playbook', help='Path to the Ansible Playbook file', required=True, type=str)
@click.option('-e', '--extra', help='Extra arguments to cluster configuration. Format <key>=<value>', multiple=True)
def cluster_playbook(cluster_id, playbook, extra):
    """Execute an Ansible Playbook in all cluster nodes.

    The CLUSTER_ID argument is the id of the cluster to execute the Ansible Playbook.
    """
    cluster_module = ClusterModule.get_module()
    extra_args = dict()
    for e in extra:
        if '=' not in e:
            raise ValueError(f"Invalid value for extra argument: `{e}`. "
                             f"Did you forgot '=' character?")
        extra_name, extra_value = e.split('=')[0], '='.join(e.split('=')[1:])
        extra_args[extra_name] = extra_value

    playbook = path_extend(playbook)
    if not os.path.isfile(playbook):
        raise ValueError(f"Invalid playbook at `{playbook}`")

    results = cluster_module.execute_playbook(cluster_id, playbook, extra_args)
    if results.ok:
        print(f"Playbook `{playbook}` was successfully executed in cluster `{cluster_id}`")
        return 0
    else:
        print(f"Playbook {playbook} was not executed correctly...")
        return 1


def cluster_copy():
    pass


def cluster_fetch():
    pass
