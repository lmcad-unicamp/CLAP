import os
import yaml
import ansible_runner
import random
import logging

from queue import Queue
from typing import List, Dict, Set, Tuple

from clap.common.driver import Codes
from clap.common.utils import path_extend, log, tmpdir, get_log_level
from clap.common.cluster_repository import RepositoryOperations, ClusterInfo, NodeInfo
from clap.common.config import Defaults

def __get_ansible_verbosity__():
    if Defaults.log_level == logging.DEBUG:
        return 4
    elif Defaults.log_level == logging.ERROR or Defaults.log_level == logging.CRITICAL:
        return 0
    else:
        return 1
        

def start_aws_nodes(queue: Queue, repository: RepositoryOperations, cluster: ClusterInfo, provider_conf: dict, 
                    login_conf: dict, instance_name: str, instance_conf: dict, count: int, driver_id: str,
                    instance_wait_timeout: int = 600, node_prefix: str = 'node', additional_ansible_kwargs: dict = None,
                    instance_tags: dict = None):
    # Main task name
    task_check_name = 'Start instances (timeout: {} seconds)'.format(instance_wait_timeout)

    try:
        # Get common parameters to aws module...
        aws_access_key = open(path_extend(Defaults.private_path, provider_conf['access_keyfile']), 'r').read().strip()
        aws_secret_key = open(path_extend(Defaults.private_path, provider_conf['secret_access_keyfile']), 'r').read().strip()
        aws_region = provider_conf['region']
        keypair_name = login_conf['keypair_name'] if 'keypair_name' in login_conf else cluster['extra']['default_keyname']
        instance_type = instance_conf['flavor']
        image_id = instance_conf['image_id']

        # Get control info to create a new node...
        control = repository.read_platform_control_info()
        node_names = []
        # Create vector with node names to instance
        for i in range(0, count):
            # Create a new node id
            node_id = "{}-{}".format(node_prefix, control.node_idx)
            control.node_idx += 1
            repository.write_platform_control_info(control)
            node_names.append(node_id)

        # Craft EC2 Task
        ec2_command_values = {
            'name': task_check_name,
            'with_items': node_names,
            'ec2': {
                'aws_access_key': aws_access_key,
                'aws_secret_key': aws_secret_key,
                'region': aws_region,
                'key_name': keypair_name,
                'instance_type': instance_type,
                'image': image_id,
                'count': count,
                'wait': True,
                'wait_timeout': instance_wait_timeout,
                'instance_tags': {
                    'CreatedWith': 'CLAP',
                    'Name': '{}-{{{{item}}}}'.format(cluster.cluster_id)
                }
            }
        }

        # List of tasks for the playbook
        tasks = []

        # Now check the optional parameters...

        # Check if the keypair is present in login['keypair_name']
        # If not, try to create a new one as in cluster['extra']['default_keyname']
        if not 'keypair_name' in login_conf:
            key_destination = path_extend(Defaults.private_path, "{}.pem".format(keypair_name))

            # Does not private cluster key exists?
            if not os.path.exists(key_destination):
                # Try to create a new EC2 keypair...
                key_creation_command = {
                    'name': 'Create an EC2 key',
                    'register': 'ec2_key',
                    'ec2_key': {
                        'aws_access_key': aws_access_key,
                        'aws_secret_key': aws_secret_key,
                        'name': keypair_name,
                        'region': aws_region,
                    }
                }

                # Fail if keypair already exists in server but not in this computer...
                key_fail_command = {
                    'name': "Check keypair existence at server and at host",
                    'when': 'not ec2_key.changed',
                    'fail': {
                        'msg': "'The keypair {} exists in the server but not in our computer. Please remove the keypair at server or locate it at your computer and put at {} path'".format(keypair_name, Defaults.private_path)
                    }
                }

                # If the keypair is successfully created, place it at the Defaults.private folder
                key_store_command = {
                    'name': "Store the created cluster's private EC2 key at CLAP's private folder",
                    'when': 'ec2_key.changed',
                    'copy': {
                        'content': "{{ ec2_key.key.private_key }}",
                        'dest': key_destination,
                        'mode': '0600'
                    }
                }
                
                # Append these tasks at node creation task...
                tasks.append(key_creation_command)
                tasks.append(key_store_command)
                tasks.append(key_fail_command)


        # If there is a placement group at config..
        if 'placement_group' in instance_conf:
            ec2_command_values['ec2']['placement_group'] = instance_conf['placement_group']

        # If there is a network ids at config...
        if 'network_ids' in instance_conf:
            ec2_command_values['ec2']['vpc_subnet_id'] = instance_conf['network_ids']
            ec2_command_values['ec2']['assign_public_ip'] = True
        
        # If there is a security group at config (if not, create a new one with default values)... 
        secgroup_name = None

        if 'security_group' in instance_conf:
            ec2_command_values['ec2']['group'] = instance_conf['security_group']
        elif 'default_security_group' in cluster.extra:
            ec2_command_values['ec2']['group'] = cluster.extra['default_security_group']
        else:
            secgroup_name = "clap-secgroup-{}".format(str(random.random())[2:])
            ec2_command_values['ec2']['group'] = secgroup_name

            security_group_command = {
                'name': 'Create a new security group',
                'ec2_group': {
                    'name': secgroup_name,
                    'aws_access_key': aws_access_key,
                    'aws_secret_key': aws_secret_key,
                    'region': aws_region,
                    'description': 'Default security group created with CLAP',
                    'rules': [
                        {
                            'proto': 'tcp',
                            'from_port': 22,
                            'to_port': 22,
                            'cidr_ip': '0.0.0.0/0'
                        },
                        {
                            'proto': 'tcp',
                            'from_port': 80,
                            'to_port': 80,
                            'cidr_ip': '0.0.0.0/0'
                        },
                        {
                            'proto': 'tcp',
                            'from_port': 443,
                            'to_port': 443,
                            'cidr_ip': '0.0.0.0/0'
                        },
                    ],
                    'rules_egress': [
                        {
                            'proto': 'all',
                            'cidr_ip': '0.0.0.0/0'
                        }
                    ]
                }
            }

            tasks.append(security_group_command)
            secgroup_created = True

        tasks.append(ec2_command_values)

        # Final playbook
        created_playbook = [{
            'gather_facts': False,
            'hosts': 'localhost',
            'tasks': tasks
        }]

    except Exception as e:
        log.error(e)
        raise

    created_nodes = []

    # Create a temporary directory to hold the new created playbook
    with tmpdir() as dir:
        # Playbok filename
        filename = path_extend(dir, 'start-aws-instances.yml')

        # Craft EC2 start instances command to yaml file
        with open(filename, 'w') as f:
            yaml.dump(created_playbook, f, explicit_start=True, default_style=None, 
                    indent=2, allow_unicode=True, default_flow_style=False)

        log.info("Starting {} ec2 instances of type: `{}`...".format(count, instance_name))
        log.debug(created_playbook)
        # Run the playbook!
        ret = ansible_runner.run(private_data_dir=dir, playbook=filename, verbosity=__get_ansible_verbosity__())
        
        # Return code not ok?
        # TODO may check return code or inexistence of runner_on_ok & task==Start instances?
        if ret.rc != 0:
            log.error("Error creating instances. Ansible command returned non-zero code")
            queue.put([])
            return []

        # Get the instance creation event
        instance_event = next(e for e in list(ret.host_events('localhost')) if e['event'] == 'runner_on_ok' and 
                                                e['event_data']['task'] == task_check_name)   
        # Finally get created instances returned by ec2 ansible module
        created_instances = instance_event['event_data']['res']['results'][0]['instances']
    

        for instance, node_id in zip(created_instances, node_names):
            # Create a new CLAP node
            node_info = NodeInfo(
                node_id=node_id,
                cluster_id=cluster['cluster_id'],
                eclust_node_name=None,
                provider_id=None,
                login_id=None,
                instance_type=instance_name,
                instance_conf=None,
                status=Codes.NODE_STATUS_INIT,
                ip=instance['public_ip'],
                keypair=None,
                key=None,
                driver_id=driver_id,
                tags={},
                extra={
                    'instance_id': instance['id'],
                    'private_ip': instance['private_ip'],
                    'dns': instance['dns_name'],
                    'private_dns': instance['private_dns_name'],
                    'architecture': instance['architecture'],
                    'instance_tags': instance['tags'],
                    'vpc_id': None,
                    'subnet_id': None
                }
            )

            # Store the fresh created clap node
            repository.write_node_info(node_info, create=True)
            created_nodes.append(node_info)
            print("Created node: `{}` (instance-id: `{}`)".format(node_id, instance['id']))

        # Security group newly created?
        if secgroup_name:
            cluster.extra['default_security_group'] = secgroup_name
            repository.write_cluster_info(cluster)

    # Put instances in queue to be available in another thread...
    queue.put(created_nodes)
    return created_nodes

