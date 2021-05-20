import time
from multiprocessing.pool import ThreadPool
from typing import Dict, List, Tuple, Callable

from common.abstract_provider import AbstractInstanceProvider
from common.configs import InstanceInfo
from common.executor import SSHCommandExecutor
from common.node import NodeRepositoryController, NodeDescriptor, NodeStatus
from common.utils import get_logger, sorted_groupby

logger = get_logger(__name__)


class InvalidProvider(Exception):
    pass


class UnhandledProviderError(Exception):
    def __init__(self, provider: str):
        super().__init__(f'Unhandled provider {provider}')


class DeploymentError(Exception):
    pass


class NodeManager:
    def __init__(self, node_repository_controller: NodeRepositoryController,
                 providers: Dict[str, AbstractInstanceProvider],
                 private_dir: str):
        self.node_repository = node_repository_controller
        self.providers = providers
        self.private_path = private_dir

    # Group by functions
    @staticmethod
    def _group_instances_by_provider(instances: List[Tuple[InstanceInfo, int]]) -> \
            Dict[str, List[Tuple[InstanceInfo, int]]]:
        return sorted_groupby(instances, key=lambda x: x[0].provider.provider)

    @staticmethod
    def group_nodes_by_provider(nodes: List[NodeDescriptor]) -> \
            Dict[str, List[NodeDescriptor]]:
        return sorted_groupby(
            nodes, key=lambda x: x.configuration.provider.provider)

    # Get nodes
    def get_nodes_by_id(self, node_ids: List[str]) -> List[NodeDescriptor]:
        return self.node_repository.get_nodes_by_id(node_ids)

    def get_nodes(self, filter_func: Callable[[NodeDescriptor], bool],
                  from_node_ids: List[str] = None) -> List[NodeDescriptor]:
        nodes = self.node_repository.get_nodes_filter(filter_func)
        if from_node_ids:
            nodes = [n for nid, n in nodes if nid in from_node_ids]
        return nodes

    def get_all_nodes(self) -> List[NodeDescriptor]:
        return self.node_repository.get_all_nodes()

    # Other useful filter functions
    def get_not_running_nodes(self, from_node_ids: List[str] = None) -> \
            List[NodeDescriptor]:
        not_running_nodes_filter: Callable[[NodeDescriptor], bool] = \
            lambda n: n.status == NodeStatus.UNKNOWN or \
                      n.status == NodeStatus.PAUSED or \
                      n.status == NodeStatus.STOPPED
        return self.get_nodes(not_running_nodes_filter, from_node_ids)

    def get_up_nodes(self, from_node_ids: List[str] = None) -> \
            List[NodeDescriptor]:
        up_nodes_filter: Callable[[NodeDescriptor], bool] = \
            lambda n: n.status == NodeStatus.STARTED or \
                      n.status == NodeStatus.REACHABLE or \
                      n.status == NodeStatus.UNREACHABLE
        return self.get_nodes(up_nodes_filter, from_node_ids)

    def get_reachable_nodes(self, from_node_ids: List[str] = None) -> \
            List[NodeDescriptor]:
        reachable_nodes_filter: Callable[[NodeDescriptor], bool] = \
            lambda n: n.status == NodeStatus.REACHABLE
        return self.get_nodes(reachable_nodes_filter, from_node_ids)

    def get_nodes_with_tag(self, key: str, from_node_ids: List[str] = None) -> \
            List[NodeDescriptor]:
        tagged_nodes_filter: Callable[[NodeDescriptor], bool] = \
            lambda n: key in n.tags
        return self.get_nodes(tagged_nodes_filter, from_node_ids)

    def get_nodes_with_tag_value(self, key: str, value: str,
                                 from_node_ids: List[str] = None) -> \
            List[NodeDescriptor]:
        tagged_nodes_filter: Callable[[NodeDescriptor], bool] = \
            lambda n: n.tags.get(key, None) == value
        return self.get_nodes(tagged_nodes_filter, from_node_ids)

    # Provisioning functions
    # TODO provide an async function
    def start_node(self, instance: InstanceInfo, count: int = 1,
                   start_timeout: int = 600) -> List[str]:
        if count < 0:
            raise ValueError(f"Invalid number of nodes to start: {count}")
        if count == 0:
            return []
        provider_obj = self.providers.get(instance.provider.provider, None)
        if provider_obj is None:
            raise UnhandledProviderError(
                f"Unhandled provider: {instance.provider.provider}")
        nodes = provider_obj.start_instances(
            instance, count, timeout=start_timeout)
        for n in nodes:
            self.node_repository.upsert_node(n)
        return [n.node_id for n in nodes]

    def start_nodes(self, instance_counts: List[Tuple[InstanceInfo, int]],
                    start_timeout: int = 600,
                    connection_retries: int = 15,
                    retry_timeout: int = 30,
                    terminate_not_alive: bool = False,
                    max_workers: int = 1) -> List[str]:
        if not instance_counts:
            return []

        provider_instances = self._group_instances_by_provider(instance_counts)

        for p in provider_instances.keys():
            if p not in self.providers:
                raise UnhandledProviderError(f"Unhandled provider: {p}")

        started_instances: List[str] = []

        def start(provider_obj: AbstractInstanceProvider,
                  instance: InstanceInfo, count: int) -> List[str]:
            # Start instances
            nodes = provider_obj.start_instances(
                instance, count, timeout=start_timeout)
            # Insert new created nodes in repository
            for n in nodes:
                self.node_repository.upsert_node(n)
            return [n.node_id for n in nodes]

        # Parallel node start, by provider
        with ThreadPool(processes=max_workers) as pool:
            values = [
                (self.providers[provider], instance, count)
                for provider, list_instance_count in provider_instances.items()
                for (instance, count) in list_instance_count
            ]

            instances = pool.starmap(start, values)
            started_instances = [i for list_instances in instances for i in list_instances]

        if not started_instances:
            raise DeploymentError('No nodes were started')

        logger.info(f"Started {len(started_instances)} nodes: "
                    f"{', '.join(sorted(started_instances))}")

        # Check created nodes aliveness
        if connection_retries > 0:
            alive_nodes = self.is_alive(
                node_ids=started_instances, retries=connection_retries,
                wait_timeout=retry_timeout)
            not_alives = [nid for nid, status in alive_nodes.items() if not status]
            if terminate_not_alive and not_alives:
                logger.warning(f'Nodes {", ".join(sorted(not_alives))} are not '
                               f'alive and being terminated')
                self.stop_nodes(not_alives)
                started_instances = [
                    nid for nid, status in alive_nodes.items() if status
                ]

        return started_instances

    def is_alive(self, node_ids: List[str], retries: int = 5,
                 wait_timeout: int = 30, update_timeout: int = 30,
                 max_workers: int = 1, test_command: str = 'echo "OK"') -> \
            Dict[str, bool]:
        if not node_ids:
            return dict()

        nodes = self.get_nodes_by_id(node_ids)
        provider_nodes = self.group_nodes_by_provider(nodes)
        checked_nodes = dict()

        def update_node_info(provider_obj: AbstractInstanceProvider,
                             nodes: List[NodeDescriptor]) -> Dict[str, str]:
            # Update node information
            nodes = provider_obj.update_instance_info(nodes, update_timeout)
            # Update repository with new info
            for node in nodes:
                self.node_repository.upsert_node(node)
            return {node.node_id: node.status for node in nodes}

        # Parallel update_info, grouped by provider
        with ThreadPool(processes=max_workers) as pool:
            values = [
                (self.providers[provider], list_nodes)
                for provider, list_nodes in provider_nodes.items()
            ]

            instances = pool.starmap(update_node_info, values)
            for i in instances:
                checked_nodes.update(i)

        # Filter for not running nodes
        not_running = lambda n: n == NodeStatus.UNKNOWN or \
                                n == NodeStatus.PAUSED or \
                                n == NodeStatus.UNREACHABLE or \
                                n == NodeStatus.STOPPED

        not_running_nodes = {
            node: not_running(status)
            for node, status in checked_nodes.items()
        }
        not_running_nodes.update({
            node_id: True
            for node_id in node_ids if node_id not in checked_nodes
        })

        # No nodes running?
        if all(not_running_nodes.values()):
            return {nid: False for nid, status in checked_nodes.items()}

        node_status = {
            node: False
            for node, status in not_running_nodes.items() if status
        }
        # Filter for not running nodes
        unreachable = lambda n: n == NodeStatus.UNKNOWN or \
                                n == NodeStatus.STARTED or \
                                n == NodeStatus.REACHABLE

        successfully_reachables = []
        unreachables_yet = [nid for nid, status in checked_nodes.items()
                            if unreachable(status)]

        # Test SSH for nodes
        for i in range(retries):
            logger.info(f"Checking if nodes {', '.join(sorted(unreachables_yet))} "
                        f"are alive (retries: {i+1}/{retries})")
            nodes = self.get_nodes_by_id(unreachables_yet)
            cmd = SSHCommandExecutor(
                test_command, nodes, self.private_path)
            cmd_res = cmd.run()

            for node in nodes:
                cmd_status = cmd_res[node.node_id]
                # Command successfully executed -> Node is reachable
                if cmd_status['ok']:
                    if cmd_status['return_code'] == 0:
                        node.status = NodeStatus.REACHABLE
                        successfully_reachables.append(node.node_id)
                        unreachables_yet.remove(node.node_id)
                    else:
                        node.status = NodeStatus.UNREACHABLE
                    self.node_repository.upsert_node(node)
                else:
                    logger.error(
                        f'Error executing command in {node.node_id[:8]}: '
                        f'{cmd_status["error"]}.'
                    )

            # All nodes were reachable or no more retries left?
            if not unreachables_yet or i == retries-1:
                break
            # Retry
            else:
                logger.info(f"Nodes: {', '.join(sorted(unreachables_yet))} are "
                            f"unreachable. Testing connection again in "
                            f"{wait_timeout} seconds...")
            time.sleep(wait_timeout)

        # Return node status
        node_status.update({
            nid: nid in successfully_reachables
            for nid in checked_nodes.keys()
        })
        return node_status

    def stop_nodes(self, node_ids: List[str], timeout: int = 180,
                   max_workers: int = 1, remove_nodes: bool = True) -> List[str]:
        if not node_ids:
            return []

        nodes = self.get_nodes_by_id(node_ids)
        provider_nodes = self.group_nodes_by_provider(nodes)

        def stop_nodes(provider_obj: AbstractInstanceProvider,
                       nodes: List[NodeDescriptor]) -> List[str]:
            try:
                stoppeds = provider_obj.stop_instances(nodes, timeout)
                for n in stoppeds:
                    self.node_repository.upsert_node(n)
                return [n.node_id for n in stoppeds]
            except Exception as e:
                logger.error(e)
                return []

        with ThreadPool(processes=max_workers) as pool:
            values = [
                (self.providers[provider], list_nodes)
                for provider, list_nodes in provider_nodes.items()
            ]

            instances = pool.starmap(stop_nodes, values)
            stopped_nodes = [i for ilist in instances for i in ilist]

        if len(stopped_nodes) == len(node_ids):
            logger.info(f"Nodes: {', '.join(sorted(stopped_nodes))} were "
                        f"successfully stopped")
        else:
            logger.info(f"Some nodes were not sucessfully stopped: "
                        f"{', '.join(sorted(list(set(node_ids).difference(stopped_nodes))))}")

        if remove_nodes:
            self.node_repository.remove_nodes(stopped_nodes)

        return stopped_nodes

    def resume_nodes(self, node_ids: List[str],
                     timeout: int = 600,
                     connection_retries: int = 10,
                     retry_timeout: int = 30,
                     max_workers: int = 1) -> List[str]:
        if not node_ids:
            return []

        nodes = self.get_nodes_by_id(node_ids)
        provider_nodes = self.group_nodes_by_provider(nodes)

        def resume_nodes(provider_obj: AbstractInstanceProvider,
                         nodes: List[NodeDescriptor]) -> List[str]:
            resumeds = provider_obj.resume_instances(nodes, timeout=timeout)
            for node in resumeds:
                self.node_repository.upsert_node(node)
            return [n.node_id for n in resumeds]

        with ThreadPool(processes=max_workers) as pool:
            values = [
                (self.providers[provider], list_nodes)
                for provider, list_nodes in provider_nodes.items()
            ]

            instances = pool.starmap(resume_nodes, values)
            resumed_nodes = [i for ilist in instances for i in ilist]

        logger.info(f"Nodes: {', '.join(sorted(resumed_nodes))} were "
                    f"successfully resumed")
        if connection_retries > 0:
            self.is_alive(resumed_nodes, retries=connection_retries,
                          wait_timeout=retry_timeout)

        return resumed_nodes

    def pause_nodes(self, node_ids: List[str], timeout: int = 180,
                    max_workers: int = 1) -> List[str]:
        if not node_ids:
            return []
        nodes = self.get_nodes_by_id(node_ids)
        provider_nodes = self.group_nodes_by_provider(nodes)

        def pause_nodes(provider_obj: AbstractInstanceProvider,
                        nodes: List[NodeDescriptor]) -> List[str]:
            pauseds = provider_obj.pause_instances(nodes, timeout=timeout)
            for node in pauseds:
                self.node_repository.upsert_node(node)
            return [n.node_id for n in pauseds]

        with ThreadPool(processes=max_workers) as pool:
            values = [
                (self.providers[provider], list_nodes)
                for provider, list_nodes in provider_nodes.items()
            ]

            instances = pool.starmap(pause_nodes, values)
            paused_nodes = [i for ilist in instances for i in ilist]

        logger.info(f"Nodes: {', '.join(sorted(paused_nodes))} were "
                    f"successfully paused")
        return paused_nodes

    # TODO find usages
    def add_tags(self, node_ids: List[str], tags: Dict[str, str]):
        if not node_ids:
            raise ValueError("No nodes to perform operation")
        if not tags:
            return
        for node in self.get_nodes_by_id(node_ids):
            node.tags.update(tags)
            self.node_repository.upsert_node(node)

    # TODO find usages
    def remove_tags(self, node_ids: List[str], tags: List[str]):
        if not node_ids:
            raise ValueError("No nodes to perform operation")
        if not tags:
            return
        for node in self.get_nodes_by_id(node_ids):
            for tag in tags:
                node.tags.pop(tag, None)
            self.node_repository.upsert_node(node)

    def upsert_node(self, node: NodeDescriptor):
        self.node_repository.upsert_node(node)

    def remove_node(self, node_id: str):
        self.node_repository.remove_node(node_id)


