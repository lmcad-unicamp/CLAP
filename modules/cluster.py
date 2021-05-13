import glob
import time
from collections import defaultdict
from dataclasses import dataclass, asdict
from typing import List, Dict, Tuple, Union

from common.node import NodeStatus
from common.clap import AbstractModule, Runner
from common.config import Config as BaseDefaults
from common.repository import RepositoryController, Repository, InvalidEntryError, SQLiteRepository
from common.utils import get_random_name, path_extend, get_logger, Singleton

from ._cluster_conf import ClusterDescriptor
from .node import NodeModule
from .group import GroupModule

from ._cluster_conf import ClusterConfigReader, SetupConfig

logger = get_logger(__name__)


class ClusterDefaults(metaclass=Singleton):
    def __init__(self):
        self.base_defaults = BaseDefaults()
        self.cluster_prefix = 'cluster'
        self.cluster_repository_path = path_extend(self.base_defaults.storage_path, 'cluster.db')
        self.cluster_config_path = path_extend(self.base_defaults.configs_path, 'clusters')
        self.repository_type_cls = SQLiteRepository


class ClusterError(Exception):
    pass


class ClusterResizeError(ClusterError):
    pass


@dataclass
class ClusterInfo:
    cluster_id: str
    cluster_name: str
    cluster_config_name: str
    cluster_config: ClusterDescriptor
    creation_time: float
    update_time: float
    cluster_state: str

    def __str__(self):
        return f"id=`{self.cluster_id}` nickname=`{self.cluster_name}` configuration=`{self.cluster_config_name}` " \
               f"state=`{self.cluster_state}` created=`{self.creation_time}` last_update=`{self.update_time}`"

    def to_dict(self):
        d = asdict(self)
        d['cluster_config'] = self.cluster_config.to_dict()
        return d

    @staticmethod
    def from_dict(d: dict) -> 'ClusterInfo':
        cluster = ClusterInfo(**d)
        cluster.cluster_config = ClusterDescriptor.from_dict(d['cluster_config'])
        return cluster


@dataclass
class ClusterState:
    STATUS_UNKNOWN = 'unknown'
    STATUS_STARTED = 'started'
    STATUS_PAUSED = 'paused'


@dataclass
class ClusterControlData:
    cluster_index: int = 0


class ClusterRepositoryController(RepositoryController):
    def __init__(self, repository: Repository, cluster_prefix: str):
        super().__init__(repository)
        self.cluster_prefix = cluster_prefix

    def get_unique_cluster_id(self) -> str:
        with self.repository.connect('control') as db:
            try:
                control = ClusterControlData(**db.get('control'))
            except InvalidEntryError:
                control = ClusterControlData()

            index = control.cluster_index
            control.cluster_index += 1
            db.upsert('control', asdict(control))
            return f'{self.cluster_prefix}-{index}'

    def create_cluster(self, cluster_config_name: str, cluster_config: ClusterDescriptor,
                       cluster_name: str = '', cluster_state: str = ClusterState.STATUS_UNKNOWN):
        name = cluster_name or get_random_name([c.cluster_name for c in self.get_all_clusters()])
        cluster_id = self.get_unique_cluster_id()
        creation_time = time.time()
        cluster = ClusterInfo(
            cluster_id=cluster_id, cluster_name=name,
            cluster_config_name=cluster_config_name, cluster_config=cluster_config,
            creation_time=creation_time, update_time=creation_time,
            cluster_state=cluster_state
        )
        self.upsert_cluster(cluster)
        return cluster

    def get_cluster(self, cluster_id: str) -> ClusterInfo:
        with self.repository.connect('cluster') as db:
            return ClusterInfo.from_dict(db.get(cluster_id))

    def get_clusters(self, cluster_ids: List[str]) -> List[ClusterInfo]:
        with self.repository.connect('cluster') as db:
            return [ClusterInfo.from_dict(v) for v in db.get_multiple(cluster_ids).values()]

    def get_cluster_with_name(self, cluster_name: str) -> ClusterInfo:
        clusters = self.get_all_clusters()
        return next(iter([c for c in clusters if c.cluster_name == cluster_name]))

    def get_all_clusters(self) -> List[ClusterInfo]:
        with self.repository.connect('cluster') as db:
            return [ClusterInfo.from_dict(c) for c in db.get_all().values()]

    def upsert_cluster(self, cluster: ClusterInfo):
        cluster.update_time = time.time()
        with self.repository.connect('cluster') as db:
            db.upsert(cluster.cluster_id, cluster.to_dict())

    def remove_cluster(self, cluster_id: str):
        with self.repository.connect('cluster') as db:
            db.remove(cluster_id)