def stop_aws_nodes(queue: Queue, repository: RepositoryOperations, provider_conf: dict, node_infos: List[NodeInfo]):
    # Main task name
    task_check_name = 'Stop instances'

    try:
        aws_access_key = open(path_extend(Defaults.private_path, provider_conf['access_keyfile']), 'r').read().strip()
        aws_secret_key = open(path_extend(Defaults.private_path, provider_conf['secret_access_keyfile']), 'r').read().strip()
        aws_region = provider_conf['region']
    except Exception as e:
        log.error(e)
        raise

    ec2_command_values = {
        'name': task_check_name,
        'ec2': {
            'aws_access_key': aws_access_key,
            'aws_secret_key': aws_secret_key,
            'region': aws_region,
            'instance_ids': [node.extra['instance_id'] for node in node_infos],
            'state': 'absent',
            'wait': False
        }
    }

    tasks = [ec2_command_values]

    created_playbook = [{
        'gather_facts': False,
        'hosts': 'localhost',
        'tasks': tasks
    }]

    with tmpdir() as dir:
        filename = path_extend(dir, 'stop-aws-instances.yml')

        # Craft EC2 start instances command to yaml file
        with open(filename, 'w') as f:
            yaml.dump(created_playbook, f, explicit_start=True, default_style=None, 
                    indent=2, allow_unicode=True, default_flow_style=False)

        # Run the playbook!
        ret = ansible_runner.run(private_data_dir=dir, playbook=filename, verbosity=__get_ansible_verbosity__())

        # Not OK?
        if ret.rc != 0:
            log.error("Error stopping instances. Ansible command returned non-zero code")
            queue.put([])
            return []

        # Get the instance removal event
        instances_event = next(e for e in list(ret.host_events('localhost')) if e['event'] == 'runner_on_ok' and 
                                                e['event_data']['task'] == task_check_name)   
        # Finally remove the instances returned by ec2 ansible module
        removed_instances = instances_event['event_data']['res']['instance_ids']

        stopped_nodes = []
        # Run through removed instance ids
        for instance_id in removed_instances:
            # Get node with the selected instance id
            node = next(iter([node for node in node_infos if node.extra['instance_id'] == instance_id]), None)
            # No one? Error?
            if not node:
                log.error("Invalid node with instance id: `{}`".format(instance_id))
                continue
            
            # Remove node with instance id
            repository.remove_node(node.node_id)
            log.info("Node `{}` has been removed!".format(node.node_id))
            stopped_nodes.append(node.node_id)
        
        queue.put(stopped_nodes)
        return stopped_nodes