if __name__ == '__main__':
    import json
    from common.configs import ConfigurationDatabase
    from common.node import NodeRepositoryController
    from common.repository import RepositoryFactory
    from common.utils import setup_log
    from providers.provider_ansible_aws import AnsibleAWSProvider
    setup_log(verbosity_level=1)

    c = ConfigurationDatabase(
     providers_file='/home/lopani/.clap/configs/providers.yaml',
     logins_file='/home/lopani/.clap/configs/logins.yaml',
     instances_file='/home/lopani/.clap/configs/instances.yaml'
    )

    type_a_instance = c.instance_descriptors['type-a']
    type_b_instance = c.instance_descriptors['type-b']
    print(type_a_instance)
    print(type_b_instance)

    node_repository_path = '/home/lopani/.clap/storage/nodes.db'
    private_path = '/home/lopani/.clap/private'
    repository = RepositoryFactory().get_repository('sqlite', node_repository_path)
    repository_controller = NodeRepositoryController(repository)
    ansible_aws = AnsibleAWSProvider(private_path)
    node_manager = NodeManager(
        repository_controller, {'aws': ansible_aws}, private_path)

    # node_manager.start_nodes(
    #     [(type_a_instance, 1), (type_b_instance, 1)], max_workers=4)

    node_ids = [node.node_id for node in node_manager.get_all_nodes()]
    print(f'Get {len(node_ids)} nodes: {node_ids}')
    res = node_manager.is_alive(node_ids)
    print(f'Result ({len(res)} nodes): {res}')

    x = SSHCommandExecutor('env', node_manager.get_nodes_by_id(node_ids),
                           private_path)
    res = x.run()

    for node_id, result in res.items():
        print(node_id)
        print(json.dumps(result, indent=4, sort_keys=True))

    # res = node_manager.stop_nodes(node_ids)
    # print(f'Stopped {len(res)} nodes: {res}')

    # node_ids = node_manager.start_nodes(
    #     [(type_a_instance, 1), (type_b_instance, 1)], max_workers=4)
    # nodes = node_manager.get_all_nodes()
    # x = SSHCommandExecutor('ls -lha ~', nodes, private_path)
    # res = x.run()
    # print(res)
    # node_manager.pause_nodes(node_ids)