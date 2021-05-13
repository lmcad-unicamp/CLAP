import concurrent.futures
import multiprocessing
import subprocess
from abc import abstractmethod, ABC
from collections import defaultdict
from dataclasses import dataclass
from typing import List, Tuple, Dict, Any, Union

import ansible_runner
import paramiko
import yaml
from paramiko import SSHClient

from common.node import NodeRepositoryController, NodeDescriptor
from common.schemas import InstanceInfo
from common.utils import path_extend, default_dict_to_dict, tmpdir, get_logger

logger = get_logger(__name__)


# TODO remove this class
class AbstractModule:
    module_name = 'abstract module'
    module_version = '0.0.0'
    module_description = 'abstract description'
    module_tags = []

    @staticmethod
    @abstractmethod
    def get_module(*args, **kwargs):
        pass


class AbstractInstanceProvider(ABC):
    provider = 'abstract provider'
    version = '0.1.0'

    def __init__(self, repository: NodeRepositoryController, verbosity: int = 0):
        self.repository = repository
        self.verbosity = verbosity

    @abstractmethod
    def create_extras(self, instance_count_list: List[Tuple[InstanceInfo, int]]):
        pass

    @abstractmethod
    def start_instances(self, instance_count_list: List[Tuple[InstanceInfo, int]], timeout: int = 600) -> List[str]:
        pass

    @abstractmethod
    def stop_instances(self, nodes_to_stop: List[str], force: bool = True, timeout: int = 600) -> List[str]:
        pass

    @abstractmethod
    def pause_instances(self, nodes_to_pause: List[str], timeout: int = 600) -> List[str]:
        pass

    @abstractmethod
    def resume_instances(self, nodes_to_resume: List[str], timeout: int = 600) -> List[str]:
        pass

    @abstractmethod
    def update_instance_info(self, nodes_to_check: List[str], timeout: int = 600) -> Dict[str, str]:
        pass


class _AbstractInstanceProvider(ABC):
    def __init__(self, repository: NodeRepositoryController,
                 verbosity: int = 0):
        self.repository = repository
        self.verbosity = verbosity

    @abstractmethod
    def start_instances(self, instance_count_list: List[Tuple[InstanceInfo, int]],
                        timeout: int = 600) -> List[str]:
        pass

    @abstractmethod
    def stop_instances(self, nodes_to_stop: List[str], force: bool = True,
                       timeout: int = 600) -> List[str]:
        pass

    @abstractmethod
    def pause_instances(self, nodes_to_pause: List[str],
                        timeout: int = 600) -> List[str]:
        pass

    @abstractmethod
    def resume_instances(self, nodes_to_resume: List[str],
                         timeout: int = 600) -> List[str]:
        pass

    @abstractmethod
    def update_instance_info(self, nodes_to_check: List[str],
                             timeout: int = 600) -> Dict[str, str]:
        pass



