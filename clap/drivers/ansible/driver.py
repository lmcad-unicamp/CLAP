import os.path
import threading
import time
import ansible_runner
import random
import yaml
import subprocess
import paramiko

from queue import Queue
from typing import Optional, List, Dict, Set, Tuple, Union, Any

from clap.common.cluster_repository import RepositoryOperations, ClusterInfo, NodeInfo
from clap.common.config import Defaults, ConfigReader
from clap.common.driver import AbstractInstanceInterface, Codes
from clap.common.utils import path_extend, log, tmpdir, get_log_level
from clap.drivers.ansible.aws_operations.operations import start_aws_nodes, stop_aws_nodes, pause_aws_nodes, resume_aws_nodes, check_instance_status

# TODO become, become=root
# TODO test vpc/ subnet
# TODO boot_disk_size
# TODO boot_disk_device
# TODO boot_disk_type
# TODO test placement_group
# TODO image_userdata
# TODO check network_ids 
# TODO check verbosity

class AnsibleInterface(AbstractInstanceInterface):
    __interface_id__ = 'ansible'

    def __init__(self, repository_operator: RepositoryOperations):
        super(AnsibleInterface, self).__init__(repository_operator)
        self.reader = ConfigReader(Defaults.cloud_conf, Defaults.login_conf, Defaults.instances_conf)
        self.cluster_prefix = 'clap'
        self.node_prefix = 'node'
        

    def __create_hosts_inventory__(self, group_hosts_map: Dict[str, List[str]], group_vars: Dict[str, Dict[str, str]]):
        inventory = dict()

        # Create all group keys
        for group in list(group_hosts_map.keys()):
            inventory[group] = []

        for group, host_list in group_hosts_map.items():
            for node in self.repository_operator.get_nodes(host_list):
                cluster = self.repository_operator.get_cluster(node.cluster_id)
                login = self.reader.get_login(cluster.login_id)

                if 'keypair_name' in login:
                    key_file = path_extend(Defaults.private_path, login['keypair_private_file'])
                else:
                    key_file = path_extend(Defaults.private_path, "{}.pem".format(cluster['extra']['default_keyname']))
                user = login['user']

                node_str = '{} ansible_host={} ansible_connection=ssh ansible_user={} ansible_ssh_private_key_file="{}"'.format(node.node_id, node.ip, user, key_file)
                if group in group_vars:
                    for key, value in group_vars[group].items():
                        node_str += ' {}={}'.format(key, value)

                inventory[group].append(node_str)

        return inventory

    def __cluster_nodes_map__(self, node_ids: List[NodeInfo]) -> Dict[str, List[NodeInfo]]:
        cluster_nodes_map = dict()

        for node in self.repository_operator.get_nodes(node_ids):
            # Get cluster name
            cluster_id = node.cluster_id
            # Append the instance to the cluster name
            if cluster_id in cluster_nodes_map:
                cluster_nodes_map[cluster_id].append(node)
            else:
                cluster_nodes_map[cluster_id] = [node]

        return cluster_nodes_map

    def __create_extra_vars__(self, output_dir: str, node_ids: List[str]):
        # for backward compatibility
        clusters_hosts_map = self.__cluster_nodes_map__(node_ids)

        elasticluster_vars = {
            'elasticluster': {
                'cloud': {},
                'nodes': {},
                'output_dir': output_dir
            }
        }

        for cluster_name, list_nodes in clusters_hosts_map.items():
            cluster = self.repository_operator.get_cluster(cluster_name)
            provider_conf = self.reader.get_provider(cluster.provider_id)
            login_conf = self.reader.get_login(cluster.login_id)

            aws_access_key = open(path_extend(Defaults.private_path, provider_conf['access_keyfile']), 'r').read().strip()
            aws_secret_key = open(path_extend(Defaults.private_path, provider_conf['secret_access_keyfile']), 'r').read().strip()
            aws_region = provider_conf['region']
            keypair_name = login_conf['keypair_name'] if 'keypair_name' in login_conf else cluster['extra']['default_keyname']

            elasticluster_vars['elasticluster']['cloud']['aws_access_key_id'] = aws_access_key
            elasticluster_vars['elasticluster']['cloud']['aws_secret_access_key'] = aws_secret_key
            elasticluster_vars['elasticluster']['cloud']['aws_region'] = aws_region

            for node in list_nodes:
                elasticluster_vars['elasticluster']['nodes'][node.node_id] = {}
                elasticluster_vars['elasticluster']['nodes'][node.node_id]['user_key_name'] = keypair_name
                elasticluster_vars['elasticluster']['nodes'][node.node_id]['instance_id'] = node.extra['instance_id'] if 'instance_id' in node.extra else None

        return elasticluster_vars

    def start_nodes(self, instances_num: Dict[str, int]) -> List[NodeInfo]:     
        # Get instance configurations from configuration files
        instances = {i_name: i_conf for i_name, i_conf in self.reader.get_instances().items() if i_name in list(instances_num.keys())}
        
        # Group instances with same provider and login --> cluster
        cluster_instance_map = dict()
        for iname, iconf in instances.items():
            # Get cluster name
            name = "{}-{}-{}-{}".format(self.__interface_id__, self.cluster_prefix, iconf['provider'], iconf['login'])

            # Append the instance to the cluster name
            if name in cluster_instance_map:
                cluster_instance_map[name].append((iname, iconf, instances_num[iname]))
            else:
                cluster_instance_map[name] = [(iname, iconf, instances_num[iname])]
            
        # Let's create new clusters or pass if already exists...
        clusters = dict()
        for cluster_name, list_iname_iconf_num in cluster_instance_map.items():
            cluster = self.repository_operator.get_cluster(cluster_name)
            # Does cluster not exists yet?
            if not cluster:
                # Get instance configuration...
                conf = list_iname_iconf_num[0][1]
                # Create a new cluster
                cluster = ClusterInfo(
                    cluster_id=cluster_name,
                    provider_id=conf['provider'],
                    login_id=conf['login'],
                    driver_id=self.__interface_id__,
                    extra=dict(default_keyname='key-{}-{}'.format(
                        cluster_name, str(random.random())[2:]))
                )
                # Create the cluster in the repository
                self.repository_operator.write_cluster_info(cluster, create=True)
            
            # Add cluster object to the map
            clusters[cluster_name] = cluster
        
        # TODO Validate configs?


        # OK clusters are created. Lets instantiate nodes!

        # Used to get another thread's results
        q = Queue()
        created_nodes = []
        
        # Iterate over each cluster and their respective (instance_name, instance_config, and number of instances) tuple 
        for cluster_name, list_iname_iconf_num in cluster_instance_map.items():
            # Read the provider configuration and login configuration of this cluster... 
            cluster = clusters[cluster_name]
            provider_conf = self.reader.get_provider(cluster['provider_id'])
            login_conf = self.reader.get_login(cluster['login_id'])

            # For each (instance_name, instance_config, and number of instances) tuple  of this cluster
            for iname, iconf, icount in list_iname_iconf_num:
                # Provider dependent operation...
                if provider_conf['provider'] == 'aws':
                    max_instance_timeout = 600

                    # Start in a new thread so if Main Thread dies (e.g. KeyboardInterrupt) the process still running
                    try:
                        t = threading.Thread(target=start_aws_nodes, args=(
                            q, self.repository_operator, clusters[cluster_name], 
                            provider_conf, login_conf, iname, iconf, icount, self.__interface_id__),
                            kwargs=dict(instance_wait_timeout=max_instance_timeout))
                        
                        # Start thread and wait its execution....
                        t.start()
                        t.join()
                    except BaseException:
                        log.error("The instantiation process is running yet (maximum timeout is {} seconds). "
                            "Terminating now may cause error in the nodes creation and system  may be in an inconsistent state...".format(
                                max_instance_timeout))
                        # Return the already created nodes...
                        return created_nodes
                        
                    created_nodes += q.get()

        if not created_nodes:
            return []

        # Check SSH connection
        alive_nodes = self.check_nodes_alive([node.node_id for node in created_nodes], retries=3, retry_timeout=15)

        # Return last updated nodes
        return self.repository_operator.get_nodes(list(alive_nodes.keys()))

    def stop_nodes(self, node_ids: List[str]):
        # Group instances with same provider and login
        cluster_nodes_map = self.__cluster_nodes_map__(node_ids)
        
        removed_nodes = []
        q = Queue()
        for cluster_id, list_nodes in cluster_nodes_map.items():
            cluster = self.repository_operator.get_cluster(cluster_id)
            provider_conf = self.reader.get_provider(cluster['provider_id'])

            if provider_conf['provider'] == 'aws':
                log.info("Stopping nodes `{}`...".format(', '.join(sorted([n.node_id for n in list_nodes]))))
                try:
                    t = threading.Thread(target=stop_aws_nodes, args=(q, self.repository_operator, provider_conf, list_nodes))
                    t.start()
                    t.join()
                except BaseException:
                    log.error("The termination process is running yet, terminating now may cause error in the nodes creation."
                        "Nodes may be in an inconsistent state...")
                    return removed_nodes
                removed_nodes += q.get()

            #if len(self.repository_operator.get_nodes_from_cluster(cluster_id)) == 0:
            #    log.debug("Removing cluster `{}` because there is no node assigned to it")
            #    self.repository_operator.remove_cluster(cluster_id)

        return removed_nodes

    def pause_nodes(self, node_ids: List[str]):
        # Group instances with same provider and login
        cluster_nodes_map = self.__cluster_nodes_map__(node_ids)
        
        removed_nodes = []
        q = Queue()
        for cluster_id, list_nodes in cluster_nodes_map.items():
            cluster = self.repository_operator.get_cluster(cluster_id)
            provider_conf = self.reader.get_provider(cluster['provider_id'])

            if provider_conf['provider'] == 'aws':
                log.info("Pausing nodes {}...".format(','.join([n.node_id for n in list_nodes]))) 
                try:
                    t = threading.Thread(target=self.__stop_aws_nodes__, args=(q, provider_conf, list_nodes))
                    t.start()
                    t.join()
                except BaseException:
                    log.error("The termination process is running yet, terminating now may cause error in the nodes creation."
                        "Nodes may be in an inconsistent state...")
                    return removed_nodes
                removed_nodes += q.get()

        return removed_nodes

    def resume_nodes(self, node_ids: List[str]):
        # Group instances with same provider and login
        cluster_nodes_map = self.__cluster_nodes_map__(node_ids)
        
        resumed_nodes = []
        q = Queue()
        for cluster_id, list_nodes in cluster_nodes_map.items():
            cluster = self.repository_operator.get_cluster(cluster_id)
            provider_conf = self.reader.get_provider(cluster['provider_id'])

            if provider_conf['provider'] == 'aws':
                log.info("Resuming nodes {}...".format(','.join([n.node_id for n in list_nodes]))) 
                try:
                    t = threading.Thread(target=self.__resume_aws_nodes__, args=(q, provider_conf, list_nodes))
                    t.start()
                    t.join()
                except BaseException:
                    log.error("The termination process is running yet, terminating now may cause error in the nodes creation."
                        "Nodes may be in an inconsistent state...")
                    return resumed_nodes
                resumed_nodes += q.get()
        
        # TODO CHECK CONNECTION

        return resumed_nodes

    def check_nodes_alive(self, node_ids: List[str], shell_command='hostname', retries=1, retry_timeout=15) -> Dict[str, bool]:
        # Group nodes with same provider and login (cluster)
        cluster_nodes_map = self.__cluster_nodes_map__(node_ids)
        
        q = Queue()
        # Iterate over all nodes of the cluters
        for cluster_id, list_nodes in cluster_nodes_map.items():
            # Get cluster
            cluster = self.repository_operator.get_cluster(cluster_id)
            provider_conf = self.reader.get_provider(cluster['provider_id'])

            if provider_conf['provider'] == 'aws':
                check_instance_status(q, self.repository_operator, provider_conf, self.repository_operator.get_nodes(node_ids))
                
        test_connection = {
            'name': 'Test SSH Connection',
            'shell': "{}".format(shell_command)
        }

        tasks = [test_connection]

        created_playbook = [{
            'gather_facts': False,
            'hosts': 'all',
            'tasks': tasks
        }]


        with tmpdir() as dir:
            filename = path_extend(dir, 'test-ssh.yml')

            # Craft EC2 start instances command to yaml file
            with open(filename, 'w') as f:
                yaml.dump(created_playbook, f, explicit_start=True, default_style=None, 
                        indent=2, allow_unicode=True, default_flow_style=False)

            # Filter only reachable nodes
            nodes_to_check = [node for node in self.repository_operator.get_nodes(node_ids) 
                                if node.status == Codes.NODE_STATUS_INIT or node.status == Codes.NODE_STATUS_REACHABLE]
            
            # Execute test only in reachable nodes...
            group_hosts_map = {'all': [node.node_id for node in nodes_to_check]}
            alive_nodes = {}

            for retry in range(1, retries+1):
                log.info("Checking if node are alive (retry: {}/{})".format(retry, retries))
                alive_nodes = self.execute_playbook_in_nodes(filename, group_hosts_map)

                # All nodes alive?
                if all(alive_nodes.values()) or retry == retries:
                    break

                log.info("Some nodes are not acessible by SSH yet... We will retry again after {} seconds. Please wait...".format(retry_timeout))
                time.sleep(retry_timeout)

            # Iterate over all passed nodes and check aliveness
            for node in self.repository_operator.get_nodes(node_ids):
                # Is the node get filtered (not reachable)?
                if node.node_id not in alive_nodes:
                    if node.status == Codes.NODE_STATUS_INIT or node.status == Codes.NODE_STATUS_REACHABLE:
                        node.status = Codes.NODE_STATUS_UNREACHABLE
                    alive_nodes[node.node_id] = False

                # If reachable
                elif alive_nodes[node.node_id]:
                    node.status = Codes.NODE_STATUS_REACHABLE
                
                # If not reachable
                else:
                    node.status = Codes.NODE_STATUS_UNREACHABLE

                # Update node information
                node.update_time = time.time()
                self.repository_operator.write_node_info(node)

            return alive_nodes

    def get_connection_to_nodes(self, node_ids: List[str], *args, **kwargs) -> Dict[str, paramiko.SSHClient]:
        shells = {}
        for node in self.repository_operator.get_nodes(node_ids):
            node = self.repository_operator.get_node(node_ids[0])
            cluster = self.repository_operator.get_cluster(node.cluster_id)
            login = self.reader.get_login(cluster.login_id)

            if 'keypair_name' in login:
                key_file = path_extend(Defaults.private_path, login['keypair_private_file'])
            else:
                key_file = path_extend(Defaults.private_path, "{}.pem".format(cluster['extra']['default_keyname']))
            
            user = login['user']
            connection_ip = node.ip

            if 'open_shell' in kwargs:
                ssh_command = 'ssh -t -o StrictHostKeyChecking=no -i "{}" {}@{}'.format(key_file, user, connection_ip)
                log.info("Executing ssh command: '{}'".format(ssh_command))
                subprocess.call(ssh_command, shell=True)
                log.info("SSH session to {} finalized!".format(connection_ip))
        
            else:
                client = paramiko.SSHClient()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy)
                client.connect(connection_ip, port=22, username=user, key_filename=key_file)
                shells[node.node_id] = client

        return shells

    def execute_playbook_in_nodes(self, playbook_path: str,
                                  group_hosts_map: Dict[str, List[str]],
                                  extra_args: Dict[str, str] = None,
                                  group_vars: Dict[str, Dict[str, str]] = None) -> Dict[str, bool]:
        group_vars = group_vars if group_vars else {}
        extra_args = extra_args if extra_args else {}

        inventory = self.__create_hosts_inventory__(group_hosts_map, group_vars)

        with tmpdir() as dir:
            inventory_filepath = path_extend(dir, 'inventory')
            with open(inventory_filepath, 'w') as inventory_file:
                for group, list_hosts in inventory.items():
                    inventory_file.write('[{}]\n'.format(group))
                    for host in list_hosts:
                        inventory_file.write(host)
                        inventory_file.write('\n')

            all_nodes = set([host for group, hosts in group_hosts_map.items() for host in hosts])

            log.info("Executing playbook: `{}`".format(playbook_path))
            extra_args.update(self.__create_extra_vars__(dir, list(all_nodes)))
            ret = ansible_runner.run(private_data_dir=dir, inventory=inventory_filepath, playbook=playbook_path, 
                                    verbosity=get_log_level(Defaults.log_level), extravars=extra_args)

            status_event = [e for e in ret.events if e['event'] == 'playbook_on_stats'][-1]['event_data']
            
            #ok_nodes = set(list(status_event['ok'].keys()) + list(status_event['ignored'].keys()) + list(status_event['skipped'].keys()))
            not_ok_nodes = set(list(status_event['dark'].keys()) + list(status_event['failures'].keys()) + list(status_event['rescued'].keys()))
        
            final_hosts_map = {node: False if node in not_ok_nodes else True for node in all_nodes}

            return final_hosts_map