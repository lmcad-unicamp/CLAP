import multiprocessing
import os
import glob
import yaml
import click
from collections import defaultdict
from dataclasses import asdict

from clap.cluster_manager import ClusterManager, ClusterConfigDatabase, ClusterRepositoryController
from clap.executor import ShellInvoker, SSHCommandExecutor, AnsiblePlaybookExecutor
from clap.repository import RepositoryFactory
from clap.utils import path_extend, float_time_to_string, get_logger, \
    Singleton, defaultdict_to_dict, str_at_middle
from app.cli.cliapp import clap_command, Defaults, ArgumentError
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
              default=cluster_defaults.cluster_repository_path,
              help='Cluster database where cluster will be written')
@click.option('-d', '--config-dir', show_default=True,
              default=cluster_defaults.cluster_config_path,
              help='Directory to search for cluster template files')
def cluster(roles_root, node_repository, cluster_repository, config_dir):
    cluster_defaults.role_defaults.role_dir = roles_root
    cluster_defaults.node_defaults.node_repository_path = node_repository
    cluster_defaults.cluster_repository_path = cluster_repository
    cluster_defaults.cluster_config_path = config_dir


@cluster.command('start')
@click.argument('cluster_template', nargs=1, required=True)
@click.option('-n', '--no-setup', help='Do not perform setup', is_flag=True,
              default=False, show_default=True)
def cluster_start(cluster_template, no_setup):
    """ Start cluster based on a cluster template.

    The CLUSTER TEMPLATE is the ID of the cluster configuration at cluster
    configuration files.
    """
    cluster_manager = get_cluster_manager()
    cluster_db = get_cluster_config_db()

    cluster_config = cluster_db.clusters.get(cluster_template, None)
    if cluster_config is None:
        raise ValueError(f"Invalid cluster templated: {cluster_template}")

    print(f"Starting cluster: {cluster_template} (perform setup: {not no_setup})")
    cluster_id = cluster_manager.start_cluster(
        cluster_config, max_workers=multiprocessing.cpu_count())
    print(f"Cluster {cluster_id} successfully created")

    nodes = cluster_manager.get_cluster_nodes_types(cluster_id)

    for node_type, list_nodes in nodes.items():
        print(f"* {len(list_nodes)} nodes of type {node_type}: "
              f"{','.join(sorted(list_nodes))}")

    if no_setup:
        return 0

    print(f"Performing setup operation in cluster {cluster_id}")
    try:
        cluster_manager.setup_cluster(
            cluster_id, max_workers=multiprocessing.cpu_count())
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

    The CLUSTER_ID argument is an optional list of cluster ids, to filter cluster by their ids.
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

        print(f"   Has {num_nodes} nodes:")
        for node_type, node_list in nodes.items():
            print(f"    - {len(node_list)} {node_type} nodes: "
                  f"{', '.join(sorted(node_list))}")

        if detailed:
            print(f"{'-'*70}")

        print()

    if not quiet:
        print(f"Listed {len(clusters)} clusters")
    return 0


@cluster.command('nodes')
@click.argument('cluster_id', nargs=1, required=True)
@click.option('-q', '--quiet', default=False, is_flag=True, show_default=True,
              help="Show only node ids")
def cluster_list(cluster_id, quiet):
    """List cluster's nodes.

    The CLUSTER_ID is the cluster id.
    """
    cluster_manager = get_cluster_manager()
    cluster_manager.get_cluster_by_id(cluster_id)

    if quiet:
        nodes = cluster_manager.get_all_cluster_nodes(cluster_id)
        for n in nodes:
            print(n)
        return 0

    nodes = cluster_manager.get_cluster_nodes_types(cluster_id)
    for node_type, node_list in nodes.items():
        print(f"{len(node_list)} {node_type}: {', '.join(sorted(node_list))}")

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
        cluster_manager.setup_cluster(
            cluster_id, start_at_stage=at,
            max_workers=1)
    except Exception as e:
        logger.error(e)
        print(f"Cluster not properly setup... You may wish perform the setup "
              f"operation again")
        return 1
    print(f"Cluster `{cluster_id}` finished setup!")
    return 0

@cluster.command('update')
@click.argument('cluster_id', nargs=1, required=True, type=str)
@click.option('-c', '--config', default=None, type=str, show_default=False,
              help='New cluster config name')
def cluster_update(cluster_id, config):
    """Perform cluster setup operation at a cluster.

    The CLUSTER_ID argument is the id of the cluster to perform the setup
    """
    cluster_manager = get_cluster_manager()
    cluster_config_db = get_cluster_config_db()
    cluster = cluster_manager.get_cluster_by_id(cluster_id)
    if config is not None:
        new_config = cluster_config_db.clusters.get(config, None)
        if not new_config:
            raise ArgumentError(f"Invalid cluster configuration: {config}")
    else:
        new_config = cluster_config_db.clusters.get(
            cluster.cluster_config.cluster_config_id, None)
        if not new_config:
            raise ArgumentError(f"Invalid cluster configuration: "
                                f"{cluster.cluster_config.cluster_config_id}")
    cluster.cluster_config = new_config
    cluster_manager.upsert_cluster(cluster)
    print(f"Configuration of cluster {cluster_id} has been updated")
    return 0


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
@click.option('-n', '--no-setup', is_flag=True, default=False, show_default=True,
              help='Do not perform setup')