class ClusterModule(AbstractModule):
    module_name = 'cluster'
    module_version = '0.1.0'
    module_description = 'Execute and manage clusters'
    module_tags = ['clusters', 'instances']

    @staticmethod
    def get_module(**defaults_override) -> 'ClusterModule':
        module_defaults = ClusterDefaults()
        cluster_repository_path = defaults_override.get(
            'cluster_repository_path', module_defaults.cluster_repository_path)
        repository_type_cls = defaults_override.get('repository_type_cls', module_defaults.repository_type_cls)
        repository = repository_type_cls(cluster_repository_path)
        cluster_prefix = defaults_override.get('cluster_prefix', module_defaults.cluster_prefix)
        cluster_repository_operator = ClusterRepositoryController(repository, cluster_prefix)
        node_module = defaults_override.get('node_module', NodeModule.get_module())
        group_module = defaults_override.get('group_module', GroupModule.get_module())
        cluster_config_path = defaults_override.get('cluster_config_path', module_defaults.cluster_config_path)
        return ClusterModule(cluster_repository_operator, node_module, group_module, cluster_config_path)

    def __init__(self, repository: ClusterRepositoryController, node_module: NodeModule, group_module: GroupModule,
                 cluster_config_path: str):
        self.node_module = node_module
        self.group_module = group_module
        self.repository = repository
        self.cluster_config_path = cluster_config_path

    def add_nodes_to_cluster(self, cluster_id: str, node_types: Dict[str, Tuple[int, int]] = None) -> Dict[
        str, List[str]]:
        cluster = self.repository.get_cluster(cluster_id)
        node_types = node_types or {
            node_name: (node_values.min_count, node_values.count)
            for node_name, node_values in cluster.cluster_config.nodes.items()
        }
        # Expand
        node_types = [
            (node_name, cluster.cluster_config.nodes[node_name].type, node_values[0], node_values[1])
            for node_name, node_values in node_types.items()
        ]

        # discard zeros
        node_types = [
            (node_name, node_type, min_count, count)
            for node_name, node_type, min_count, count in node_types if count > 0
        ]

        if not node_types:
            return []

        # Group by node types
        grouped_node_types = defaultdict(list)
        for values in node_types:
            grouped_node_types[values[1]].append(values)
        grouped_node_types = dict(grouped_node_types)

        desired_nodes_to_start = {node_type: sum(v[3] for v in values) for node_type, values in
                                  grouped_node_types.items()}
        minimum_nodes_to_start = {node_type: sum(v[2] for v in values) for node_type, values in
                                  grouped_node_types.items()}

        # TODO: discard zeros
        started_nodes = self.node_module.start_nodes_by_instance_config_id(desired_nodes_to_start)

        # Group by nodes
        grouped_started_nodes = defaultdict(list)
        for node in self.node_module.get_nodes_by_id(started_nodes):
            grouped_started_nodes[node.configuration.instance.instance_config_id].append(node)

        # Check for unreachable nodes
        not_started_nodes = []
        for node_type, list_nodes in grouped_started_nodes.items():
            not_started_nodes += [node.node_id for node in list_nodes if node.status != NodeStatus.REACHABLE]
            grouped_started_nodes[node_type] = [node for node in list_nodes if
                                                node.status == NodeStatus.REACHABLE]

        # Check if any type if less than desired. If yes --> Fail
        nodes_fail = any(len(list_nodes) < minimum_nodes_to_start[node_type] for node_type, list_nodes in
                         grouped_started_nodes.items())

        # If some types have failed with less than minimum specified --> Failed to start cluster (stop all started nodes)
        if nodes_fail:
            self.node_module.stop_nodes(node_ids=started_nodes)
            raise ClusterResizeError("Nodes failed to start")

        # Stop the non-reachable nodes
        if not_started_nodes:
            self.node_module.stop_nodes(node_ids=not_started_nodes)

        partitioned_nodes = dict()
        # Perform partition
        # TODO check if minimum of each type was sucessfully started
        for node_type, node_values in grouped_node_types.items():
            nodes_to_partition = [node.node_id for node in grouped_started_nodes[node_type]]
            # Ensure the minimum quantity of nodes for each cluster_node type
            for cluster_node_name, _, minimum, _ in node_values:
                partitioned_nodes[cluster_node_name] = nodes_to_partition[:minimum]
                nodes_to_partition = nodes_to_partition[minimum:]
                if len(partitioned_nodes[cluster_node_name]) < minimum:
                    logger.error(f"Cluster `{cluster_id}` does not reached minimum nodes quantity. "
                                 f"Node type `{cluster_node_name}` has {len(partitioned_nodes[cluster_node_name])} but minimum was {minimum} "
                                 f"Stopping cluster `{cluster_id}`")
                    self.node_module.stop_nodes(started_nodes)
                    raise ClusterResizeError("Minimum nodes to start not reached")

            # Partitionate the remaining
            for cluster_node_name, _, minimum, desired in node_values:
                remaining = desired - minimum
                if remaining == 0:
                    continue
                # Request more than have to partitionate?
                if remaining >= len(nodes_to_partition):
                    partitioned_nodes[cluster_node_name] += nodes_to_partition
                    break
                else:
                    partitioned_nodes[cluster_node_name] += nodes_to_partition[:remaining]
                    nodes_to_partition = nodes_to_partition[remaining:]

        return self.add_existing_node_to_cluster(cluster.cluster_id, partitioned_nodes)

        # # Finish by tagging the nodes
        # for cluster_node_type, list_nodes in partitioned_nodes.items():
        #     tags = {
        #         'clusters': cluster.cluster_id,
        #         'cluster_node_type': f'{cluster.cluster_id}:{cluster_node_type}',
        #         'cluster_node_setup': f'{cluster.cluster_id}:{cluster_node_type}:no'
        #     }
        #     self.node_module.add_tag_to_nodes(list_nodes, tags)
        #
        # return partitioned_nodes

    def add_existing_node_to_cluster(self, cluster_id: str, node_types_ids: Dict[str, List[str]]) -> Dict[
        str, List[str]]:
        for cluster_node_type, list_nodes in node_types_ids.items():
            tags = {
                'clusters': cluster_id,
                f'{cluster_id}_type': f'{cluster_node_type}',
                f'{cluster_id}_setup': f'{cluster_node_type}:no'
            }
            self.node_module.add_tag_to_nodes(tags=tags, node_ids=list_nodes)
        return node_types_ids

    def remove_nodes_from_cluster_by_id(self, cluster_id: str, node_ids: List[str], stop_nodes: bool = True,
                                        remove_cluster: bool = False) -> List[str]:
        if not node_ids:
            raise ValueError("No nodes provided")
        cluster_nodes = self.get_nodes_from_cluster(cluster_id)
        invalid_nodes = [node_id for node_id in node_ids if node_id not in cluster_nodes]
        if invalid_nodes:
            raise Exception(f"Nodes `{', '.join(sorted(invalid_nodes))}` does not belong to cluster `{cluster_id}`")
        if stop_nodes:
            self.node_module.stop_nodes(node_ids)
        else:
            self.node_module.remove_tag_from_nodes(tags={'clusters': cluster_id, f'{cluster_id}_type': None,
                                                         f'{cluster_id}_setup': None}, node_ids=node_ids)

        if remove_cluster:
            if not self.get_nodes_from_cluster(cluster_id):
                self.repository.remove_cluster(cluster_id)

        return node_ids

    def remove_nodes_from_cluster_by_type(self, cluster_id: str, node_types: Dict[str, int], stop_nodes: bool = True,
                                          remove_cluster: bool = True) -> List[str]:
        cluster_nodes = self.get_nodes_from_cluster_by_type(cluster_id)
        # TODO
        nodes_to_remove = set()
        for node_type, qtde in node_types.items():
            try:
                if len(cluster_nodes[node_type]) < qtde:
                    raise IndexError(node_type)
                nodes_to_remove.update(cluster_nodes[node_type][:qtde])
            except IndexError:
                logger.error(f"Invalid quantity for node of type `{node_type}` at cluster `{cluster_id}`")
                raise
            except KeyError:
                logger.error(f"Invalid node of type `{node_type}` at cluster `{cluster_id}`")
                raise

        return self.remove_nodes_from_cluster_by_id(cluster_id, node_ids=list(nodes_to_remove), stop_nodes=stop_nodes,
                                                    remove_cluster=remove_cluster)

        # if remove_cluster:
        #     if not self.get_nodes_from_cluster(cluster_id):
        #         self.repository.remove_cluster(cluster_id)

    def create_cluster(self, cluster_name: str, extra_args: Dict[str, str] = None,
                       start_nodes: bool = True, cluster_path: str = None) -> str:
        cluster_files = glob.glob(path_extend(cluster_path if cluster_path else self.cluster_config_path, '*'))
        config_reader = ClusterConfigReader(cluster_files, extra=extra_args)
        cluster_config = config_reader.get_cluster_descriptor(cluster_name)
        cluster = self.repository.create_cluster(cluster_config_name=cluster_name, cluster_config=cluster_config)
        try:
            if start_nodes:
                self.add_nodes_to_cluster(cluster.cluster_id)
        except Exception as e:
            self.repository.remove_cluster(cluster.cluster_id)
            raise ClusterError(e)

        return cluster.cluster_id

    def update_cluster_config(self, cluster_id: str, extra_args: Dict[str, str] = None, cluster_path: str = None) -> str:
        cluster_files = glob.glob(path_extend(cluster_path if cluster_path else self.cluster_config_path, '*'))
        config_reader = ClusterConfigReader(cluster_files, extra=extra_args)
        cluster = self.repository.get_cluster(cluster_id)
        cluster.cluster_config = config_reader.get_cluster_descriptor(cluster.cluster_config_name)
        self.repository.upsert_cluster(cluster)
        return cluster_id

    def stop_cluster(self, cluster_id: str, stop_nodes: bool = True):
        node_ids = self.get_nodes_from_cluster(cluster_id)
        if node_ids:
            self.remove_nodes_from_cluster_by_id(cluster_id, node_ids, stop_nodes=stop_nodes)
        self.repository.remove_cluster(cluster_id)

    # TODO force_pause
    def pause_cluster(self, cluster_id: str, force_pause: bool = False) -> List[str]:
        node_ids = self.get_nodes_from_cluster(cluster_id)
        return self.node_module.pause_nodes(node_ids=node_ids) if node_ids else []

    def resume_cluster(self, cluster_id: str) -> List[str]:
        node_ids = self.get_nodes_from_cluster(cluster_id)
        return self.node_module.resume_nodes(node_ids=node_ids) if node_ids else []

    def alive_cluster(self, cluster_id: str) -> Dict[str, bool]:
        node_ids = self.get_nodes_from_cluster(cluster_id)
        return self.node_module.is_alive(node_ids=node_ids) if node_ids else {}

    def get_nodes_from_cluster(self, cluster_id: str) -> List[str]:
        cluster = self.repository.get_cluster(cluster_id)
        return [node.node_id for node in self.node_module.get_nodes_with_filter(
            key=lambda n: 'clusters' in n.tags and cluster_id in n.tags['clusters'])]

    def get_nodes_from_cluster_by_type(self, cluster_id: str) -> Dict[str, List[str]]:
        node_types_final = defaultdict(list)
        for node in self.node_module.get_nodes_by_id(self.get_nodes_from_cluster(cluster_id)):
            node_types = node.tags[f'{cluster_id}_type']
            for t in node_types:
                node_types_final[t].append(node.node_id)

        return dict(node_types_final)

    def _run_command(self, node_ids: List[str], command_string: str) -> Dict[str, Runner.CommandResult]:
        return self.node_module.execute_command_in_nodes(command=command_string, node_ids=node_ids)

    def _run_playbook(self, node_ids: List[str], playbook: str, extra: Dict[str, str]) -> Runner.PlaybookResult:
        return self.node_module.execute_playbook_in_nodes(
            playbook_path=playbook, group_hosts_map=node_ids, extra_args=extra)

    def _run_setup(self, node_ids: List[str], setup_name: str, setup_config: SetupConfig):
        logger.info(f"Performing setup `{setup_name}` at nodes `{', '.join(sorted(node_ids))}`....")
        # TODO
        for group in setup_config.groups:
            group_name, host_name = (group.name, '__default__') if '/' not in group.name else (
                group.name.split('/')[0], group.name.split('/')[1])
            extra = group.extra or {}
            self.group_module.add_group_to_nodes(group_name=group_name, group_hosts_map={host_name: node_ids},
                                                 extra_args=extra)
        # TODO
        for action in setup_config.actions:
            if action.type == 'action':
                group_name, host_name = (action.group, None) if '/' not in action.group else (
                    action.group.split('/')[0], action.group.split('/')[0])
                action_name = action.name
                extra = action.extra
                nodes_to_run = node_ids if not host_name else {host_name: node_ids}
                res = self.group_module.execute_group_action(group_name=group_name, action_name=action_name,
                                                             node_ids=nodes_to_run, extra_args=extra)
                if not res.ok:
                    raise Exception(f"Error executing action `{action_name}` from group `{group_name}`. "
                                    f"Returned with code {res.ret_code}")

            elif action.type == 'command':
                executions = self._run_command(node_ids, action.command)
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

            elif action.type == 'playbook':
                playbook = action.path
                extra = action.extra
                ret_val = self._run_playbook(node_ids=node_ids, playbook=playbook, extra=extra)
                if not ret_val.ok:
                    raise Exception(f"Playbook at `{playbook}` did not executed successfully "
                                    f"(return with code {ret_val.ret_code})")
            else:
                raise Exception(f"Invalid action type {action['type']}")

    def execute_setup(self, node_ids: List[str], setup_name: str, extra_args: Dict[str, str] = None):
        cluster_files = glob.glob(path_extend(self.cluster_config_path, '*'))
        config_reader = ClusterConfigReader(cluster_files, extra=extra_args)
        setup = config_reader.get_setup_config(setup_name)
        self._run_setup(node_ids, setup_name, setup)

    def cluster_setup(self, cluster_id: str, nodes_type: Dict[str, List[str]] = None, re_add_to_group: bool = False,
                      at: str = 'before_all'):
        cluster = self.repository.get_cluster(cluster_id)
        cluster_nodes = self.get_nodes_from_cluster_by_type(cluster_id)

        # If not nodes, perform in all cluster nodes!
        if not nodes_type:
            nodes_type = cluster_nodes

        invalid_node_types = [t for t in nodes_type if t not in cluster.cluster_config.nodes.keys()]
        if invalid_node_types:
            raise Exception(f"Invalid node types `{', '.join(sorted(invalid_node_types))}`")

        new_nodes = list(set([node_id for node_list in nodes_type.values() for node_id in node_list]))
        all_cluster_nodes = list(set([node_id for node_list in cluster_nodes.values() for node_id in node_list]))

        setups = ['before_all', 'before', 'node', 'after', 'after_all']
        if at not in setups:
            raise Exception(f"Invalid phase to start setup: `{at}`")

        setups = setups[setups.index(at):]
        setups_to_execute = []

        if 'before_all' in setups:
            for before_setup in cluster.cluster_config.before_all:
                if all_cluster_nodes:
                    setups_to_execute.append((all_cluster_nodes, before_setup[0], before_setup[1]))
        if 'before' in setups:
            for before_setup in cluster.cluster_config.before:
                if new_nodes:
                    setups_to_execute.append((new_nodes, before_setup[0], before_setup[1]))
        if 'node' in setups:
            for node_name, node_list in nodes_type.items():
                for setup in cluster.cluster_config.nodes[node_name].setups:
                    if node_list:
                        setups_to_execute.append((node_list, setup[0], setup[1]))
        if 'after' in setups:
            for after_setup in cluster.cluster_config.after:
                if new_nodes:
                    setups_to_execute.append((new_nodes, after_setup[0], after_setup[1]))
        if 'after_all' in setups:
            for after_setup in cluster.cluster_config.after_all:
                if all_cluster_nodes:
                    setups_to_execute.append((all_cluster_nodes, after_setup[0], after_setup[1]))

        for execute_args in setups_to_execute:
            # TODO skip zeros
            self._run_setup(*execute_args)

        for node_type, list_nodes in nodes_type.items():
            self.node_module.remove_tag_from_nodes(tags={f'{cluster_id}_setup': f'{node_type}:no'}, node_ids=list_nodes)
            self.node_module.add_tag_to_nodes(tags={f'{cluster_id}_setup': f'{node_type}:yes'}, node_ids=list_nodes)

    def get_clusters(self, cluster_ids: List[str]) -> List[ClusterInfo]:
        return self.repository.get_clusters(cluster_ids)

    def get_all_clusters(self) -> List[ClusterInfo]:
        return self.repository.get_all_clusters()

    def list_clusters(self, cluster_ids: List[str] = None) -> List[ClusterInfo]:
        return self.get_clusters(cluster_ids=cluster_ids)

    def group_add_by_type(self, cluster_id: str, group_name: str,
                          group_host_type: Union[List[str], Dict[str, List[str]]],
                          extra_args: Dict[str, str] = None) -> List[str]:
        nodes = self.get_nodes_from_cluster_by_type(cluster_id)
        if type(group_host_type) is list:
            nodes_map = set()
            for cluster_type in group_host_type:
                nodes_map.update(nodes[cluster_type])
            nodes_map = list(nodes_map)

        elif type(group_host_type) is dict:
            nodes_map = defaultdict(list)
            for group_type, list_cluster_type in group_host_type.items():
                values = set()
                for cluster_type in list_cluster_type:
                    values.update(nodes[cluster_type])
                nodes_map[group_type] = list(values)
            nodes_map = dict(nodes_map)
        else:
            raise TypeError(f"Invalid type `{type(group_host_type)}` for group_host_type")

        return self.group_module.add_group_to_nodes(group_name=group_name, group_hosts_map=nodes_map, extra_args=extra_args)

    def group_action(self, cluster_id: str, group_name: str, action: str, extra_args: Dict[str, str] = None) -> Runner.PlaybookResult:
        node_ids = self.get_nodes_from_cluster(cluster_id)
        return self.group_module.execute_group_action(group_name=group_name, action_name=action, node_ids=node_ids,
                                                      extra_args=extra_args)

    def execute_command(self, cluster_id: str, command: str) -> Dict[str, Runner.CommandResult]:
        node_ids = self.get_nodes_from_cluster(cluster_id)
        return self._run_command(node_ids=node_ids, command_string=command)

    def execute_playbook(self, cluster_id: str, playbook: str, extra_args: Dict[str, str]) -> Runner.PlaybookResult:
        node_ids = self.get_nodes_from_cluster(cluster_id)
        return self._run_playbook(node_ids=node_ids, playbook=playbook, extra=extra_args)

    def connect(self, cluster_id: str):
        cluster = self.get_clusters(cluster_ids=[cluster_id])[0]
        if cluster.cluster_config.options.ssh_to:
            ssh_node_types = self.get_nodes_from_cluster_by_type(cluster_id)
            try:
                node_id = ssh_node_types[cluster.cluster_config.options.ssh_to][0]
            except (IndexError, KeyError):
                raise ClusterError(f"No nodes of type `{cluster.cluster_config.options.ssh_to}`")
        else:
            ssh_nodes = self.get_nodes_from_cluster(cluster_id)
            try:
                node_id = ssh_nodes[0]
            except IndexError:
                raise ClusterError(f"No nodes in cluster `{cluster_id}`")

        self.node_module.connect_to_node(node_id)



if __name__ == '__main__':
    cluster_module = ClusterModule.get_module()
    cluster_id = cluster_module.create_cluster('my-cool-cluster')
    cluster = cluster_module.get_cluster(cluster_id)[cluster_id]
    cluster_module.update_cluster_config(
        ['/home/napoli/.clap/configs/clusters/cluster-example.yml',
         '/home/napoli/.clap/configs/clusters/cluster-example-2.yml'],
        cluster.cluster_id
    )

    cluster_module.cluster_setup(cluster.cluster_id)
    cluster_module.stop_cluster(cluster.cluster_id)