def pause_aws_nodes(queue, provider_conf, node_infos: List[NodeInfo]):
    try:
        aws_access_key = open(path_extend(Defaults.private_path, provider_conf['access_keyfile']), 'r').read().strip()
        aws_secret_key = open(path_extend(Defaults.private_path, provider_conf['secret_access_keyfile']), 'r').read().strip()
        aws_region = provider_conf['region']
    except Exception as e:
        log.error(e)
        raise

    ec2_command_values = {
        'name': 'Pause instances',
        'ec2': {
            'aws_access_key': aws_access_key,
            'aws_secret_key': aws_secret_key,
            'region': aws_region,
            'instance_ids': [node.extra['instance_id'] for node in node_infos],
            'state': 'stopped',
            'wait': True
        }
    }

    tasks = [ec2_command_values]

    created_playbook = [{
        'gather_facts': False,
        'hosts': 'localhost',
        'tasks': tasks
    }]

    with tmpdir() as dir:
        filename = path_extend(dir, 'pause-instances.yml')

        # Craft EC2 start instances command to yaml file
        with open(filename, 'w') as f:
            yaml.dump(created_playbook, f, explicit_start=True, default_style=None, 
                    indent=2, allow_unicode=True, default_flow_style=False)

        # Run the playbook!
        ret = ansible_runner.run(private_data_dir=dir, playbook=filename, verbosity=__get_ansible_verbosity__())

        # DEbug
        x = list(ret.events)
        
        # Not OK?
        if ret.rc != 0:
            log.error("Error pausing instances. Ansible command returned non-zero code")
            queue.put([])
            return []
        
        paused_nodes = []            
        for node in node_infos:
            node.status = Codes.NODE_STATUS_PAUSED
            self.repository_operator.write_node_info(node)
            log.info("Node `{}` has been paused!".format(node.node_id))
            paused_nodes.append(node)

        queue.put(paused_nodes)
        return paused_nodes