def cluster_grow(cluster_id, node, no_setup):
    """Start more nodes at a cluster by cluster node type.

    The CLUSTER_ID argument is the id of the cluster to add more nodes.
    """
    cluster_manager = get_cluster_manager()
    nodes_to_start = list()

    for n in node:
        node_name, qtde = n.split(':')[0], int(n.split(':')[1]) if ':' in n else 1
        nodes_to_start.append((node_name, qtde))

    all_nodes = defaultdict(list)
    for node_type, qtde in nodes_to_start:
        nodes = cluster_manager.grow(cluster_id, node_type, qtde, min_count=qtde)
        print(f"Started {len(nodes)} of type {node_type}: {', '.join(sorted(nodes))}")
        all_nodes[node_type] += nodes
    all_nodes = defaultdict_to_dict(all_nodes)

    if no_setup:
        return 0

    print(f"Performing setup operation in cluster {cluster_id}")
    try:
        cluster_manager.setup_cluster(cluster_id, nodes_being_added=all_nodes)
    except Exception as e:
        logger.error(e)
        print(f"Cluster not properly setup... You may wish perform the setup "
              f"operation again")
        return 1
    print(f"Cluster `{cluster_id}` finished setup!")
    return 0


@cluster.command('connect')
@click.argument('cluster_id', nargs=1, required=True, type=str)
def cluster_connect(cluster_id):
    """Obtain an interactive SSH shell to a cluster node.

    The CLUSTER_ID argument is the id of the cluster to obtain an interactive shell.
    """
    cluster_manager = get_cluster_manager()
    node_manager = get_node_manager()
    cluster = cluster_manager.get_cluster_by_id(cluster_id)
    nodes = cluster_manager.get_cluster_nodes_types(cluster_id)
    if cluster.cluster_config.options.ssh_to is not None:
        if cluster.cluster_config.options.ssh_to not in nodes:
            raise ValueError(
                f"No nodes of type {cluster.cluster_config.options.ssh_to} to "
                f"connect")
        nodes = node_manager.get_nodes_by_id(
            nodes[cluster.cluster_config.options.ssh_to])
        print(f"Connecting to node: {nodes[0].node_id} "
              f"({cluster.cluster_config.options.ssh_to})")
        e = ShellInvoker(nodes[0], cluster_defaults.base_defaults.private_path)
        e.run()
    else:
        nodes = cluster_manager.get_all_cluster_nodes(cluster_id)
        if not nodes:
            raise ValueError("No nodes in the cluster")
        nodes = node_manager.get_nodes_by_id(nodes)
        e = ShellInvoker(nodes[0], cluster_defaults.base_defaults.private_path)
        e.run()
    return 0


@cluster.command('execute')
@click.argument('cluster_id', nargs=1, required=True, type=str)
@click.option('-cmd', '--command', required=True, type=str,
              help='Command string to execute')
def cluster_execute(cluster_id, command):
    """Execute an shell command in all cluster nodes.

    The CLUSTER_ID argument is the id of the cluster to execute the shell command.
    """
    # TODO check this method
    cluster_manager = get_cluster_manager()
    node_manager = get_node_manager()
    nodes = cluster_manager.get_all_cluster_nodes(cluster_id)
    nodes = node_manager.get_nodes_by_id(nodes)

    if not nodes:
        print("No nodes in the cluster")
        return 0

    e = SSHCommandExecutor(
        command, nodes, cluster_defaults.base_defaults.private_path)
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


@cluster.command('playbook')
@click.argument('cluster_id', nargs=1, required=True, type=str)
@click.option('-p', '--playbook', required=True, type=str,
              help='Path to the Ansible Playbook file')
@click.option('-e', '--extra', multiple=True,
              help='Extra arguments to cluster configuration. Format <key>=<value>')
@click.option('-nv', '--node-vars', default=None, type=str, multiple=True,
              help='Host variables to be passed. Format: <node_id>:<key>=<val>',
              show_default=False)
def cluster_playbook(cluster_id, playbook, extra, node_vars):
    """Execute an Ansible Playbook in all cluster nodes.

    The CLUSTER_ID argument is the id of the cluster to execute the Ansible Playbook.
    """
    cluster_manager = get_cluster_manager()
    node_manager = get_node_manager()
    nodes = cluster_manager.get_all_cluster_nodes(cluster_id)
    nodes = node_manager.get_nodes_by_id(nodes)

    if not nodes:
        print("No nodes in the cluster")
        return 0

    extra_args = dict()
    for e in extra:
        if '=' not in e:
            raise ValueError(f"Invalid value for extra argument: `{e}`. "
                             f"Did you forgot '=' character?")
        extra_name, extra_value = e.split('=')[0], '='.join(e.split('=')[1:])
        extra_args[extra_name] = extra_value

    playbook = path_extend(playbook)
    if not os.path.isfile(playbook):
        raise ValueError(f"Invalid playbook file `{playbook}`")

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
        nodes, cluster_defaults.base_defaults.private_path, {}, node_variables)
    executor = AnsiblePlaybookExecutor(
        playbook, cluster_defaults.base_defaults.private_path, inventory, extra_args)
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


