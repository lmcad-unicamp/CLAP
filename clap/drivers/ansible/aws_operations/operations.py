import os
import yaml
import ansible_runner
import random
import logging
import time
import jinja2

from queue import Queue
from typing import List, Dict, Set, Tuple

from clap.common.driver import Codes
from clap.common.utils import path_extend, log, tmpdir
from clap.common.cluster_repository import RepositoryOperations, ClusterInfo, NodeInfo
from clap.common.config import Defaults

def __get_ec2_common_template__(provider_conf: dict, node_infos: List[NodeInfo], task_check_name: str, state: str):
    aws_access_key = open(path_extend(Defaults.private_path, provider_conf['access_keyfile']), 'r').read().strip()
    aws_secret_key = open(path_extend(Defaults.private_path, provider_conf['secret_access_keyfile']), 'r').read().strip()

    envvars = os.environ.copy()
    envvars['AWS_ACCESS_KEY'] = aws_access_key
    envvars['AWS_SECRET_KEY'] = aws_secret_key
    envvars['AWS_REGION'] = provider_conf['region']

    ec2_values = {
        'gather_facts': 'no',
        'hosts': 'localhost',
        'task_name': task_check_name,
        'instance_ids': [node.extra['instance_id'] for node in node_infos],
        'wait': 'no',
        'state': state
    }

    jinjaenv = jinja2.Environment(loader=jinja2.FileSystemLoader(os.path.dirname(os.path.abspath(__file__))), 
                trim_blocks=True, lstrip_blocks=True)
    template = jinjaenv.get_template('ec2-common.j2')
    rendered_template = template.render(ec2_values)

    log.debug("Ansible template to run")
    log.debug(rendered_template)

    return rendered_template, envvars

def stop_aws_nodes(queue: Queue, repository: RepositoryOperations, provider_conf: dict, node_infos: List[NodeInfo]) -> List[str]:
    # Main task check name
    task_check_name = 'Stop instances'
    rendered_template, envvars = __get_ec2_common_template__(provider_conf, node_infos, task_check_name, 'absent')
    
    with tmpdir() as dir:
        filename = path_extend(dir, 'stop-instances.yml')

        with open(filename, 'w') as f:
            f.write(rendered_template)

        # Run the playbook!
        ret = ansible_runner.run(private_data_dir=dir, playbook=filename, verbosity=Defaults.verbosity, envvars=envvars,
                                debug=True if Defaults.verbosity>3 else False)

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

def pause_aws_nodes(queue: Queue, repository: RepositoryOperations, provider_conf: dict, node_infos: List[NodeInfo]) -> List[str]:
    # Main task check name
    task_check_name = 'Pause instances'
    rendered_template, envvars = __get_ec2_common_template__(provider_conf, node_infos, task_check_name, 'stopped')
    
    with tmpdir() as dir:
        filename = path_extend(dir, 'pause-instances.yml')

        with open(filename, 'w') as f:
            f.write(rendered_template)

        # Run the playbook!
        ret = ansible_runner.run(private_data_dir=dir, playbook=filename, verbosity=Defaults.verbosity, envvars=envvars, debug=True if Defaults.verbosity>3 else False)

        # Not OK?
        if ret.rc != 0:
            log.error("Error pausing instances. Ansible command returned non-zero code")
            queue.put([])
            return []

        # Get the instance removal event
        instances_event = next(e for e in list(ret.host_events('localhost')) if e['event'] == 'runner_on_ok' and 
                                                e['event_data']['task'] == task_check_name)   
        # Finally remove the instances returned by ec2 ansible module
        paused_instances = instances_event['event_data']['res']['instances']
        already_paused_instances = instances_event['event_data']['res']['instance_ids']
        paused_instances_ids = [i['id'] for i in instances_event['event_data']['res']['instances']]

        paused_nodes = []
        
        for paused_instance_id in already_paused_instances:
            if paused_instance_id not in paused_instances_ids:
                node = next(iter([node for node in node_infos if node.extra['instance_id'] == paused_instance_id]), None)
                if not node:
                    log.error("Invalid node with instance id: `{}`".format(paused_instance_id))
                    continue

                node.ip = None
                node.status = Codes.NODE_STATUS_PAUSED
                node.update_time = time.time()
                repository.update_node(node)
                log.info("Node `{}` has been already paused!".format(node.node_id))
                paused_nodes.append(node.node_id)

        # Run through removed instance ids
        for instance in paused_instances:
            # Get node with the selected instance id
            node = next(iter([node for node in node_infos if node.extra['instance_id'] == instance['id']]), None)
            # No one? Error?
            if not node:
                log.error("Invalid node with instance id: `{}`".format(instance['id']))
                continue
            
            node.ip = None
            node.status = Codes.NODE_STATUS_PAUSED
            node.update_time = time.time()
            # Remove node with instance id
            repository.update_node(node)
            log.info("Node `{}` has been paused!".format(node.node_id))
            paused_nodes.append(node.node_id)
        
        queue.put(paused_nodes)
        return paused_nodes

