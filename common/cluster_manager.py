import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from multiprocessing.pool import ThreadPool
from typing import Optional, Dict, Union, List, Tuple

import dacite

from common.configs import ConfigurationDatabase, InstanceInfo
from common.executor import SSHCommandExecutor, Executor, AnsiblePlaybookExecutor
from common.node_manager import NodeManager
from common.repository import Repository, InvalidEntryError
from common.role_manager import RoleManager
from common.utils import yaml_load, path_extend, get_logger, get_random_name, get_random_object

logger = get_logger(__name__)


class ClusterConfigurationError(Exception):
    pass


class ClusterError(Exception):
    pass


class ClusterSetupError(ClusterError):
    pass


class InvalidClusterError(Exception):
    def __init__(self, cluster_id: str):
        self.cluster_id = cluster_id
        super().__init__(f"Invalid cluster: {cluster_id}")


class InvalidSetupError(ClusterConfigurationError):
    def __init__(self, cluster_name: str, setup_name: str):
        self.cluster_name = cluster_name
        self.setup_name = setup_name
        super().__init__(f"Invalid setup named {setup_name} in cluster "
                         f"{cluster_name}")


class NodeSizeError(ClusterConfigurationError):
    pass


@dataclass
class RoleActionType:
    role: str
    action: str
    extra: Optional[Dict[str, str]] = field(default_factory=dict)


@dataclass
class CommandActionType:
    command: str


@dataclass
class PlaybookActionType:
    playbook: str
    extra: Optional[Dict[str, str]] = field(default_factory=dict)


ActionType = Union[RoleActionType, CommandActionType, PlaybookActionType]


@dataclass
class RoleAdd:
    name: str
    extra: Optional[Dict[str, str]] = field(default_factory=dict)


@dataclass
class SetupConfig:
    roles: Optional[List[RoleAdd]] = field(default_factory=list)
    actions: Optional[List[ActionType]] = field(default_factory=list)


@dataclass
class ClusterOptions:
    ssh_to: Optional[str] = None


@dataclass
class _NodeConfig:
    type: str
    count: int
    min_count: Optional[int] = None
    setups: List[str] = field(default_factory=list)


@dataclass
class _ClusterConfig:
    options: Optional[ClusterOptions]
    before_all: Optional[List[str]] = field(default_factory=list)
    before: Optional[List[str]] = field(default_factory=list)
    after_all: Optional[List[str]] = field(default_factory=list)
    after: Optional[List[str]] = field(default_factory=list)
    nodes: Optional[Dict[str, _NodeConfig]] = field(default_factory=dict)


@dataclass
class ClusterConfigFile:
    setups: Optional[Dict[str, SetupConfig]] = field(default_factory=dict)
    clusters: Optional[Dict[str, _ClusterConfig]] = field(default_factory=dict)


@dataclass
class NodeConfig:
    type: str
    count: int
    min_count: Optional[int] = None
    setups: List[SetupConfig] = field(default_factory=list)


@dataclass
class ClusterConfig:
    cluster_config_id: str
    options: Optional[ClusterOptions]
    before_all: Optional[List[SetupConfig]] = field(default_factory=list)
    before: Optional[List[SetupConfig]] = field(default_factory=list)
    after_all: Optional[List[SetupConfig]] = field(default_factory=list)
    after: Optional[List[SetupConfig]] = field(default_factory=list)
    nodes: Optional[Dict[str, NodeConfig]] = field(default_factory=dict)


def validate_valid_role():
    pass


def validate_valid_cluster():
    pass


