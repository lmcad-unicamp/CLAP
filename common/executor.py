import multiprocessing
import os
import subprocess
from abc import abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from multiprocessing.pool import ThreadPool
from typing import List, Callable, Any, Union, Dict, Set
from concurrent.futures import ThreadPoolExecutor, as_completed

import ansible_runner
import paramiko
import yaml

from common.node import NodeDescriptor
from common.utils import path_extend, get_logger, tmpdir, defaultdict_to_dict

logger = get_logger(__name__)


class Executor:
    @abstractmethod
    def run(self) -> Any:
        raise NotImplementedError("Must be implemented in derived classes")


class SSHCommandExecutor(Executor):
    def __init__(self, command: str,
                 nodes: List[NodeDescriptor],
                 private_path: str,
                 max_workers: int = 0,
                 connection_timeout: float = 10.0,
                 execution_timeout: float = None,
                 environment: dict = None):
        self.command = command
        self.nodes = nodes
        self.private_path = private_path
        self.max_workers = max_workers if max_workers > 0 else \
            multiprocessing.cpu_count()
        self.connection_timeout = connection_timeout
        self.execution_timeout = execution_timeout
        self.environment = environment or dict()

    def connect_and_execute(self, node: NodeDescriptor) -> dict:
        try:
            user = node.configuration.login.user
            ssh_port = node.configuration.login.ssh_port
            connection_ip = node.ip
            key_file = path_extend(
                self.private_path, node.configuration.login.keypair_private_file)
            if not connection_ip:
                raise ConnectionError(f"Invalid connection ip '{node.ip}' for node "
                                      f"{node.nickname}. Check if {node.nickname} "
                                      f"is alive first...")

            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy)
            client.connect(connection_ip, port=ssh_port, username=user,
                           key_filename=key_file, timeout=self.connection_timeout)
            _, stdout, stderr = client.exec_command(
                self.command, timeout=self.execution_timeout,
                environment=self.environment)
            stdout_lines = stdout.readlines()
            stderr_lines = stderr.readlines()
            return_code = stdout.channel.recv_exit_status()
            client.close()
            return {
                'ok': True,
                'return_code': return_code,
                'stdout_lines': stdout_lines,
                'stderr_lines': stderr_lines,
                'error': None
            }
        except Exception as e:
            logger.error(f"Error executing command in node {node.node_id[:8]}: {e}")
            return {
                'ok': False,
                'return_code': None,
                'stdout_lines': None,
                'stderr_lines': None,
                'error': str(e)
            }

    def run(self) -> dict:
        results = dict()
        with ThreadPool(processes=self.max_workers) as pool:
            values = [(node,) for node in self.nodes]
            _results = pool.starmap(self.connect_and_execute, values)
            for node, result in zip(self.nodes, _results):
                results[node.node_id] = result
        return results