def resume_aws_nodes(queue, provider_conf, node_infos: List[NodeInfo]):
    try:
        aws_access_key = open(path_extend(Defaults.private_path, provider_conf['access_keyfile']), 'r').read().strip()
        aws_secret_key = open(path_extend(Defaults.private_path, provider_conf['secret_access_keyfile']), 'r').read().strip()
        aws_region = provider_conf['region']
    except Exception as e:
        log.error(e)
        raise

    ec2_command_values = {
        'name': 'Resume instances',
        'ec2': {
            'aws_access_key': aws_access_key,
            'aws_secret_key': aws_secret_key,
            'region': aws_region,
            'instance_ids': [node.extra['instance_id'] for node in node_infos],
            'state': 'restarted',
            'wait': True
        }
    }

    tasks = [ec2_command_values]

    created_playbook = [{
        'gather_facts': False,
        'hosts': 'localhost',
        'tasks': tasks
    }]

    with tmpdir() as dir:
        filename = path_extend(dir, 'resume-instances.yml')

        # Craft EC2 start instances command to yaml file
        with open(filename, 'w') as f:
            yaml.dump(created_playbook, f, explicit_start=True, default_style=None, 
                    indent=2, allow_unicode=True, default_flow_style=False)

        # Run the playbook!
        ret = ansible_runner.run(private_data_dir=dir, playbook=filename, verbosity=__get_ansible_verbosity__())

        # DEbug
        x = list(ret.events)
        
        # Not OK?
        if ret.rc != 0:
            log.error("Error resuming instances. Ansible command returned non-zero code")
            queue.put([])
            return []
        
        resumed_nodes = []
        for node in node_infos:
            node.status = Codes.NODE_STATUS_INIT
            self.repository_operator.write_node_info(node)
            log.info("Node `{}` has been resumed!".format(node.node_id))
            resumed_nodes.append(node)

        queue.put(resumed_nodes)
        return resumed_nodes

def check_instance_status(queue, repository: RepositoryOperations, provider_conf, node_infos: List[NodeInfo]):
     # Main task name
    task_check_name = 'Check AWS instance status'

    try:
        # Get common parameters to aws module...
        aws_access_key = open(path_extend(Defaults.private_path, provider_conf['access_keyfile']), 'r').read().strip()
        aws_secret_key = open(path_extend(Defaults.private_path, provider_conf['secret_access_keyfile']), 'r').read().strip()
        aws_region = provider_conf['region']
    except Exception as e:
        log.error(e)
        raise

    # Craft EC2 check instance task
    ec2_command_values = {
        'name': task_check_name,
        'ec2_instance_info': {
            'aws_access_key': aws_access_key,
            'aws_secret_key': aws_secret_key,
            'region': aws_region,
            'instance_ids': [node.extra['instance_id'] for node in node_infos],
        }
    }

    tasks = [ec2_command_values]

    created_playbook = [{
        'gather_facts': False,
        'hosts': 'localhost',
        'tasks': tasks
    }]

    with tmpdir() as dir:
        filename = path_extend(dir, 'check-aws-instances.yml')

        # Craft EC2 start instances command to yaml file
        with open(filename, 'w') as f:
            yaml.dump(created_playbook, f, explicit_start=True, default_style=None, 
                    indent=2, allow_unicode=True, default_flow_style=False)

        # Run the playbook!
        ret = ansible_runner.run(private_data_dir=dir, playbook=filename, verbosity=__get_ansible_verbosity__())
        
        # Not OK?
        if ret.rc != 0:
            log.error("Error checking instances. Ansible command returned non-zero code")
            queue.put([])
            return []

        # Get the instance status event
        instance_event = next(e for e in list(ret.host_events('localhost')) if e['event'] == 'runner_on_ok' and 
                                                e['event_data']['task'] == task_check_name)   
        # Finally get instances status returned by ec2_instance_info ansible module
        instances_status = instance_event['event_data']['res']['instances']

        stated_nodes = []
        for instance in instances_status:
            # Get the node with instance_id
            node = next(iter([node for node in node_infos if node.extra['instance_id'] == instance['instance_id']]), None)
            # Invalid node?
            if not node:
                log.error("Invalid node with instance id: `{}`".format(instance['instance_id']))
                continue

            if instance['state']['name'] == 'running':
                node.status = Codes.NODE_STATUS_INIT
            elif instance['state']['name'] == 'stopped':
                node.status = Codes.NODE_STATUS_PAUSED
            else:
                node.status = Codes.NODE_STATUS_UNREACHABLE
            
            node.ip = instance['public_ip_address'] if 'public_ip_address' in instance else None
            node.extra = {
                'instance_id': instance['instance_id'],
                'private_ip': instance['private_ip_address'],
                'dns': instance['public_dns_name'],
                'private_dns': instance['private_dns_name'],
                'architecture': instance['architecture'],
                'instance_tags': instance['tags'],
                'vpc_id': instance['vpc_id'],
                'subnet_id': instance['subnet_id']
            }
            repository.write_node_info(node)

            stated_nodes.append(node)
        
        queue.put(stated_nodes)
        return stated_nodes