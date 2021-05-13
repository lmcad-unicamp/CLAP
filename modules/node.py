import concurrent.futures
import multiprocessing

import jinja2
import os
import time

from typing import List, Dict, Union, Tuple, Callable
from paramiko import SSHClient
from itertools import groupby

from common.config import Config as BaseDefaults
from common.node import NodeRepositoryController, NodeDescriptor, NodeStatus, \
    get_local_node
from common.provider import AbstractModule, AbstractInstanceProvider, Runner
from common.repository import SQLiteRepository, InvalidEntryError
from common.schemas import ConfigurationDatabase, InstanceInfo, ProviderConfig, LoginConfig, InstanceConfigAWS, \
    YAMLConfigurationDatabase, ProviderConfigLocal
from common.utils import path_extend, get_logger, Singleton, get_random_name

from drivers.provider_ansible_aws import AnsibleAWSProvider

logger = get_logger(__name__)


class InvalidProvider(Exception):
    pass


class EmptyNodeList(Exception):
    pass


class InvalidNode(Exception):
    pass


class NodeDefaults(metaclass=Singleton):
    def __init__(self):
        self.base_defaults = BaseDefaults()
        self.node_repository_path = path_extend(self.base_defaults.storage_path, 'nodes.db')
        self.repository_type_cls = SQLiteRepository
        self.configuration_reader_type_cls = YAMLConfigurationDatabase
        self.providers_path = path_extend(self.base_defaults.configs_path, 'providers.yaml')
        self.logins_path = path_extend(self.base_defaults.configs_path, 'logins.yaml')
        self.instances_path = path_extend(self.base_defaults.configs_path, 'instances.yaml')
        self.instance_providers_cls = {
            AnsibleAWSProvider.provider: AnsibleAWSProvider
        }
        self.templates_path = path_extend(os.path.dirname(os.path.abspath(__file__)), 'templates')