class AnsiblePlaybookExecutor(Executor):
    @dataclass
    class PlaybookResult:
        ok: bool
        ret_code: int
        hosts: Dict[str, bool]
        events: Dict[str, List[dict]]
        vars: Dict[str, Dict[str, Any]]

    @staticmethod
    def create_inventory(
            hosts_node_map: Union[
                List[NodeDescriptor], Dict[str, List[NodeDescriptor]]],
            private_path: str,
            host_vars: Dict[str, Dict[str, str]] = None,
            node_vars: Dict[str, Dict[str, str]] = None) -> dict:
        inventory = defaultdict(dict)
        hosts = defaultdict(dict)
        host_vars = host_vars or dict()
        node_vars = node_vars or dict()

        if type(hosts_node_map) is list:
            hosts_node_map = {'all': hosts_node_map}
        elif type(hosts_node_map) is not dict:
            raise TypeError(f"Invalid type {type(hosts_node_map)} for "
                            f"hosts_node_map parameter")

        for host, node_list in hosts_node_map.items():
            host_dict = dict()
            try:
                host_dict['vars'] = host_vars[host]
            except KeyError:
                pass

            _hosts = dict()
            for node in node_list:
                _host_vars = dict()
                _host_vars['ansible_host'] = node.ip
                _host_vars['ansible_connection'] = 'ssh'
                _host_vars['ansible_user'] = node.configuration.login.user
                _host_vars['ansible_ssh_private_key_file'] = path_extend(
                    private_path, node.configuration.login.keypair_private_file)
                _host_vars['ansible_port'] = node.configuration.login.ssh_port
                _host_vars.update(node_vars.get(node.node_id, dict()))
                _hosts[node.node_id] = _host_vars

            host_dict['hosts'] = _hosts

            if host == 'all':
                inventory['all'] = host_dict
            else:
                hosts[host] = host_dict

        if hosts:
            inventory['all']['children'] = defaultdict_to_dict(hosts)

        return defaultdict_to_dict(inventory)

    @staticmethod
    def create_extra_vars(output_dir: str, nodes: List[NodeDescriptor],
                          private_path: str) -> dict:
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
                aws_access_key = open(
                    path_extend(private_path,
                                node.configuration.provider.access_keyfile),
                    'r').read().strip()
                aws_secret_key = open(
                    path_extend(private_path,
                                node.configuration.provider.secret_access_keyfile),
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

    def __init__(self, playbook_file: str,
                 private_path: str,
                 inventory: Union[list, dict] = None,
                 extra_args: Dict[str, str] = None,
                 env_vars: Dict[str, str] = None,
                 quiet: bool = False,
                 verbosity: int = 0):
        default_inventory = {
            'all': {
                'children': {
                    'localhost': {}
                }
            }
        }
        self.playbook_file = playbook_file
        self.private_path = private_path
        self.inventory = inventory or default_inventory
        self.env_vars = env_vars or os.environ.copy()
        self.extra_args = extra_args or dict()
        self.quiet = quiet
        self.verbosity = verbosity

    def run(self) -> PlaybookResult:
        with tmpdir() as tdir:
            logger.debug(f"Ansible runner will execute the playbook at: "
                         f"`{self.playbook_file}`.")
            logger.debug(f"Inventory: \n{yaml.dump(self.inventory)}")
            logger.debug(f"Extra: \n{yaml.dump(self.extra_args)}")
            ret = ansible_runner.run(
                private_data_dir=tdir, inventory=self.inventory,
                playbook=self.playbook_file, quiet=self.quiet,
                verbosity=self.verbosity, extravars=self.extra_args,
                envvars=self.env_vars,
                debug=True if self.verbosity > 3 else False)

            host_playbook_vars = defaultdict(dict)
            for e in ret.events:
                try:
                    if e['event_data']['task_action'] == 'set_fact' and \
                            e['event'] == 'runner_on_ok':
                        params = e['event_data']['res']['ansible_facts']
                        host = e['event_data']['host']
                        host_playbook_vars[host].update(params)
                except KeyError:
                    continue

            host_playbook_vars = defaultdict_to_dict(host_playbook_vars)
            logger.debug(f"Collected host playbook variables (facts): "
                         f"{host_playbook_vars}")

            stats = ret.stats
            if stats is None:
                r = self.PlaybookResult(
                    ok=False, ret_code=ret.rc, hosts={}, events={},
                    vars=host_playbook_vars
                )
                return r

            all_nodes = list({host for hosts in stats.values()
                              for host in hosts.keys()})
            not_ok_nodes = list({host for s in ['dark', 'failures']
                                 for host in stats[s].keys()})
            hosts_stats = {n: n not in not_ok_nodes for n in all_nodes}
            hosts_events = {n: list(ret.host_events(n)) for n in all_nodes}

            r = self.PlaybookResult(
                ok=ret.status == 'successful',
                ret_code=ret.rc,
                hosts=hosts_stats,
                events=hosts_events,
                vars=host_playbook_vars
            )
            return r


class ShellInvoker(Executor):
    def __init__(self, node: NodeDescriptor, private_path: str,
                 verbosity: int = 0, ssh_binary: str = 'ssh'):
        self.node = node
        self.private_path = private_path
        self.verbosity = verbosity
        self.ssh_binary = ssh_binary

    def run(self):
        user = self.node.configuration.login.user
        ssh_port = self.node.configuration.login.ssh_port
        connection_ip = self.node.ip
        key_file = path_extend(
            self.private_path,
            self.node.configuration.login.keypair_private_file)
        ssh_verbose = "-{}".format('v' * self.verbosity) if self.verbosity > 1 \
            else ""
        ssh_command = f'{self.ssh_binary} -t {ssh_verbose} -o "Port={ssh_port}" ' \
                      f'-o StrictHostKeyChecking=no -o "User={user}" ' \
                      f'-i "{key_file}" {connection_ip}'
        logger.debug(f"Executing ssh command: '{ssh_command}'")
        try:
            subprocess.check_call(ssh_command, shell=True)
            logger.debug(f"SSH session to {connection_ip} finalized!")
        except subprocess.CalledProcessError:
            logger.error(f"Invalid connection ip: {self.node.ip}. "
                         f"Check if `{self.node.node_id}` is alive first...")


# if __name__ == '__main__':
    # import os
    # import common.config
    # import common.node
    # import common.repository
    # import json
    # config = common.config.Config()
    # rpath = os.path.join(config.storage_path, 'nodes.db')
    # repository = common.repository.SQLiteRepository(rpath)
    # node_controller = common.node.NodeRepositoryController(repository)
    # node = node_controller.get_nodes_by_id(['node-5'])[0]
    # print(node)

    # c = SSHCommandExecutor('ls -lha ~', [node], config.private_path)
    # results = c.run()
    # print(json.dumps(results, sort_keys=True, indent=4))

    # p = AnsiblePlaybookExecutor('/home/lopani/.clap/groups/debug.yaml', config.private_path, hosts_node_map=[node])
    # results = p.run()
    # print(json.dumps(results, sort_keys=True, indent=4))