def resume_aws_nodes(queue: Queue, repository: RepositoryOperations, provider_conf: dict, node_infos: List[NodeInfo]) -> List[str]:
    # Main task name
    task_check_name = 'Resume instances'
    rendered_template, envvars = __get_ec2_common_template__(provider_conf, node_infos, task_check_name, 'running')
    
    with tmpdir() as dir:
        filename = path_extend(dir, 'resume-instances.yml')

        with open(filename, 'w') as f:
            f.write(rendered_template)

        # Run the playbook!
        ret = ansible_runner.run(private_data_dir=dir, playbook=filename, verbosity=Defaults.verbosity, envvars=envvars, debug=True if Defaults.verbosity>3 else False)

        # Not OK?
        if ret.rc != 0:
            log.error("Error resuming instances. Ansible command returned non-zero code")
            queue.put([])
            return []

        # Get the instance removal event
        instances_event = next(e for e in list(ret.host_events('localhost')) if e['event'] == 'runner_on_ok' and 
                                                e['event_data']['task'] == task_check_name)   
        # Finally remove the instances returned by ec2 ansible module
        resumed_instances = instances_event['event_data']['res']['instances']
        already_running_instances = instances_event['event_data']['res']['instance_ids']
        resumed_instances_ids = [i['id'] for i in instances_event['event_data']['res']['instances']]

        resumed_nodes = []
        
        for running_instance_id in already_running_instances:
            if running_instance_id not in resumed_instances_ids:
                node = next(iter([node for node in node_infos if node.extra['instance_id'] == running_instance_id]), None)
                # No one? Error?
                if not node:
                    log.error("Invalid node with instance id: `{}`".format(running_instance_id))
                    continue

                log.info("Node `{}` has been already resumed!".format(node.node_id))
                resumed_nodes.append(node.node_id)

        
        # Run through removed instance ids
        for instance in resumed_instances:
            # Get node with the selected instance id
            node = next(iter([node for node in node_infos if node.extra['instance_id'] == instance['id']]), None)
            # No one? Error?
            if not node:
                log.error("Invalid node with instance id: `{}`".format(instance['id']))
                continue
            
            node.ip = instance['public_ip']
            node.extra = {
                    'instance_id': instance['id'],
                    'private_ip': instance['private_ip'],
                    'dns': instance['dns_name'],
                    'private_dns': instance['private_dns_name'],
                    'architecture': instance['architecture'],
                    'instance_tags': instance['tags'],
                    'vpc_id': None,
                    'subnet_id': None
                }
            node.status = Codes.NODE_STATUS_INIT
            node.update_time = time.time()

            # Remove node with instance id
            repository.update_node(node)
            log.info("Node `{}` has been resumed!".format(node.node_id))
            resumed_nodes.append(node.node_id)
        
        queue.put(resumed_nodes)
        return resumed_nodes