class NodeModule(AbstractModule):
    module_name = 'node'
    module_version = '0.1.0'
    module_description = 'Execute and manage modules'
    module_tags = ['instance']

    @staticmethod
    def get_module(**defaults_override) -> 'NodeModule':
        module_defaults = NodeDefaults()
        node_repository_path = defaults_override.get('node_repository_path', module_defaults.node_repository_path)
        providers_path = defaults_override.get('providers_path', module_defaults.providers_path)
        logins_path = defaults_override.get('logins_path', module_defaults.logins_path)
        instances_path = defaults_override.get('instances_path', module_defaults.instances_path)
        templates_path = defaults_override.get('templates_path', module_defaults.templates_path)
        private_path = defaults_override.get('private_path', module_defaults.base_defaults.private_path)
        verbosity = defaults_override.get('verbosity', module_defaults.base_defaults.verbosity)

        repository_type_cls = defaults_override.get('repository_type_cls', module_defaults.repository_type_cls)
        configuration_reader_type_cls = defaults_override.get(
            'configuration_reader_type_cls', module_defaults.configuration_reader_type_cls)
        instance_providers_cls = defaults_override.get('instance_providers_cls', module_defaults.instance_providers_cls)

        repository_operator = NodeRepositoryController(repository_type_cls(node_repository_path))
        config_reader = configuration_reader_type_cls(providers_path, logins_path, instances_path)
        providers = {
            provider_name: provider_cls(repository_operator, verbosity)
            for provider_name, provider_cls in instance_providers_cls.items()
        }
        runner = Runner(private_path, verbosity)

        return NodeModule(repository_operator, config_reader, providers, runner, templates_path)

    def __init__(self, node_repository: NodeRepositoryController, config_reader: ConfigurationDatabase,
                 providers: Dict[str, AbstractInstanceProvider], runner: Runner, templates_path: str):
        self.node_repository_operator = node_repository
        self.config_reader = config_reader
        self.providers = providers
        self.runner_provider = runner
        self.templates_path = templates_path
        self.jinjaenv = jinja2.Environment(loader=jinja2.FileSystemLoader(self.templates_path), trim_blocks=True,
                                           lstrip_blocks=True)

    @staticmethod
    def __group_instances_by_provider__(instances: List[Tuple[InstanceInfo, int]]) -> \
            Dict[str, List[Tuple[InstanceInfo, int]]]:
        # return {provider: [(instance-1, count), (instance-2, count) ... ]}
        return {k: list(v) for k, v in groupby(instances, lambda x: x[0].provider.provider)}

    @staticmethod
    def __group_nodes_by_provider__(nodes: List[NodeDescriptor]) -> Dict[str, List[NodeDescriptor]]:
        # return {provider: [(instance-1, count), (instance-2, count) ... ]}
        return {k: list(v) for k, v in groupby(nodes, lambda x: x.configuration.provider.provider)}

    def __get_existing_nodes__(self, node_ids: List[str] = None, another_filter: Callable[[NodeDescriptor], bool] = None,
                               unique: bool = True) -> List[NodeDescriptor]:
        if not node_ids and not another_filter:
            raise EmptyNodeList("No nodes provided")
        nodes = []
        if node_ids:
            nodes += self.get_nodes_by_id(node_ids)
        if another_filter:
            nodes += self.get_nodes_with_filter(another_filter, unique=False)
        if not nodes:
            raise EmptyNodeList("No nodes to perform operation")
        return self.__unique_nodes__(nodes) if unique else nodes

    @staticmethod
    def __unique_nodes__(nodes: List[NodeDescriptor]) -> List[NodeDescriptor]:
        d = {node.node_id: node for node in nodes}
        return list(d.values())

    def get_nodes_by_id(self, node_ids: List[str]) -> List[NodeDescriptor]:
        try:
            return self.node_repository_operator.get_nodes_by_id(node_ids)
        except InvalidEntryError as e:
            raise InvalidNode(e)

    def get_all_nodes(self):
        return self.node_repository_operator.get_all_nodes()

    def get_nodes_with_filter(self, key: Callable[[NodeDescriptor], bool], unique: bool = True) -> List[NodeDescriptor]:
        all_nodes = [node for node in self.get_all_nodes() if key(node)]
        return self.__unique_nodes__(all_nodes) if unique else all_nodes

    def start_nodes_by_instance_descriptor(self, instance_counts: List[Tuple[InstanceInfo, int]],
                                           start_timeout: int = 600, connection_retries: int = 15,
                                           retry_timeout: float = 30.0, terminate_not_alive: bool = False) -> List[str]:
        grouped_instances = self.__group_instances_by_provider__(instance_counts)
        started_instances = []
        invalid_providers = [provider for provider in grouped_instances.keys() if provider not in self.providers]
        if invalid_providers:
            raise InvalidProvider(f"Providers `{', '.join(sorted(invalid_providers))}` are not valid")

        for provider, list_instance_count in grouped_instances.items():
            provider_obj = self.providers[provider]
            provider_obj.create_extras(list_instance_count)
            started_instances += provider_obj.start_instances(list_instance_count, timeout=start_timeout)
            logger.info(f"Started nodes `{', '.join(sorted(started_instances))}` at provider: {provider}")

        if not started_instances:
            logger.info(f"No nodes were started")
            return []

        logger.info(f"Started {len(started_instances)} nodes: `{', '.join(sorted(started_instances))}`")

        if connection_retries > 0:
            alive_nodes = self.is_alive(
                node_ids=started_instances, retries=connection_retries, wait_timeout=retry_timeout)
            not_alive_nodes = [node_id for node_id, status in alive_nodes.items() if not status]
            if terminate_not_alive and not_alive_nodes:
                logger.warning(f"Nodes `{', '.join(sorted(not_alive_nodes))}` are not alive and being terminated")
                self.stop_nodes(not_alive_nodes, force=True)
                started_instances = [node_id for node_id, status in alive_nodes.items() if status]

        return started_instances

    def start_nodes_by_instance_config_id(self, instance_counts: Dict[str, int], start_timeout: int = 600,
                                          connection_retries: int = 15, retry_timeout: float = 30.0,
                                          terminate_not_alive: bool = False) -> List[str]:
        instances_count_tuple = [
            (self.config_reader.get_instance_info(instance_id), count)
            for instance_id, count in instance_counts.items()
        ]
        return self.start_nodes_by_instance_descriptor(
            instances_count_tuple, start_timeout=start_timeout, connection_retries=connection_retries,
            retry_timeout=retry_timeout, terminate_not_alive=terminate_not_alive)

    # TODO find usages
    def is_alive(self, node_ids: List[str] = None, another_filter: Callable[[NodeDescriptor], bool] = None, retries: int = 5,
                 wait_timeout: float = 30.0) -> Dict[str, bool]:
        # if not node_ids and not tags:
        #    return
        # Get specified nodes
        is_invalid = lambda n: n == NodeStatus.UNKNOWN or n == NodeStatus.PAUSED or n == NodeStatus.STOPPED
        checked_nodes = dict()
        nodes = []

        if not node_ids and not another_filter:
            nodes += self.get_all_nodes()
        if node_ids:
            nodes += self.get_nodes_by_id(node_ids)
        if another_filter:
            nodes += self.get_nodes_with_filter(another_filter, unique=False)
        if not nodes:
            raise EmptyNodeList("No nodes to perform operation")
        nodes = self.__unique_nodes__(nodes)

        for provider, list_nodes in self.__group_nodes_by_provider__(nodes).items():
            _node_ids = [node.node_id for node in list_nodes]
            checked_nodes.update(self.providers[provider].update_instance_info(_node_ids))

        # At this point node status can be UNKNOWN, PAUSED, STOPPED or STARTED..
        # If all nodes are invalid (paused, unknown or stopped). Stop!
        if all(is_invalid(i) for i in checked_nodes.values()) or retries == 0:
            return {node_id: not is_invalid(status) for node_id, status in checked_nodes.items()}

        # All started nodes now are being unreachable and we will try to log in via SSH to change state to reachable
        checked_nodes = {node_id: (NodeStatus.UNREACHABLE if status == NodeStatus.STARTED else status)
                         for node_id, status in checked_nodes.items()}

        # retries > 0
        # Now execute the playbook to test the login to the node
        for i in range(retries):
            unreachable_nodes = [nid for nid, status in checked_nodes.items() if status == NodeStatus.UNREACHABLE]
            logger.info(f"Checking if nodes `{', '.join(sorted(unreachable_nodes))}` are alive. (retries: {i+1}/{retries})")
            run_results = self.runner_provider.execute_playbook(
                playbook_path=path_extend(self.templates_path, 'test_ssh.yml'),
                group_hosts_map=self.node_repository_operator.get_nodes_by_id(unreachable_nodes),
                quiet=True)

            unreachable_nodes = []
            for node in self.get_nodes_by_id(list(run_results.hosts.keys())):
                node.status = NodeStatus.REACHABLE if run_results.hosts[node.node_id] else NodeStatus.UNREACHABLE
                self.node_repository_operator.upsert_node(node)
                checked_nodes[node.node_id] = node.status
                if node.status == NodeStatus.UNREACHABLE:
                    unreachable_nodes.append(node.node_id)

            if not unreachable_nodes or i == retries - 1:
                break
            else:
                logger.info(f"Nodes `{', '.join(sorted(unreachable_nodes))}` are unreachable. "
                            f"Trying again in {wait_timeout} seconds....")

            time.sleep(wait_timeout)

        return {node_id: status == NodeStatus.REACHABLE for node_id, status in checked_nodes.items()}

    # TODO find usages
    def stop_nodes(self, node_ids: List[str] = None, another_filter: Callable[[NodeDescriptor], bool] = None,
                   stop_timeout: int = 600, force: bool = True) -> List[str]:
        nodes = self.__get_existing_nodes__(node_ids, another_filter)
        stopped_nodes = []
        for provider, list_nodes in self.__group_nodes_by_provider__(nodes).items():
            stopped_nodes += self.providers[provider].stop_instances(
                [node.node_id for node in list_nodes], force=force, timeout=stop_timeout)
        return stopped_nodes

    # TODO must wait for SSH option
    # TODO find usages
    def resume_nodes(self, node_ids: List[str] = None, another_filter: Callable[[NodeDescriptor], bool] = None,
                     resume_timeout: int = 600, connection_retries: int = 10,
                     connection_retry_timeout: float = 30.0) -> List[str]:
        nodes = self.__get_existing_nodes__(node_ids, another_filter)
        resumed_nodes = []
        for provider, list_nodes in self.__group_nodes_by_provider__(nodes).items():
            resumed_nodes += self.providers[provider].resume_instances(
                [node.node_id for node in list_nodes], timeout=resume_timeout)
        logger.info(f"Nodes `{', '.join(sorted(resumed_nodes))}` were successfully resumed...")
        if connection_retries > 0:
            self.is_alive(resumed_nodes, retries=connection_retries, wait_timeout=connection_retry_timeout)
        return resumed_nodes

    # TODO find usages
    def pause_nodes(self, node_ids: List[str] = None, another_filter: Callable[[NodeDescriptor], bool] = None,
                    pause_timeout: int = 600) -> List[str]:
        nodes = self.__get_existing_nodes__(node_ids, another_filter)
        paused_nodes = []
        for provider, list_nodes in self.__group_nodes_by_provider__(nodes).items():
            paused_nodes += self.providers[provider].pause_instances(
                [node.node_id for node in list_nodes], timeout=pause_timeout)
        logger.info(f"Nodes `{', '.join(sorted(paused_nodes))}` were successfully paused...")
        return paused_nodes

    def connect_to_node(self, node_id: str, **kwargs):
        node = self.get_nodes_by_id([node_id])[0]
        self.runner_provider.invoke_shell(node, **kwargs)

    # TODO find usages
    def get_ssh_connections(self, node_ids: List[str] = None, another_filter: Callable[[NodeDescriptor], bool] = None,
                            workers: int = 0, connect_timeout: int = 10) -> Dict[str, SSHClient]:
        nodes = self.__get_existing_nodes__(node_ids, another_filter)
        return self.runner_provider.get_connections(nodes, workers=workers, connect_timeout=connect_timeout)

    def execute_command_in_nodes(self, command: str, node_ids: List[str] = None,
                                 another_filter: Callable[[NodeDescriptor], bool] = None, workers: int = 0,
                                 connection_timeout: int = 10, execution_timeout: int = None,
                                 envvars: dict = None) -> Dict[str, Runner.CommandResult]:
        nodes = self.__get_existing_nodes__(node_ids, another_filter)
        return self.runner_provider.run_command(
            nodes, command=command, workers=workers, connect_timeout=connection_timeout,
            exec_timeout=execution_timeout, environment=envvars)

    def execute_playbook_in_nodes(self, playbook_path: str,
                                  group_hosts_map: Union[List[str], Dict[str, List[str]]],
                                  extra_args: Dict[str, str] = None,
                                  group_vars: Dict[str, Dict[str, str]] = None,
                                  host_vars: Dict[str, Dict[str, str]] = None,
                                  tags: List[str] = None,
                                  quiet: bool = False) -> Runner.PlaybookResult:
        # if type(group_hosts_map) is list:
        #     group_hosts_map = {'default': group_hosts_map}

        if type(group_hosts_map) is list:
            if 'node-local' in group_hosts_map:
                group_hosts_map.remove('node-local')
                group_hosts_map = self.node_repository_operator.get_nodes_by_id(group_hosts_map)
                group_hosts_map.append(get_local_node())
            else:
                group_hosts_map = self.node_repository_operator.get_nodes_by_id(group_hosts_map)

        elif type(group_hosts_map) is dict:
            g_map = dict()
            for key, host_list in group_hosts_map.items():
                if 'node-local' in host_list:
                    host_list.remove('node-local')
                    g_map[key] = self.node_repository_operator.get_nodes_by_id(host_list)
                    g_map[key].append(get_local_node())
                else:
                    g_map[key] = self.node_repository_operator.get_nodes_by_id(host_list)
            group_hosts_map = g_map

        else:
            raise TypeError(f"group_hosts_map variable must be a list-like or a dict-like")

        return self.runner_provider.execute_playbook(playbook_path=playbook_path, group_hosts_map=group_hosts_map,
                                                     extra_args=extra_args, group_vars=group_vars, host_vars=host_vars,
                                                     tags=tags, quiet=quiet)

    # TODO find usages
    def add_tag_to_nodes(self, tags: Dict[str, str], node_ids: List[str] = None,
                         another_filter: Callable[[NodeDescriptor], bool] = None) -> List[str]:
        if not tags:
            raise Exception("No tags provided")
        nodes = []
        for node in self.__get_existing_nodes__(node_ids, another_filter):
            for tag, value in tags.items():
                if tag in node.tags:
                    node.tags[tag].append(value)
                    node.tags[tag] = list(set(node.tags[tag]))
                else:
                    node.tags[tag] = [value]
            self.node_repository_operator.upsert_node(node)
            nodes.append(node.node_id)
        return nodes

    # TODO find usages
    def remove_tag_from_nodes(self, tags: Dict[str, str], node_ids: List[str] = None,
                              another_filter: Callable[[NodeDescriptor], bool] = None) -> List[str]:
        if not tags:
            raise Exception("No tags provided")
        nodes = []
        for node in self.__get_existing_nodes__(node_ids, another_filter):
            removed = False
            for tag, value in tags.items():
                if tag not in node.tags:
                    continue
                if not value:
                    node.tags.pop(tag)
                else:
                    _tags = set(node.tags[tag])
                    _tags.discard(value)
                    if len(_tags) == 0:
                        node.tags.pop(tag)
                    else:
                        node.tags[tag] = list(_tags)
                removed = True
            if removed:
                self.node_repository_operator.upsert_node(node)
                nodes.append(node.node_id)
        return nodes

    # TODO find usages
    def node_has_tag(self, tag: str, value: str = None, node_ids: List[str] = None,
                     another_filter: Callable[[NodeDescriptor], bool] = None) -> Dict[str, bool]:
        if not tag:
            raise Exception("No tags provided")

        nodes = dict()
        for node in self.__get_existing_nodes__(node_ids, another_filter):
            if tag not in node.tags:
                nodes[node.node_id] = False
            elif not value:
                nodes[node.node_id] = True
            else:
                nodes[node.node_id] = value in node.tags[tag]
        return nodes

    def upsert_node(self, node: NodeDescriptor):
        self.node_repository_operator.upsert_node(node)

    def get_provider_config(self, provider_config_id: str) -> ProviderConfig:
        return self.config_reader.get_provider_config(provider_config_id)

    def get_all_provider_configs(self) -> Dict[str, ProviderConfig]:
        return self.config_reader.get_all_providers_config()

    def get_login_config(self, login_config_id: str) -> LoginConfig:
        return self.config_reader.get_login_config(login_config_id)

    def get_all_login_configs(self) -> Dict[str, LoginConfig]:
        return self.config_reader.get_all_logins_config()

    def get_instances_config(self, instance_config_id: str) -> InstanceConfigAWS:
        return self.config_reader.get_instance_config(instance_config_id)

    def get_all_instance_configs(self) -> Dict[str, InstanceConfigAWS]:
        return self.config_reader.get_all_instances_config()

    def get_instance_descriptor(self, instance_config_id: str) -> InstanceInfo:
        return self.config_reader.get_instance_info(instance_config_id)

    def get_all_instance_descriptors(self) -> Dict[str, InstanceInfo]:
        return self.config_reader.get_all_instances_info()