class ClusterConfigDatabase:
    def __init__(self, cluster_files: List[str], discard_invalids: bool = True,
                 load: bool = True):
        self.cluster_files = cluster_files
        self.clusters: Dict[str, ClusterConfig] = {}
        self.setups: Dict[str, SetupConfig] = {}
        self._discard_invalids = discard_invalids
        if load:
            self.load()

    def _load_cluster_and_setups(self):
        clusters = {}
        setups = {}
        # Collect all cluster and setup configurations
        for cfile in self.cluster_files:
            try:
                cdata = yaml_load(cfile)
                cdata = dacite.from_dict(data_class=ClusterConfigFile, data=cdata)
                for cname, cconfig in cdata.clusters.items():
                    if cname in clusters:
                        logger.error(f"Redefinition of cluster {cname}. Skipping")
                        continue
                    clusters[cname] = cconfig
                for sname, sconfig in cdata.setups.items():
                    if sname in setups:
                        logger.error(f"Redefinition of setup {sname}. Skipping")
                        continue
                    setups[sname] = sconfig
            except Exception as e:
                if self._discard_invalids:
                    logger.error(e)
                    continue
                else:
                    raise

        return setups, clusters

    def load(self):
        setups, clusters = self._load_cluster_and_setups()
        self.setups = setups

        def _validate_setup_names(cname: str, setup_names: List[str]) -> \
                List[SetupConfig]:
            _setups = []
            for sname in setup_names:
                if sname not in self.setups:
                    raise InvalidSetupError(cname, sname)
                _setups.append(self.setups[sname])
            return _setups

        # Perform validations
        for cname, cconfig in clusters.items():
            # validate setups
            clusters[cname].before_all = _validate_setup_names(
                cname, cconfig.before_all)
            clusters[cname].before = _validate_setup_names(
                cname, cconfig.before)
            clusters[cname].after = _validate_setup_names(
                cname, cconfig.after)
            clusters[cname].after_all = _validate_setup_names(
                cname, cconfig.after_all)
            for nname, nconfig in cconfig.nodes.items():
                clusters[cname].nodes[nname].setups = \
                    _validate_setup_names(cname, nconfig.setups)

            # validate count and min_count
            for nname, nconfig in cconfig.nodes.items():
                if nconfig.count < 0:
                    raise NodeSizeError(f"In cluster {cname}: {nname}.count < 0")
                if nconfig.min_count is not None:
                    if nconfig.min_count < 0:
                        raise NodeSizeError(f"In cluster {cname}: {nname}.min_count < 0")
                    elif nconfig.min_count > nconfig.count:
                        raise NodeSizeError(f"In cluster {cname}: {nname}.min_count > "
                                            f"{nname}.count")
                else:
                    nconfig.min_count = nconfig.count

            # Validate cluster options
            if cconfig.options is not None:
                if cconfig.options.ssh_to is not None:
                    if cconfig.options.ssh_to not in cconfig.nodes:
                        raise ValueError(f"In cluster {cname}: invalid ssh_to "
                                         f"option's value: {cconfig.options.ssh_to}")

            data = asdict(cconfig)
            data['cluster_config_id'] = cname
            cluster = dacite.from_dict(data_class=ClusterConfig, data=data)
            self.clusters[cname] = cluster


@dataclass
class ClusterDescriptor:
    cluster_id: str
    cluster_name: str
    cluster_config: ClusterConfig
    creation_time: float
    update_time: float
    is_setup: bool = False


class ClusterRepositoryController:
    def __init__(self, repository: Repository):
        self.repository = repository

    def upsert_cluster(self, cluster: ClusterDescriptor):
        cluster.update_time = time.time()
        with self.repository.connect('clusters') as db:
            cluster_dict = asdict(cluster)
            db.upsert(cluster.cluster_id, cluster_dict)

    def remove_cluster(self, cluster_id: str):
        with self.repository.connect('clusters') as db:
            db.remove(cluster_id)

    def get_cluster_by_id(self, cluster_id: str) -> ClusterDescriptor:
        with self.repository.connect('clusters') as db:
            cdata = db.get(cluster_id)
            return dacite.from_dict(data_class=ClusterDescriptor, data=cdata)

    def get_all_clusters(self) -> List[ClusterDescriptor]:
        with self.repository.connect('clusters') as db:
            return [
                dacite.from_dict(data_class=ClusterDescriptor, data=cdata)
                for cid, cdata in db.get_all().items()
            ]