def check_instance_status(queue, repository: RepositoryOperations, provider_conf, node_infos: List[NodeInfo]):
     # Main task name
    task_check_name = 'Check AWS instance status'

    aws_access_key = open(path_extend(Defaults.private_path, provider_conf['access_keyfile']), 'r').read().strip()
    aws_secret_key = open(path_extend(Defaults.private_path, provider_conf['secret_access_keyfile']), 'r').read().strip()

    envvars = os.environ.copy()
    envvars['AWS_ACCESS_KEY'] = aws_access_key
    envvars['AWS_SECRET_KEY'] = aws_secret_key
    envvars['AWS_REGION'] = provider_conf['region']

    ec2_values = {
        'gather_facts': 'no',
        'hosts': 'localhost',
        'task_name': task_check_name,
        'instance_ids': [node.extra['instance_id'] for node in node_infos],
    }

    jinjaenv = jinja2.Environment(loader=jinja2.FileSystemLoader(os.path.dirname(os.path.abspath(__file__))), 
                trim_blocks=True, lstrip_blocks=True)
    template = jinjaenv.get_template('ec2-check.j2')
    rendered_template = template.render(ec2_values)

    log.debug("Ansible template to run")
    log.debug(rendered_template)

    with tmpdir() as dir:
        filename = path_extend(dir, 'check-instances.yml')

        with open(filename, 'w') as f:
            f.write(rendered_template)

        # Run the playbook!
        ret = ansible_runner.run(private_data_dir=dir, playbook=filename, verbosity=Defaults.verbosity, envvars=envvars, debug=True if Defaults.verbosity>3 else False)
        
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
            repository.update_node(node)

            stated_nodes.append(node)
        
        queue.put(stated_nodes)
        return stated_nodes

