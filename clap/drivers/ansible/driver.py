import os.path
import threading
import time
import ansible_runner
import random
import yaml
import subprocess
import paramiko
import logging
import jinja2

from queue import Queue
from typing import Optional, List, Dict, Set, Tuple, Union, Any

from clap.common.cluster_repository import RepositoryOperations, ClusterInfo, NodeInfo
from clap.common.config import Defaults, ConfigReader
from clap.common.driver import AbstractInstanceInterface, Codes
from clap.common.utils import path_extend, log, tmpdir
from clap.drivers.ansible.aws_operations.operations import start_aws_nodes, stop_aws_nodes, pause_aws_nodes, resume_aws_nodes, check_instance_status

# TODO test vpc/ subnet
# TODO test placement_group
# TODO image_userdata
# TODO check network_ids 

class AnsibleInterface(AbstractInstanceInterface):
    __interface_id__ = 'ansible'

    def __init__(self, repository_operator: RepositoryOperations):
        super(AnsibleInterface, self).__init__(repository_operator)
        self.reader = ConfigReader(Defaults.cloud_conf, Defaults.login_conf, Defaults.instances_conf)

    def __create_hosts_inventory__(self, group_hosts_map: Dict[str, List[str]], group_vars: Dict[str, Dict[str, str]]):
        inventory = dict()

        # Create all group keys
        for group in list(group_hosts_map.keys()):
            inventory[group] = []

        for group, host_list in group_hosts_map.items():
            for node in self.repository_operator.get_nodes(host_list):
                cluster = self.repository_operator.get_clusters(node.cluster_id)[0]
                login = self.reader.get_login(cluster.login_id)

                if 'keypair_name' in login:
                    key_file = path_extend(Defaults.private_path, login['keypair_private_file'])
                else:
                    key_file = path_extend(Defaults.private_path, "{}.pem".format(cluster['extra']['default_keyname']))
                user = login['user']

                node_str = '{} ansible_host={} ansible_connection=ssh ansible_user={} ansible_ssh_private_key_file="{}"'.format(node.node_id, node.ip, user, key_file)
                if 'sudo' in login:
                    #node_str += " ansible_become=yes"
                    node_str += " ansible_become_user={}".format(login['sudo_user'] 
                                if 'sudo_user' in login else 'root')
                    node_str += " ansible_become_method={}".format(login['sudo_method'] 
                                if 'sudo_method' in login else 'sudo')
                
                if group in group_vars:
                    for key, value in group_vars[group].items():
                        node_str += ' {}={}'.format(key, value)

                inventory[group].append(node_str)

        return inventory

    def __cluster_nodes_map__(self, node_ids: List[str]) -> Dict[str, List[NodeInfo]]:
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
            cluster = self.repository_operator.get_clusters(cluster_name)[0]
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
        invalid_instances = [i_name for i_name in instances_num.keys() if i_name not in self.reader.get_instances().keys()]
        if invalid_instances:
            raise Exception("Could not start nodes. Invalid instance types: `{}`".format(', '.join(sorted(invalid_instances))))

        # Get instance configurations from configuration files
        instances = {i_name: i_conf for i_name, i_conf in self.reader.get_instances().items() if i_name in list(instances_num.keys())}
        
        # Group instances with same provider and login --> cluster
        cluster_instance_map = dict()
        for iname, iconf in instances.items():
            # Get cluster name
            name = "{}-{}-{}-{}".format(self.__interface_id__, 'clap', iconf['provider'], iconf['login'])

            # Append the instance to the cluster name
            if name in cluster_instance_map:
                cluster_instance_map[name].append((iname, iconf, instances_num[iname]))
            else:
                cluster_instance_map[name] = [(iname, iconf, instances_num[iname])]
            
        # Let's create new clusters or pass if already exists...
        clusters = dict()
        for cluster_name, list_iname_iconf_num in cluster_instance_map.items():
            cluster = self.repository_operator.get_clusters(cluster_name)
            # Does cluster not exists yet?
            if not cluster:
                # Get instance configuration...
                conf = list_iname_iconf_num[0][1]
                # Create a new cluster
                cluster = self.repository_operator.new_cluster(
                    cluster_id=cluster_name,
                    provider_id=conf['provider'],
                    login_id=conf['login'],
                    driver_id=self.__interface_id__,
                    extra=dict(default_keyname='key-{}-{}'.format(
                        cluster_name, str(random.random())[2:]))
                )
            else:
                cluster = cluster[0]
                
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
        alive_nodes = self.check_nodes_alive(created_nodes, retries=10, retry_timeout=15)

        # Return last updated nodes
        return self.repository_operator.get_nodes(list(alive_nodes.keys()))

    def stop_nodes(self, node_ids: List[str], force: bool) -> List[str]:
        # Group instances with same provider and login
        cluster_nodes_map = self.__cluster_nodes_map__(node_ids)
        
        removed_nodes = []
        q = Queue()
        for cluster_id, list_nodes in cluster_nodes_map.items():
            cluster = self.repository_operator.get_clusters(cluster_id)[0]
            provider_conf = self.reader.get_provider(cluster['provider_id'])

            if provider_conf['provider'] == 'aws':
                log.info("Stopping nodes `{}`...".format(', '.join(sorted([n.node_id for n in list_nodes]))))
                try:
                    t = threading.Thread(target=stop_aws_nodes, args=(q, self.repository_operator, provider_conf, list_nodes, force))
                    t.start()
                    t.join()
                except BaseException:
                    log.error("The termination process is running yet, terminating now may cause error in the nodes creation."
                        "Nodes may be in an inconsistent state...")
                    return removed_nodes
                removed_nodes += q.get()

        return removed_nodes

    def pause_nodes(self, node_ids: List[str]) -> List[str]:
        # Group instances with same provider and login
        cluster_nodes_map = self.__cluster_nodes_map__(node_ids)
        
        paused_nodes = []
        q = Queue()
        for cluster_id, list_nodes in cluster_nodes_map.items():
            cluster = self.repository_operator.get_clusters(cluster_id)[0]
            provider_conf = self.reader.get_provider(cluster['provider_id'])

            if provider_conf['provider'] == 'aws':
                log.info("Pausing nodes `{}`...".format(', '.join(sorted([n.node_id for n in list_nodes]))))
                try:
                    t = threading.Thread(target=pause_aws_nodes, args=(q, self.repository_operator, provider_conf, list_nodes))
                    t.start()
                    t.join()
                except BaseException:
                    log.error("The pause process is running yet, terminating now may cause error in the nodes creation."
                        "Nodes may be in an inconsistent state...")
                    return paused_nodes
                paused_nodes += q.get()

        return paused_nodes

    def resume_nodes(self, node_ids: List[str]) -> List[str]:
        # Group instances with same provider and login
        cluster_nodes_map = self.__cluster_nodes_map__(node_ids)
        
        resumed_nodes = []
        q = Queue()
        for cluster_id, list_nodes in cluster_nodes_map.items():
            cluster = self.repository_operator.get_clusters(cluster_id)[0]
            provider_conf = self.reader.get_provider(cluster['provider_id'])

            if provider_conf['provider'] == 'aws':
                log.info("Resuming nodes `{}`...".format(', '.join(sorted([n.node_id for n in list_nodes]))))
                try:
                    t = threading.Thread(target=resume_aws_nodes, args=(q, self.repository_operator, provider_conf, list_nodes))
                    t.start()
                    t.join()
                except BaseException:
                    log.error("The resume process is running yet, terminating now may cause error in the nodes creation."
                        "Nodes may be in an inconsistent state...")
                    return resumed_nodes
                resumed_nodes += q.get()


        if not resumed_nodes:
            return []

        # Check SSH connection
        alive_nodes = self.check_nodes_alive(resumed_nodes, retries=10, retry_timeout=15)

        # Return last updated nodes
        return list(alive_nodes.keys())

    def check_nodes_alive(self, node_ids: List[str], shell_command='hostname', retries=1, retry_timeout=20) -> Dict[str, bool]:
        # Group nodes with same provider and login (cluster)
        cluster_nodes_map = self.__cluster_nodes_map__(node_ids)
        
        for retry in range(1, retries+1):
            print("Checking if nodes `{}` are alive (retry: {}/{})".format(', '.join(sorted(node_ids)), retry, retries))
            log.info("Checking if nodes `{}` are alive (retry: {}/{})".format(', '.join(sorted(node_ids)), retry, retries))

            q = Queue()
            # Iterate over all nodes of the cluters
            for cluster_id, list_nodes in cluster_nodes_map.items():
                # Get cluster
                cluster = self.repository_operator.get_clusters(cluster_id)[0]
                provider_conf = self.reader.get_provider(cluster['provider_id'])

                if provider_conf['provider'] == 'aws':
                    check_instance_status(q, self.repository_operator, provider_conf, self.repository_operator.get_nodes(node_ids))

            jinjaenv = jinja2.Environment(loader=jinja2.FileSystemLoader(os.path.dirname(os.path.abspath(__file__))), 
                        trim_blocks=True, lstrip_blocks=True)
            template = jinjaenv.get_template('test-ssh.j2')
            rendered_template = template.render({'shell_command': shell_command})

            log.debug("Ansible template to run")
            log.debug(rendered_template)

            with tmpdir() as dir:
                filename = path_extend(dir, 'test-ssh.yml')

                with open(filename, 'w') as f:
                    f.write(rendered_template)

                # Filter only reachable nodes
                nodes_to_check = [node for node in self.repository_operator.get_nodes(node_ids) 
                                    if node.status == Codes.NODE_STATUS_INIT or node.status == Codes.NODE_STATUS_REACHABLE]
                
                # Execute test only in reachable nodes...
                group_hosts_map = {'all': [node.node_id for node in nodes_to_check]}
                alive_nodes = {}
                alive_nodes = self.execute_playbook_in_nodes(filename, group_hosts_map)

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
                    self.repository_operator.update_node(node)

                
                # All nodes alive?
                if all(alive_nodes.values()) or retry == retries:
                    break

                log.info("Some nodes are not acessible by SSH yet... We will retry again after {} seconds. Please wait...".format(retry_timeout))
                print("Some nodes are not acessible by SSH yet... We will retry again after {} seconds. Please wait...".format(retry_timeout))
                time.sleep(retry_timeout)

        return alive_nodes

    def get_connection_to_nodes(self, node_ids: List[str], *args, **kwargs) -> Dict[str, paramiko.SSHClient]:
        shells = {}
        for node in self.repository_operator.get_nodes(node_ids):
            cluster = self.repository_operator.get_clusters(node.cluster_id)[0]
            login = self.reader.get_login(cluster.login_id)

            if 'keypair_name' in login:
                key_file = path_extend(Defaults.private_path, login['keypair_private_file'])
            else:
                key_file = path_extend(Defaults.private_path, "{}.pem".format(cluster['extra']['default_keyname']))
            
            user = login['user']
            connection_ip = node.ip

            if not connection_ip:
                log.error("Invalid connection ip for node `{}`. Try checking if `{}` is alive first...".format(node.node_id, node.node_id))
                continue

            if 'open_shell' in kwargs:
                ssh_binary = kwargs.get("ssh_binary", 'ssh')
                ssh_port = kwargs.get('ssh_port', 22)
                ssh_verbose = "-{}".format('v'*Defaults.verbosity) if Defaults.verbosity > 1 else ""

                ssh_command = '{} -t {} -o "Port={}" -o StrictHostKeyChecking=no -o "User={}" -i "{}" {}'.format(
                            ssh_binary, ssh_verbose, ssh_port, user, key_file, connection_ip)
                log.info("Executing ssh command: '{}'".format(ssh_command))
                try:
                    subprocess.check_call(ssh_command, shell=True)
                    log.info("SSH session to {} finalized!".format(connection_ip))
                except subprocess.CalledProcessError:
                    log.error("Invalid connection ip for node `{}`. Try checking if `{}` is alive first...".format(node.node_id, node.node_id))
                
                return {}
        
            else:
                client = paramiko.SSHClient()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy)
                try:
                    client.connect(connection_ip, port=22, username=user, key_filename=key_file)
                    shells[node.node_id] = client
                except (paramiko.ssh_exception.SSHException, paramiko.ssh_exception.socket.error) as e:
                    log.error(e)
                    log.error("Invalid connection ip for node `{}`. Try checking if `{}` is alive first...".format(node.node_id, node.node_id))
        return shells

    def execute_playbook_in_nodes(self, playbook_path: str,
                                  group_hosts_map: Dict[str, List[str]],
                                  extra_args: Dict[str, str] = None,
                                  group_vars: Dict[str, Dict[str, str]] = None,
                                  quiet: bool = False) -> Dict[str, bool]:
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
            
            with open(inventory_filepath, 'r') as inventory_file: 
                log.debug("Inventory used")
                log.debug(inventory_file.readlines())

            all_nodes = set([host for group, hosts in group_hosts_map.items() for host in hosts])

            log.info("Executing playbook: `{}`".format(playbook_path))
            extra_args.update(self.__create_extra_vars__(dir, list(all_nodes)))
            ret = ansible_runner.run(private_data_dir=dir, inventory=inventory_filepath, playbook=playbook_path, quiet=quiet,
                                    verbosity=Defaults.verbosity, extravars=extra_args, debug=True if Defaults.verbosity>3 else False)
            
            # Check set_fact variables for add roles...
            roles = {}
            for e in ret.events:
                try:
                    if e['event_data']['task_action'] == 'set_fact' and e['event'] == 'runner_on_ok':
                        params = e['event_data']['res']['ansible_facts']['clap_role']
                        host = e['event_data']['host']
                        to_add_role = []
                        
                        if type(params) is str:
                            to_add_role = [params]
                        elif type(params) is list:
                            to_add_role = [str(p) for p in params]
                        else:
                            raise Exception
                        
                        if not to_add_role:
                            continue

                        if host in roles:
                            roles[host] += to_add_role
                        else:
                            roles[host] = to_add_role 
                except Exception as e:
                    print(e)

            if roles:
                nodes = self.repository_operator.get_nodes(list(roles.keys()))
                for node in nodes:
                    node.roles = list(set(node.roles+roles[node.node_id]))
                    self.repository_operator.update_node(node)

            status_event = [e for e in ret.events if e['event'] == 'playbook_on_stats'][-1]['event_data']
            
            #ok_nodes = set(list(status_event['ok'].keys()) + list(status_event['ignored'].keys()) + list(status_event['skipped'].keys()))
            not_ok_nodes = set(list(status_event['dark'].keys()) + list(status_event['failures'].keys()) + list(status_event['rescued'].keys()))
        
            final_hosts_map = {node: False if node in not_ok_nodes else True for node in all_nodes}

            return final_hosts_map