# TODO remove this class
class Runner:
    @dataclass
    class CommandResult:
        stdout_lines: List[str]
        stderr_lines: List[str]

    @dataclass
    class PlaybookResult:
        ok: bool
        ret_code: int
        hosts: Dict[str, bool]
        events: Dict[str, List[dict]]
        vars: Dict[str, Dict[str, Any]]

    def __init__(self, private_path: str, verbosity: int = 0):
        self.private_path = private_path
        self.verbosity = verbosity

    # TODO also allows localhost
    def __create_inventory__(self, group_hosts_map: Dict[str, List[NodeDescriptor]], group_vars: Dict[str, Dict[str, str]],
                             host_vars: Dict[str, Dict[str, str]]) -> dict:
        inventory = defaultdict(dict)

        groups = defaultdict(dict)

        for group, host_list in group_hosts_map.items():
            gdict = dict()
            try:
                gdict['vars'] = group_vars[group]
            except KeyError:
                pass

            hosts = dict()
            for node in host_list:
                _host_vars = dict()
                _host_vars['ansible_host'] = node.ip
                _host_vars['ansible_connection'] = 'ssh'
                _host_vars['ansible_user'] = node.configuration.login.user
                _host_vars['ansible_ssh_private_key_file'] = path_extend(self.private_path,
                                                                         node.configuration.login.keypair_private_file)
                _host_vars['ansible_port'] = node.configuration.login.ssh_port
                _host_vars.update(host_vars.get(node.node_id, dict()))
                hosts[node.node_id] = _host_vars

            gdict['hosts'] = hosts

            if group == 'all':
                inventory['all'] = gdict
            else:
                groups[group] = gdict

        if groups:
            inventory['all']['children'] = default_dict_to_dict(groups)

        return default_dict_to_dict(inventory)

    def __create_extra_vars__(self, output_dir: str, nodes: List[NodeDescriptor]):
        elasticluster_vars = {
            'elasticluster': {
                'cloud': {},
                'nodes': {},
                'output_dir': output_dir
            }
        }

        for node in nodes:
            if node.configuration.provider.provider == 'local':
                continue

            if node.configuration.provider.provider == 'aws':
                aws_access_key = open(path_extend(self.private_path, node.configuration.provider.access_keyfile),
                                      'r').read().strip()
                aws_secret_key = open(path_extend(self.private_path, node.configuration.provider.secret_access_keyfile),
                                      'r').read().strip()
                aws_region = node.configuration.provider.region
                keypair_name = node.configuration.login.keypair_name

                elasticluster_vars['elasticluster']['cloud']['aws_access_key_id'] = aws_access_key
                elasticluster_vars['elasticluster']['cloud']['aws_secret_access_key'] = aws_secret_key
                elasticluster_vars['elasticluster']['cloud']['aws_region'] = aws_region
                elasticluster_vars['elasticluster']['nodes'][node.node_id] = {
                    'user_key_name': keypair_name,
                    'instance_id': node.cloud_instance_id
                }

        return elasticluster_vars

    def run_command(self, nodes: List[NodeDescriptor], command: str, workers: int = 0, connect_timeout: int = 10,
                    exec_timeout: int = None, environment: dict = None) -> Dict[str, CommandResult]:
        workers = multiprocessing.cpu_count() if workers < 1 else workers

        def connect_and_execute(node: NodeDescriptor) -> Runner.CommandResult:
            user = node.configuration.login.user
            ssh_port = node.configuration.login.ssh_port
            connection_ip = node.ip
            key_file = path_extend(self.private_path, node.configuration.login.keypair_private_file)
            if not connection_ip:
                raise Exception(f"Invalid connection ip ({node.ip}) for node {node.node_id}. "
                                f"Try checking if `{node.node_id}` is alive first...")
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy)
            client.connect(connection_ip, port=ssh_port, username=user, key_filename=key_file, timeout=connect_timeout)
            _, stdout, stderr = client.exec_command(command, timeout=exec_timeout, environment=environment)
            result = Runner.CommandResult(stdout_lines=stdout.readlines(), stderr_lines=stderr.readlines())
            client.close()
            return result

        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {node.node_id: executor.submit(connect_and_execute, node) for node in nodes}

        results = dict()
        for node in nodes:
            node_id = node.node_id
            if node_id not in futures:
                results[node_id] = None
                continue
            try:
                results[node_id] = futures[node_id].result()
            except Exception as e:
                logger.error(f"Error executing command `{command}` in node {node_id}: {type(e)}: {e}")
                results[node_id] = None
                continue

        return results

    def invoke_shell(self, node: NodeDescriptor, **kwargs):
        user = node.configuration.login.user
        connection_ip = node.ip
        ssh_port = kwargs.pop('ssh_port', node.configuration.login.ssh_port)
        ssh_binary = kwargs.pop("ssh_binary", 'ssh')
        key_file = path_extend(self.private_path, node.configuration.login.keypair_private_file)

        ssh_verbose = "-{}".format('v' * self.verbosity) if self.verbosity > 1 else ""
        ssh_command = '{} -t {} -o "Port={}" -o StrictHostKeyChecking=no -o "User={}" -i "{}" {}'.format(
            ssh_binary, ssh_verbose, ssh_port, user, key_file, connection_ip)
        logger.debug(f"Executing ssh command: '{ssh_command}'")
        try:
            subprocess.check_call(ssh_command, shell=True)
            logger.debug(f"SSH session to {connection_ip} finalized!")
        except subprocess.CalledProcessError:
            logger.error(f"Invalid connection ip ({node.ip}). Try checking if `{node.node_id}` is alive first...")

    def get_connections(self, nodes: List[NodeDescriptor], workers: int = 0, connect_timeout: int = 10) -> Dict[str, SSHClient]:
        shells = {}
        workers = multiprocessing.cpu_count() if workers < 1 else workers

        def connect(node: NodeDescriptor) -> SSHClient:
            user = node.configuration.login.user
            ssh_port = node.configuration.login.ssh_port
            connection_ip = node.ip
            key_file = path_extend(self.private_path, node.configuration.login.keypair_private_file)
            if not connection_ip:
                raise Exception(f"Invalid connection ip ({node.ip}) for node {node.node_id}. "
                                f"Try checking if `{node.node_id}` is alive first...")
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy)
            client.connect(connection_ip, port=ssh_port, username=user, key_filename=key_file, timeout=connect_timeout)
            return client

        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [(node.node_id, executor.submit(connect, node)) for node in nodes]

        for node_id, future in futures:
            try:
                shells[node_id] = future.result()
            except Exception as e:
                logger.error(f"Cannot retrieve connection to node {node_id}. An exception occurred")
                logger.error(f"{type(e)}: {e}")

        return shells

    # TODO filter tags
    def execute_playbook(self, playbook_path: str, group_hosts_map: Union[List[NodeDescriptor], Dict[str, List[NodeDescriptor]]],
                             extra_args: Dict[str, str] = None, group_vars: Dict[str, Dict[str, str]] = None,
                             host_vars: Dict[str, Dict[str, str]] = None, tags: List[str] = None,
                         quiet: bool = False) -> PlaybookResult:
        if not group_hosts_map:
            raise ValueError("No nodes provided")
        if type(group_hosts_map) is list:
            group_hosts_map = {'all': group_hosts_map}
        elif type(group_hosts_map) is dict:
            for group_name, list_hosts in group_hosts_map.items():
                if not list_hosts:
                    raise ValueError(f"No hosts provided for group `{group_name}`")
        else:
            raise TypeError(f"Invalid type `{type(group_hosts_map)}` for group_hosts_map")

        tags = tags or []
        group_vars = group_vars or {}
        extra_args = extra_args or {}
        host_vars = host_vars or {}
        inventory = self.__create_inventory__(group_hosts_map, group_vars, host_vars)

        with tmpdir() as tdir:
            all_nodes = [host for group, hosts in group_hosts_map.items() for host in hosts]
            extra_args.update(self.__create_extra_vars__(tdir, all_nodes))
            logger.debug(f"Ansible runner will execute the playbook at: `{playbook_path}`.")
            logger.debug(f"Inventory: \n{yaml.dump(inventory, sort_keys=True)}")
            logger.debug(f"Extra: \n{yaml.dump(extra_args, sort_keys=True)}")
            ret = ansible_runner.run(private_data_dir=tdir, inventory=inventory, playbook=playbook_path,
                                     quiet=quiet, verbosity=self.verbosity, extravars=extra_args,
                                     debug=True if self.verbosity > 3 else False)

            host_playbook_vars = {node.node_id: dict() for node in all_nodes}
            for e in ret.events:
                try:
                    if e['event_data']['task_action'] == 'set_fact' and e['event'] == 'runner_on_ok':
                        params = e['event_data']['res']['ansible_facts']
                        host = e['event_data']['host']
                        host_playbook_vars[host].update(params)
                except Exception:
                    continue

            logger.debug(f"Collected host playbook variables (facts): {host_playbook_vars}")

            try:
                if ret.status != 'successful':
                    raise IndexError
                status_event = [e for e in ret.events if e['event'] == 'playbook_on_stats'][-1]['event_data']
            except IndexError:
                return Runner.PlaybookResult(ok=False, ret_code=ret.rc,
                                             hosts={node.node_id: False for node in all_nodes},
                                             events={node.node_id: list() for node in all_nodes},
                                             vars=host_playbook_vars)

            # ok_nodes = set(list(status_event['ok'].keys()) +
            # list(status_event['ignored'].keys()) + list(status_event['skipped'].keys()))
            not_ok_nodes = set(list(status_event['dark'].keys()) + list(status_event['failures'].keys()) + list(
                status_event['rescued'].keys()))
            return Runner.PlaybookResult(ok=ret.status == 'successful', ret_code=ret.rc,
                                         hosts={node.node_id: node.node_id not in not_ok_nodes for node in all_nodes},
                                         events={n.node_id: list(ret.host_events(n.node_id)) for n in all_nodes},
                                         vars=host_playbook_vars)


    # # TODO find usages
    # def get_connection_to_nodes(self, nodes: List[NodeInfo], *args, **kwargs) -> Dict[str, SSHClient]:
    #     shells = {}
    #     for node in nodes:
    #         user = node.configuration.login.user
    #         connection_ip = node.ip
    #         ssh_port = kwargs.pop('ssh_port', 22)
    #         key_file = path_extend(self.config.private_path, node.configuration.login.keypair_private_file)
    #
    #         if not connection_ip:
    #             logger.error(f"Invalid connection ip ({node.ip}). Try checking if `{node.node_id}` is alive first...")
    #             continue
    #
    #         if 'open_shell' in kwargs:
    #             ssh_binary = kwargs.pop("ssh_binary", 'ssh')
    #             ssh_verbose = "-{}".format('v' * self.verbosity) if self.verbosity > 1 else ""
    #             ssh_command = '{} -t {} -o "Port={}" -o StrictHostKeyChecking=no -o "User={}" -i "{}" {}'.format(
    #                 ssh_binary, ssh_verbose, ssh_port, user, key_file, connection_ip)
    #             logger.info(f"Executing ssh command: '{ssh_command}'")
    #             try:
    #                 subprocess.check_call(ssh_command, shell=True)
    #                 logger.info(f"SSH session to {connection_ip} finalized!")
    #             except subprocess.CalledProcessError:
    #                 logger.error(f"Invalid connection ip ({node.ip}). Try checking if `{node.node_id}` is alive first...")
    #                 pass
    #             continue
    #
    #         else:
    #             client = paramiko.SSHClient()
    #             client.set_missing_host_key_policy(paramiko.AutoAddPolicy)
    #             try:
    #                 client.connect(connection_ip, port=ssh_port, username=user, key_filename=key_file)
    #                 shells[node.node_id] = client
    #             except (paramiko.ssh_exception.SSHException, paramiko.ssh_exception.socket.error) as e:
    #                 logger.error(e)
    #                 logger.error(f"Invalid connection ip ({node.ip}). Try checking if `{node.node_id}` is alive first...")
    #                 continue
    #
    #     return shells
    #
    #
    # def execute_playbook_in_nodes(self, playbook_path: str,
    #                               group_hosts_map: Dict[str, List[NodeInfo]],
    #                               extra_args: Dict[str, str] = None,
    #                               group_vars: Dict[str, Dict[str, str]] = None,
    #                               host_vars: Dict[str, Dict[str, str]] = None,
    #                               tags: List[str] = None,
    #                               quiet: bool = False) -> PlaybookResult:
    #     if not group_hosts_map:
    #         raise ValueError("No nodes provided")
    #
    #     group_vars = group_vars or {}
    #     extra_args = extra_args or {}
    #     host_vars = host_vars or {}
    #     tags = tags or []
    #     inventory = self.__create_inventory__(group_hosts_map, group_vars, host_vars)
    #
    #     with tmpdir() as dir:
    #         inventory_filepath = path_extend(dir, 'inventory')
    #         with open(inventory_filepath, 'w') as inventory_file:
    #             for group, list_hosts in inventory.items():
    #                 inventory_file.write(f'[{group}]\n')
    #                 for host in list_hosts:
    #                     inventory_file.write(host)
    #                     inventory_file.write('\n')
    #
    #         # with open(inventory_filepath, 'r') as inventory_file:
    #         #    log.debug("Inventory used")
    #         #    log.debug(inventory_file.readlines())
    #
    #         all_nodes = [host for group, hosts in group_hosts_map.items() for host in hosts]
    #
    #         # log.info("Executing playbook: `{}`".format(playbook_path))
    #         extra_args.update(self.__create_extra_vars__(dir, all_nodes))
    #         ret = ansible_runner.run(private_data_dir=dir, inventory=inventory_filepath, playbook=playbook_path,
    #                                  quiet=quiet, verbosity=self.verbosity, extravars=extra_args,
    #                                  debug=True if self.verbosity > 3 else False)
    #
    #         # Check set_fact variables for add roles...
    #         # self.__add_role_to_node__(list(ret.events))
    #
    #         try:
    #             if ret.status != 'successful':
    #                 raise IndexError
    #             status_event = [e for e in ret.events if e['event'] == 'playbook_on_stats'][-1]['event_data']
    #         except IndexError:
    #             return RunnerResult(ok=False, ret_code=ret.rc, hosts={node.node_id: False for node in all_nodes},
    #                                 events={node.node_id: list() for node in all_nodes})
    #
    #         # ok_nodes = set(list(status_event['ok'].keys()) + list(status_event['ignored'].keys()) + list(status_event['skipped'].keys()))
    #         not_ok_nodes = set(list(status_event['dark'].keys()) + list(status_event['failures'].keys()) + list(
    #             status_event['rescued'].keys()))
    #         final_hosts_map = RunnerResult(
    #             ok=ret.status == 'successful', ret_code=ret.rc,
    #             hosts={node.node_id: node.node_id not in not_ok_nodes for node in all_nodes},
    #             events={node.node_id: list(ret.host_events(node.node_id)) for node in all_nodes})
    #         return final_hosts_map

# @dataclass
# class RunnerResult:
#     ok: bool
#     ret_code: int
#     hosts: Dict[str, bool]
#     events: Dict[str, List[dict]]