class ClusterManager:
    def __init__(self, node_manager: NodeManager, role_manager: RoleManager,
                 config_db: ConfigurationDatabase,
                 cluster_repository_controller: ClusterRepositoryController,
                 private_dir: str, cluster_tag_prefix: str = '.cluster:'):
        self.node_manager = node_manager
        self.role_manager = role_manager
        self.config_db = config_db
        self.cluster_repository = cluster_repository_controller
        self.private_dir = private_dir
        self.cluster_tag_prefix: str = cluster_tag_prefix

    def add_cluster_tag(self, node_ids: List[str], cluster_id: str,
                        node_type: str) -> List[str]:
        cluster_tag = f"{self.cluster_tag_prefix}{cluster_id}"
        added_nodes = []
        for n in self.node_manager.get_nodes_by_id(node_ids):
            tags = dict(n.tags)
            if cluster_tag in tags:
                node_types = set(tags[cluster_tag].split(','))
                node_types.add(node_type)
                tags[cluster_tag] = ','.join(sorted(node_types))
            else:
                tags[cluster_tag] = node_type
            n.tags = tags
            self.node_manager.upsert_node(n)
            added_nodes.append(n.node_id)
        return added_nodes

    def get_all_cluster_nodes(self, cluster_id: str) -> List[str]:
        cluster_tag = f"{self.cluster_tag_prefix}{cluster_id}"
        cluster_cond = lambda n: cluster_tag in n.tags
        return [n.node_id for n in self.node_manager.get_nodes(cluster_cond)]

    def get_cluster_nodes_types(self, cluster_id: str) -> Dict[str, List[str]]:
        cluster_tag = f"{self.cluster_tag_prefix}{cluster_id}"
        cluster_cond = lambda n: cluster_tag in n.tags
        nodes_dict = defaultdict(set)

        for node in self.node_manager.get_nodes(cluster_cond):
            for node_type in node.tags[cluster_tag].split(','):
                nodes_dict[node_type].add(node.node_id)

        # Set to list
        nodes = {
            node_type: list(node_set)
            for node_type, node_set in nodes_dict.items()
        }
        return nodes

    def get_cluster_by_id(self, cluster_id: str) -> ClusterDescriptor:
        try:
            return self.cluster_repository.get_cluster_by_id(cluster_id)
        except InvalidEntryError as e:
            raise InvalidClusterError(cluster_id) from e

    def get_all_clusters(self) -> List[ClusterDescriptor]:
        return self.cluster_repository.get_all_clusters()

    def start_cluster_node(self, cluster_id: str, node_type: str,
                           instance_info: InstanceInfo, count: int,
                           start_timeout: int = 600) -> List[str]:
        nodes = self.node_manager.start_node(instance_info, count, start_timeout)
        self.add_cluster_tag(nodes, cluster_id, node_type)
        return nodes

    def start_cluster(self, cluster_config: ClusterConfig,
                      start_timeout: int = 600,
                      max_workers: int = 1,
                      destroy_on_min_count: bool = True) -> ClusterDescriptor:
        node_types: Dict[str, Tuple[NodeConfig, InstanceInfo]] = {
            node_name: (node_values, self.config_db.instance_descriptors[node_values.type])
            for node_name, node_values in cluster_config.nodes.items()
        }

        creation_time = time.time()
        cluster = ClusterDescriptor(
            str(uuid.uuid4()), get_random_object(), cluster_config,
            creation_time, creation_time
        )

        def _start_cluster_node(node_type: str) -> Tuple[str, List[str]]:
            try:
                nconfig, instance = node_types[node_type]
                started_nodes = self.start_cluster_node(
                    cluster.cluster_id, node_type, instance, nconfig.count,
                    start_timeout)
                return node_type, started_nodes
            except Exception as e:
                logger.error(f'Error starting cluster node {node_type}: {e}')
                return node_type, []

        with ThreadPool(processes=max_workers) as pool:
            instances = pool.map(_start_cluster_node, node_types.keys())
            started_nodes: Dict[str, List[str]] = {
                node_type: nodes
                for node_type, nodes in instances
            }

        all_nodes = list({n for _, node_list in started_nodes.items() for n in node_list})
        alive_nodes = self.node_manager.is_alive(all_nodes, retries=15)
        not_alives = [n for n, status in alive_nodes.items() if not status]
        if not_alives:
            stopped_nodes = self.node_manager.stop_nodes(not_alives)
            logger.info(f"Stopped nodes: {', '.join(sorted(stopped_nodes))}")
            started_nodes = {
                node_type: [n for n in node_list if n not in not_alives]
                for node_type, node_list in started_nodes.items()
            }

        not_reached_nodes = []
        # Check if min_counts is reached, else destroy cluster
        for node_type, (nconfig, _) in node_types.items():
            nodes = started_nodes[node_type]
            if len(nodes) < nconfig.min_count:
                not_reached_nodes.append(node_type)
                logger.error(
                    f"Could not start the minimum nodes of type {node_type} of "
                    f"cluster {cluster_config.cluster_config_id}. "
                    f"Started nodes: {len(nodes)}; minimum: {nconfig.min_count}")

        if destroy_on_min_count and not_reached_nodes:
            nodes_to_stop = [n for nodes in started_nodes.values() for n in nodes]
            logger.error("Destroying cluster... Stopping all nodes: "
                         f"{', '.join(nodes_to_stop)}")
            self.node_manager.stop_nodes(nodes_to_stop)

        self.cluster_repository.upsert_cluster(cluster)
        return cluster

    def add_existing_nodes_to_cluster(self, cluster_id: str,
                                      node_types: Dict[str, List[str]],
                                      max_workers: int = 1):
        # Just to check if cluster exists...
        self.get_cluster_by_id(cluster_id)
        for node_type, node_list in node_types.items():
            self.add_cluster_tag(node_list, cluster_id, node_type)
        self.setup_cluster(cluster_id, node_types, max_workers)

    def run_action(self, action: ActionType, node_ids: List[str]) -> bool:
        try:
            nodes = self.node_manager.get_nodes_by_id(node_ids)
            if type(action) is CommandActionType:
                e = SSHCommandExecutor(action.command, nodes, self.private_dir)
                result = e.run()
                return result['ok']

            elif type(action) is RoleActionType:
                role_node_dict = self.role_manager.get_role_nodes(
                    action.role, from_node_ids=node_ids)
                result = self.role_manager.perform_action(
                    action.role, action.action, role_node_dict, extra_args=action.extra)
                return result.ok

            elif type(action) is PlaybookActionType:
                inventory = AnsiblePlaybookExecutor.create_inventory(
                    nodes, self.private_dir)
                e = AnsiblePlaybookExecutor(
                    action.playbook, self.private_dir, inventory, action.extra)
                result = e.run()
                return result.ok

            else:
                logger.error(f"Invalid action type: {type(action)}")
                return False
        except Exception as e:
            logger.error(e)
            return False

    def run_role_add(self, role: RoleAdd, node_ids: List[str]) -> bool:
        try:
            if '/' in role.name:
                host_map = {role.name.split('/')[1]: node_ids}
            else:
                host_map = node_ids
            added_nodes = self.role_manager.add_role(
                role.name, host_map, extra_args=role.extra)
            return all(n in added_nodes for n in node_ids)
        except Exception as e:
            logger.error(e)
            return False

    def run_setup(self, setup: SetupConfig, node_ids: List[str]) -> bool:
        logger.info(f"* Running setup {setup} at nodes: {node_ids}")
        for role in setup.roles:
            if not self.run_role_add(role, node_ids):
                return False
        for action in setup.actions:
            if not self.run_action(action, node_ids):
                return False
        return True

    def _run_setup_list(self, setups: List[SetupConfig], node_ids: List[str]) -> bool:
        logger.info(f"*** Running {len(setups)} setups at nodes: {node_ids}")
        for setup in setups:
            if not self.run_setup(setup, node_ids):
                return False
        return True

    def setup_cluster(self, cluster_id: str, nodes_types: Dict[str, List[str]] = None,
                      max_workers: int = 1, start_at_stage: str = 'before_all'):
        cluster = self.cluster_repository.get_cluster_by_id(cluster_id)
        cluster.is_setup = False
        self.cluster_repository.upsert_cluster(cluster)

        if not nodes_types:
            nodes_types = self.get_cluster_nodes_types(cluster_id)

        all_nodes = self.get_all_cluster_nodes(cluster_id)
        all_being_added = list(
            {n for _, list_nodes in nodes_types.items() for n in list_nodes}
        )
        stages = {
            'before_all': 1,
            'before': 2,
            'node': 3,
            'after': 4,
            'after_all': 5
        }

        start_at_stage = stages[start_at_stage]

        # Before all Stage
        if start_at_stage <= stages['before_all']:
            if not self._run_setup_list(cluster.cluster_config.before_all, all_nodes):
                raise ClusterSetupError(
                    f"Error setting up cluster {cluster_id} at 'before_all' stage")

        # Before Stage
        if start_at_stage <= stages['before']:
            if not self._run_setup_list(cluster.cluster_config.before, all_being_added):
                raise ClusterSetupError(
                    f"Error setting up cluster {cluster_id} at 'before' stage")

        # Node Stage
        if start_at_stage <= stages['node']:
            with ThreadPool(processes=max_workers) as pool:
                values: List[Tuple[List[SetupConfig], List[str]]] = [
                    (cluster.cluster_config.nodes[node_type].setups, node_list)
                    for node_type, node_list in nodes_types.items()
                ]
                results = pool.starmap(self._run_setup_list, values)

            if not all(results):
                raise ClusterSetupError(
                    f"Error setting up cluster {cluster_id} at 'node' stage")

        # After Stage
        if start_at_stage <= stages['after']:
            if not self._run_setup_list(cluster.cluster_config.after, all_being_added):
                raise ClusterSetupError(
                    f"Error setting up cluster {cluster_id} at 'after' stage")

        # After all Stage
        if start_at_stage <= stages['after_all']:
            if not self._run_setup_list(cluster.cluster_config.after_all, all_nodes):
                raise ClusterSetupError(
                    f"Error setting up cluster {cluster_id} at 'after all' stage")

        cluster.is_setup = True
        self.cluster_repository.upsert_cluster(cluster)

    def pause_cluster(self, cluster_id: str, timeout: int = 180,
                      max_workers: int = 1) -> List[str]:
        nodes = self.get_all_cluster_nodes(cluster_id)
        return self.node_manager.pause_nodes(
            nodes, timeout=timeout, max_workers=max_workers)

    def resume_cluster(self, cluster_id: str, timeout: int = 180,
                       max_workers: int = 1) -> List[str]:
        nodes = self.get_all_cluster_nodes(cluster_id)
        return self.node_manager.resume_nodes(
            nodes, timeout=timeout, max_workers=max_workers)

    def stop_cluster(self, cluster_id: str, timeout: int = 180,
                     max_workers: int = 1, remove_cluster: bool = True) -> List[str]:
        nodes = self.get_all_cluster_nodes(cluster_id)
        nodes = self.node_manager.stop_nodes(
            nodes, timeout=timeout, max_workers=max_workers)
        if remove_cluster:
            self.cluster_repository.remove_cluster(cluster_id)
        return nodes

    def is_alive(self, cluster_id: str, retries: int = 5,
                 wait_timeout: int = 30, update_timeout: int = 30,
                 max_workers: int = 1, test_command: str = 'echo "OK"') -> \
            Dict[str, bool]:
        nodes = self.get_all_cluster_nodes(cluster_id)
        return self.node_manager.is_alive(
            nodes, retries=retries, wait_timeout=wait_timeout,
            update_timeout=update_timeout, max_workers=max_workers,
            test_command=test_command)


