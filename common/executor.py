import multiprocessing
import subprocess
from abc import abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from typing import List, Callable, Any, Union, Dict, Set
from concurrent.futures import ThreadPoolExecutor, as_completed

import ansible_runner
import paramiko
import yaml

from common.node import NodeDescriptor
from common.utils import path_extend, get_logger, tmpdir, default_dict_to_dict

logger = get_logger(__name__)


class Executor:
    @abstractmethod
    def run(self) -> dict:
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

    def connect_and_execute(self, node: NodeDescriptor):
        user = node.configuration.login.user
        ssh_port = node.configuration.login.ssh_port
        connection_ip = node.ip
        key_file = path_extend(
            self.private_path, node.configuration.login.keypair_private_file)
        if not connection_ip:
            raise ConnectionError(f"Invalid connection ip '{node.ip}' for node "
                                  f"{node.node_id}. Check if {node.node_id} "
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
        client.close()
        return stdout_lines, stderr_lines

    def run(self) -> dict:
        results = dict()
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [executor.submit(self.connect_and_execute, node)
                       for node in self.nodes]
            for node, future in zip(self.nodes, as_completed(futures)):
                try:
                    stdout, stderr = future.result()
                    results[node.node_id] = {
                        'success': True,
                        'stdout_lines': stdout,
                        'stderr_lines': stderr,
                        'error': None
                    }
                except Exception as e:
                    logger.error(f"Error executing command `{self.command}` in "
                                 f"node {node.node_id}. {type(e)}: {e}")
                    results[node.node_id] = {
                        'success': False,
                        'stdout_lines': None,
                        'stderr_lines': None,
                        'error': e
                    }
        return results


class AnsiblePlaybookExecutor(Executor):
    @dataclass
    class PlaybookResult:
        ok: bool
        ret_code: int
        hosts: Dict[str, bool]
        events: Dict[str, List[dict]]
        vars: Dict[str, Dict[str, Any]]

    def __init__(self, playbook_file: str,
                 private_path: str,
                 hosts_node_map: Union[List[NodeDescriptor],
                                       Dict[str, List[NodeDescriptor]]] = None,
                 inventory: dict = None,
                 extra_args: Dict[str, str] = None,
                 group_vars: Dict[str, Dict[str, str]] = None,
                 host_vars: Dict[str, Dict[str, str]] = None,
                 quiet: bool = False,
                 verbosity: int = 0
                 ):
        self.playbook_file = playbook_file
        if not hosts_node_map and inventory is None:
            raise ValueError("No nodes informed to execute playbook")
        if type(hosts_node_map) is list:
            self.hosts_node_map = {'all': hosts_node_map}
        elif type(hosts_node_map) is dict:
            for host_name, list_hosts in hosts_node_map.items():
                if not list_hosts:
                    raise ValueError(f"No hosts provided for host: {host_name}")
            self.hosts_node_map = hosts_node_map
        #else:
        #    raise TypeError(f"Invalid type `{type(hosts_node_map)}` for "
        #                    f"hosts_node_map")
        self.private_path = private_path
        self.inventory = inventory or dict()
        self.extra_args = extra_args or dict()
        self.group_vars = group_vars or dict()
        self.host_vars = host_vars or dict()
        self.quiet = quiet
        self.verbosity = verbosity

    def create_extra_vars(self, outdir: str, nodes: List[NodeDescriptor]) -> dict:
        elasticluster_vars = {
            'elasticluster': {
                'cloud': {},
                'nodes': {},
                'output_dir': outdir
            }
        }

        for node in nodes:
            if node.configuration.provider.provider == 'local':
                continue

            if node.configuration.provider.provider == 'aws':
                aws_access_key = open(
                    path_extend(self.private_path,
                                node.configuration.provider.access_keyfile),
                    'r').read().strip()
                aws_secret_key = open(
                    path_extend(self.private_path,
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

    # TODO also allows localhost
    def create_inventory(self, group_hosts_map: Dict[str, List[NodeDescriptor]],
                         group_vars: Dict[str, Dict[str, str]],
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
                _host_vars['ansible_ssh_private_key_file'] = path_extend(
                    self.private_path,
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

    def run(self) -> dict:
        if not self.inventory:
            inventory = self.create_inventory(
                self.hosts_node_map, self.group_vars, self.host_vars)
        else:
            inventory = self.inventory

        with tmpdir() as tdir:
            all_nodes = list([node for host, nodes in self.hosts_node_map.items()
                             for node in nodes])
            self.extra_args.update(self.create_extra_vars(tdir, all_nodes))
            logger.debug(f"Ansible runner will execute the playbook at: "
                         f"`{self.playbook_file}`.")
            logger.debug(f"Inventory: \n{yaml.dump(inventory, sort_keys=True)}")
            logger.debug(f"Extra: \n{yaml.dump(self.extra_args, sort_keys=True)}")
            ret = ansible_runner.run(
                private_data_dir=tdir, inventory=inventory,
                playbook=self.playbook_file, quiet=self.quiet,
                verbosity=self.verbosity, extravars=self.extra_args,
                debug=True if self.verbosity > 3 else False)

            host_playbook_vars = {node.node_id: dict() for node in all_nodes}
            for e in ret.events:
                try:
                    if e['event_data']['task_action'] == 'set_fact' and \
                            e['event'] == 'runner_on_ok':
                        params = e['event_data']['res']['ansible_facts']
                        host = e['event_data']['host']
                        host_playbook_vars[host].update(params)
                except Exception as e:
                    continue

            logger.debug(f"Collected host playbook variables (facts): "
                         f"{host_playbook_vars}")

            try:
                if ret.status != 'successful':
                    raise IndexError
                status_event = [e for e in ret.events
                                if e['event'] == 'playbook_on_stats'][-1]['event_data']
            except IndexError:
                r = AnsiblePlaybookExecutor.PlaybookResult(
                    ok=False, ret_code=ret.rc,
                    hosts={node.node_id: False for node in all_nodes},
                    events={node.node_id: list() for node in all_nodes},
                    vars=host_playbook_vars
                )
                return asdict(r)

            # ok_nodes = set(list(status_event['ok'].keys()) +
            # list(status_event['ignored'].keys()) + list(status_event['skipped'].keys()))
            not_ok_nodes = set(list(status_event['dark'].keys()) +
                               list(status_event['failures'].keys()) +
                               list(status_event['rescued'].keys()))
            r = AnsiblePlaybookExecutor.PlaybookResult(
                ok=ret.status == 'successful', ret_code=ret.rc,
                hosts={node.node_id: node.node_id not in not_ok_nodes
                       for node in all_nodes},
                events={n.node_id: list(ret.host_events(n.node_id))
                        for n in all_nodes},
                vars=host_playbook_vars)
            return asdict(r)


class ShellInvoker(Executor):
    def __init__(self, node: NodeDescriptor, private_path: str,
                 verbosity: int = 0, ssh_binary: str = 'ssh'):
        self.node = node
        self.private_path = private_path
        self.verbosity = verbosity
        self.ssh_binary = ssh_binary

    def run(self) -> dict:
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

        return {}


if __name__ == '__main__':
    import os
    import common.config
    import common.node
    import common.repository
    import json
    config = common.config.Config()
    rpath = os.path.join(config.storage_path, 'nodes.db')
    repository = common.repository.SQLiteRepository(rpath)
    node_controller = common.node.NodeRepositoryController(repository)
    node = node_controller.get_nodes_by_id(['node-5'])[0]
    print(node)

    # c = SSHCommandExecutor('ls -lha ~', [node], config.private_path)
    # results = c.run()
    # print(json.dumps(results, sort_keys=True, indent=4))

    p = AnsiblePlaybookExecutor('/home/lopani/.clap/groups/debug.yaml', config.private_path, hosts_node_map=[node])
    results = p.run()
    print(json.dumps(results, sort_keys=True, indent=4))