def start_aws_nodes(queue: Queue, repository: RepositoryOperations, cluster: ClusterInfo, provider_conf: dict, 
                    login_conf: dict, instance_name: str, instance_conf: dict, count: int, driver_id: str,
                    instance_wait_timeout: int = 600, node_prefix: str = 'node', additional_ansible_kwargs: dict = None,
                    instance_tags: dict = None) -> List[str]:
    task_check_name = 'Start instances (timeout {} seconds)'.format(instance_wait_timeout)

    aws_access_key = open(path_extend(Defaults.private_path, provider_conf['access_keyfile']), 'r').read().strip()
    aws_secret_key = open(path_extend(Defaults.private_path, provider_conf['secret_access_keyfile']), 'r').read().strip()

    envvars = os.environ.copy()
    envvars['AWS_ACCESS_KEY'] = aws_access_key
    envvars['AWS_SECRET_KEY'] = aws_secret_key
    envvars['AWS_REGION'] = provider_conf['region']

    keypair_name = login_conf['keypair_name'] if 'keypair_name' in login_conf else cluster['extra']['default_keyname']
    instance_type = instance_conf['flavor']
    image_id = instance_conf['image_id']

    ec2_vals = {
        'gather_facts': 'no',
        'hosts': 'localhost',
        'task_name': task_check_name,
        'keypair_name': keypair_name,
        'instance_type': instance_type,
        'image_id': image_id,
        'count': count,
        'wait': 'yes',
        'instance_wait_timeout': instance_wait_timeout,
        'instance_tags': {
            'CreatedWith': 'CLAP'
        }
    }

    if not 'keypair_name' in login_conf:
        key_destination = path_extend(Defaults.private_path, "{}.pem".format(keypair_name))

        # Does not private cluster key exists?
        if not os.path.exists(key_destination):
            # Try to create a new EC2 keypair...
            ec2_vals['key_destination'] = key_destination

    # If there is a security group at config (if not, create a new one with default values)... 
    secgroup_name = None

    if 'security_group' in instance_conf:
        ec2_vals['security_group'] = instance_conf['security_group']
    elif 'default_security_group' in cluster.extra:
        ec2_vals['security_group'] = cluster.extra['default_security_group']
    else:
        secgroup_name = "secgroup-{}-{}-{}-{}".format(driver_id, cluster.provider_id, cluster.login_id, str(random.random())[2:])
        ec2_vals['security_group'] = secgroup_name
        ec2_vals['create_security_group'] = True

        # If there is a placement group at config..
    if 'placement_group' in instance_conf:
        ec2_vals['placement_group'] = instance_conf['placement_group']

    # If there is a network ids at config...
    if 'network_ids' in instance_conf:
        ec2_vals['vpc_subnet_id'] = instance_conf['network_ids']

    # Creating volumes
    if 'boot_disk_size' in instance_conf or 'boot_disk_device' in instance_conf or 'boot_disk_iops' in instance_conf or 'boot_disk_type' in instance_conf:
        if 'boot_disk_device' in instance_conf:
            ec2_vals['device_name'] = instance_conf['boot_disk_device']
        else:
            ec2_vals['device_name'] = '/dev/sda1'
        
        if 'boot_disk_type' in instance_conf:
            ec2_vals['volume_type'] = instance_conf['boot_disk_type']
        else:
            ec2_vals['volume_type'] = 'standard'
        
        if 'boot_disk_size' in instance_conf:
            ec2_vals['volume_size'] = instance_conf['boot_disk_size']

        if 'boot_disk_snapshot' in instance_conf:
            ec2_vals['snapshot'] = instance_conf['snapshot']

        if 'boot_disk_iops' in instance_conf:
            ec2_vals['iops'] = instance_conf['iops']

    jinjaenv = jinja2.Environment(loader=jinja2.FileSystemLoader(os.path.dirname(os.path.abspath(__file__))), 
            trim_blocks=True, lstrip_blocks=True)
    template = jinjaenv.get_template('ec2-start.j2')
    rendered_template = template.render(ec2_vals)

    log.debug("Ansible template to run")
    log.debug(rendered_template)

    created_nodes = []

    with tmpdir() as dir:
        filename = path_extend(dir, 'start-instances.yml')

        with open(filename, 'w') as f:
            f.write(rendered_template)

        # Run the playbook!
        ret = ansible_runner.run(private_data_dir=dir, playbook=filename, verbosity=Defaults.verbosity, envvars=envvars, 
                                debug=True if Defaults.verbosity>3 else False)

        # Not OK?
        # TODO may check return code or inexistence of runner_on_ok & task==Start instances?
        if ret.rc != 0:
            log.error("Error creating instances. Ansible command returned non-zero code")
            queue.put([])
            return []

        # Get the instance creation event
        instance_event = next(e for e in list(ret.host_events('localhost')) if e['event'] == 'runner_on_ok' and e['event_data']['task'] == task_check_name)
        created_instances = instance_event['event_data']['res']['instances']

        id_name_map_list = []

        for instance in created_instances:
            # Create a new CLAP node
            node_info = repository.new_node(
                cluster_id=cluster['cluster_id'],
                instance_type=instance_name,
                status=Codes.NODE_STATUS_INIT,
                driver_id=driver_id,
                ip=instance['public_ip'],
                instance_id=instance['id'],
                tags={},
                groups={},
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

            created_nodes.append(node_info.node_id)
            node_name = "{}-{}-{}-{}".format(driver_id, cluster.login_id, cluster.provider_id, node_info.node_id)
            id_name_map_list.append({'id': node_info.instance_id, 'name': node_name})
            log.info("Created node: `{}` (instance-id: `{}` - instance-name: `{}`)".format(node_info.node_id, node_info.instance_id, node_name))
        
        # Security group newly created?
        if secgroup_name:
            cluster.extra['default_security_group'] = secgroup_name
            repository.update_cluster(cluster)

        # Tag EC2 instances
        ec2_tag_instances = {
            'gather_facts': 'no',
            'hosts': 'localhost',
            'names': id_name_map_list
        }

        template = jinjaenv.get_template('ec2-tag-instances.j2')
        rendered_template = template.render(ec2_tag_instances)

        log.debug("Ansible template to run")
        log.debug(rendered_template)

        filename = path_extend(dir, 'tag-aws-instances.yml')

        with open(filename, 'w') as f:
            f.write(rendered_template)

        log.info("Tagging the instances")

        # Run the playbook!
        ret = ansible_runner.run(private_data_dir=dir, playbook=filename, verbosity=Defaults.verbosity, envvars=envvars, 
                                debug=True if Defaults.verbosity>3 else False)
        if ret.rc != 0:
            log.error("Error tagging instances. Ansible command returned non-zero code")
            queue.put(created_nodes)
            return created_nodes


    # Put instances in queue to be available in another thread...
    queue.put(created_nodes)
    return created_nodes