if __name__ == '__main__':
    import json
    from dataclasses import asdict
    from common.repository import RepositoryFactory
    from common.utils import setup_log
    from common.node import NodeRepositoryController
    from providers.provider_ansible_aws import AnsibleAWSProvider

    setup_log(verbosity_level=1)
    node_repository_path = '/home/lopani/.clap/storage/nodes.db'
    private_path = '/home/lopani/.clap/private'
    cluster_file_path = '/home/lopani/.clap/configs/clusters/spits-cluster.yml'
    cluster_repository_path = '/home/lopani/.clap/storage/clusters.db'

    config_db = ConfigurationDatabase(
        providers_file='/home/lopani/.clap/configs/providers.yaml',
        logins_file='/home/lopani/.clap/configs/logins.yaml',
        instances_file='/home/lopani/.clap/configs/instances.yaml'
    )

    repository = RepositoryFactory().get_repository('sqlite', node_repository_path)
    repository_controller = NodeRepositoryController(repository)

    ansible_aws = AnsibleAWSProvider(private_path)
    node_manager = NodeManager(
        repository_controller, {'aws': ansible_aws}, private_path)

    role_manager = RoleManager(
        repository_controller,
        '/home/lopani/.clap/groups',
        '/home/lopani/.clap/groups/actions.d',
        '/home/lopani/.clap/private'
    )

    cluster_db = ClusterConfigDatabase([cluster_file_path])
    print(cluster_db.clusters)

    repository = RepositoryFactory().get_repository('sqlite', cluster_repository_path)
    cluster_repository_controller = ClusterRepositoryController(repository)

    cluster_manager = ClusterManager(
        node_manager, role_manager, config_db,
        cluster_repository_controller, private_path)

    cluster_config = cluster_db.clusters['spits-cluster']
    cluster = cluster_manager.start_cluster(cluster_config, max_workers=4)
    cluster = cluster_manager.get_all_clusters()[0]
    print(f"CLUSTER: {cluster}")
    all_cluster_node_types = cluster_manager.get_cluster_nodes_types(cluster.cluster_id)
    print(f"All cluster node types: {all_cluster_node_types}")
    all_cluster_nodes = cluster_manager.get_all_cluster_nodes(cluster.cluster_id)
    print(f"All cluster nodes: {all_cluster_nodes}")
    cluster_manager.setup_cluster(cluster.cluster_id, max_workers=1)
    print('setup ok')
    stopped_nodes = cluster_manager.stop_cluster(cluster.cluster_id)
    print(f'Stopped nodes: {stopped_nodes}')
