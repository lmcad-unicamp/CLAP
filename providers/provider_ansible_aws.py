import concurrent.futures
import multiprocessing
import os
import ansible_runner
import random
import jinja2

from dataclasses import dataclass, asdict
from itertools import groupby
from typing import List, Dict, Tuple, Any

from common.config import Config
from common.executor import AnsiblePlaybookExecutor
from common.node import NodeDescriptor, NodeRepositoryController, NodeStatus, \
    NodeLifecycle, NodeType
from common.provider import AbstractInstanceProvider
from common.repository import RepositoryController, InvalidEntryError, RepositoryFactory
from common.schemas import InstanceInfo, ProviderConfigAWS
from common.utils import path_extend, tmpdir, get_logger

logger = get_logger(__name__)


class AnsibleAWSProvider(AbstractInstanceProvider):
    provider = 'aws'
    version = '0.1.0'

    def __init__(self, repository: NodeRepositoryController, verbosity: int = 0,
                 **kwargs):
        super(AnsibleAWSProvider, self).__init__(repository, verbosity)
        self.config = Config()
        self.private_path = self.config.private_path
        self.templates_path = path_extend(
            os.path.dirname(os.path.abspath(__file__)), 'templates')
        self.jinjaenv = jinja2.Environment(
            loader=jinja2.FileSystemLoader(self.templates_path),
            trim_blocks=True, lstrip_blocks=True)

    @staticmethod
    def _get_named_event(events: Dict[str, List[dict]], task_name) -> dict:
        instance_event = [e for _e in events.values() for e in _e
                          if e['event'] == 'runner_on_ok' and
                          e['event_data']['task'] == task_name][0]
        return instance_event

    def _run_template(self, output_filename: str, rendered_template: str,
                      envvars: Dict[str, str] = None, quiet: bool = False) -> \
            AnsiblePlaybookExecutor.PlaybookResult:
        with tmpdir(suffix='.aws') as tdir:
            output_filename = path_extend(tdir, output_filename)
            with open(output_filename, 'w') as f:
                f.write(rendered_template)

            r = AnsiblePlaybookExecutor(
                output_filename, self.private_path, inventory={'all': 'localhost'},
                env_vars=envvars, verbosity=self.verbosity, quiet=quiet)
            return r.run()

    def create_envvars(self, config: ProviderConfigAWS):
        envvars = os.environ.copy()
        acc_key = path_extend(self.private_path, config.access_keyfile)
        sec_key = path_extend(self.private_path, config.secret_access_keyfile)
        envvars['AWS_ACCESS_KEY'] = open(acc_key, 'r').read().strip()
        envvars['AWS_SECRET_KEY'] = open(sec_key, 'r').read().strip()
        envvars['AWS_REGION'] = config.region
        return envvars

    def _start_instances(self, instance: InstanceInfo, count: int,
                         wait_timeout: int) -> List[str]:
        task_check_name = f"Starting {count} " \
                          f"{instance.instance.instance_config_id} instances " \
                          f"(timeout {wait_timeout} seconds)"
        envvars = self.create_envvars(instance.provider)
        instance.instance.security_group = instance.instance.security_group
        instance_tags = {'CreatedWith': 'CLAP'}

        ec2_vals = {
            'keypair_name': instance.login.keypair_name,
            'instance_type': instance.instance.flavor,
            'image_id': instance.instance.image_id,
            'count': count,
            'wait': 'yes',
            'security_group': instance.instance.security_group,
            'instance_wait_timeout': wait_timeout,
        }

        # If there is a placement group at config..
        if instance.instance.placement_group:
            ec2_vals['placement_group'] = instance.instance.placement_group
        # If there is a network ids at config...
        if instance.instance.network_ids:
            ec2_vals['vpc_subnet_id'] = instance.instance.network_ids
        # Creating volumes
        if instance.instance.boot_disk_size or \
                instance.instance.boot_disk_type or \
                instance.instance.boot_disk_iops or \
                instance.instance.boot_disk_device or \
                instance.instance.boot_disk_snapshot:
            ec2_vals['device_name'] = instance.instance.boot_disk_device or '/dev/sda1'
            ec2_vals['boot_disk_type'] = instance.instance.boot_disk_type or 'standard'
            if instance.instance.boot_disk_size:
                ec2_vals['volume_size'] = instance.instance.boot_disk_size
            if instance.instance.boot_disk_snapshot:
                ec2_vals['snapshot'] = instance.instance.boot_disk_snapshot
            if instance.instance.boot_disk_iops:
                ec2_vals['iops'] = instance.instance.boot_disk_iops

        # Request Spot?
        if instance.instance.price:
            launch_group = 'spot-{}'.format(str(random.random())[2:])
            ec2_vals['spot_price'] = instance.instance.price
            ec2_vals['spot_timeout'] = instance.instance.timeout or 600
            ec2_vals['spot_launch_group'] = launch_group
            instance_tags['Spot'] = True
            instance_tags['SpotLaunchGroup'] = launch_group
            task_check_name = f"Starting {count} " \
                              f"{instance.instance.instance_config_id} spot " \
                              f"instances (timeout {wait_timeout} seconds)"

        # Final instance vars
        ec2_vals['instance_tags'] = instance_tags
        ec2_vals['task_name'] = task_check_name

        # Render and run ec2_start_instances.j2 playbook
        rendered_template = self.jinjaenv.get_template('ec2_start_instances.j2').render(ec2_vals)
        result = self._run_template('start_instances.yml', rendered_template, envvars=envvars)
        if not result.ok:
            logger.error("Error executing start instances playbook. "
                         f"Non-zero return code ({result.ret_code})")
            return []

        # Get the instance creation event
        task_event = self._get_named_event(result.events, task_check_name)
        created_instances = task_event['event_data']['res']['instances']
        created_nodes = []

        for fresh_instance in created_instances:
            lifecycle = NodeLifecycle.PREEMPTIBLE if instance.instance.price \
                else NodeLifecycle.NORMAL
            # Create a new CLAP node
            node_info = self.repository.create_node(
                instance_descriptor=instance,
                cloud_instance_id=fresh_instance['id'],
                ip=fresh_instance['public_ip'],
                status=NodeStatus.STARTED,
                cloud_lifecycle=lifecycle,
                node_type=NodeType.TYPE_CLOUD,
                extra={
                    'instance_id': fresh_instance['id'],
                    'private_ip': fresh_instance['private_ip'],
                    'dns': fresh_instance['dns_name'],
                    'private_dns': fresh_instance['private_dns_name'],
                    'architecture': fresh_instance['architecture'],
                    'instance_tags': fresh_instance['tags'],
                    'vpc_id': None,
                    'subnet_id': None
                }
            )
            created_nodes.append(node_info.node_id)
            logger.info(
                f"Created an AWS node: `{node_info.node_id}` - {node_info.nickname} "
                f"(cloud-instance-id: `{node_info.cloud_instance_id}`)")

        return created_nodes

    def _tag_instances(self, node_list: List[str]) -> List[str]:
        task_check_name = 'Tagging instances'
        # Group by provider
        node_list = self.repository.get_nodes_by_id(node_list)
        tagged_instances = []

        for _, nodes in groupby(node_list, lambda x: x.configuration.provider.provider_config_id):
            nodes = list(nodes)
            envvars = self.create_envvars(nodes[0].configuration.provider)
            names = [{
                'id': node.cloud_instance_id,
                'name': f"{node.node_id}-{node.nickname.replace(' ', '')}"
            } for node in nodes]

            ec2_vals = {
                'task_name': task_check_name,
                'names': names,
            }

            rendered_template = self.jinjaenv.get_template('ec2_tag_instances.j2').render(ec2_vals)
            result = self._run_template('ec2_tag_instances.yml', rendered_template, envvars)
            if not result.ok:
                logger.error(
                    f"Error tagging instances "
                    f"`{', '.join(sorted([node.node_id for node in nodes]))}`. "
                    f"Non-zero return code ({result.ret_code})")
            else:
                tagged_instances += [node.node_id for node in nodes]

        return tagged_instances

    def execute_common_template(self, nodes: List[NodeDescriptor],
                                provider_config: ProviderConfigAWS,
                                task_check_name: str, state: str,
                                wait: str = 'no') -> Dict[str, List[dict]]:
        envvars = self.create_envvars(provider_config)
        ec2_vals = {
            'task_name': task_check_name,
            'instance_ids': [node.cloud_instance_id for node in nodes],
            'wait': wait,
            'state': state
        }

        rendered_template = self.jinjaenv.get_template('ec2_common.j2').render(ec2_vals)
        result = self._run_template(
            'ec2_common_{}.yml'.format(state), rendered_template, envvars)
        if not result.ok:
            logger.error(f"Error changing state of nodes "
                         f"{','.join([node.node_id for node in nodes])} to {state}. "
                         f"Non-zero return code ({result.ret_code})")
            return {}

        return result.events

    def execute_check_template(self, nodes: List[NodeDescriptor],
                               provider_config: ProviderConfigAWS,
                               task_check_name: str,
                               quiet: bool = False) -> Dict[str, List[dict]]:
        envvars = self.create_envvars(provider_config)
        ec2_vals = {
            'task_name': task_check_name,
            'instance_ids': [node.cloud_instance_id for node in nodes],
        }

        rendered_template = self.jinjaenv.get_template('ec2_check.j2').render(ec2_vals)
        result = self._run_template('ec2_check.yml', rendered_template, envvars, quiet=quiet)
        if not result.ok:
            logger.error(f"Error checking nodes "
                         f"{','.join([node.node_id for node in nodes])}. "
                         f"Non-zero return code ({result.ret_code})")
            return {}
        return result.events

    def start_instances(self, instance_count_list: List[Tuple[InstanceInfo, int]], timeout: int = 600) -> List[str]:
        created_nodes = []
        for (instance, count) in instance_count_list:
            created_nodes += self._start_instances(instance, count, timeout)
        self._tag_instances(created_nodes)
        return created_nodes

    def stop_instances(self, nodes_to_stop: List[str], force: bool = True,
                       timeout: int = 600) -> List[str]:
        state = 'absent'
        stopped_nodes = []
        nodes_to_stop = self.repository.get_nodes_by_id(nodes_to_stop)

        # group nodes with the same provider
        for _, nodes in groupby(nodes_to_stop, lambda x: x.configuration.provider.provider_config_id):
            nodes = list(nodes)
            provider_config = nodes[0].configuration.provider
            task_check_name = f"Stopping nodes `{', '.join(sorted([node.node_id for node in nodes]))}`"
            events = self.execute_common_template(
                nodes, provider_config, task_check_name, state, wait='no')
            if not events:
                raise Exception('No events')

            # remove instances...
            task_event = self._get_named_event(events, task_check_name)
            removed_instance_ids = task_event['event_data']['res']['instance_ids']

            if not force:
                successfully_stopped = [node.node_id for node in nodes if
                                        node.cloud_instance_id in removed_instance_ids]
            else:
                successfully_stopped = [node.node_id for node in nodes]
            self.repository.remove_nodes(successfully_stopped)
            stopped_nodes += successfully_stopped

        return stopped_nodes

    def pause_instances(self, nodes_to_pause: List[str], timeout: int = 600) -> List[str]:
        state = 'stopped'
        paused_nodes = []
        nodes_to_pause = self.repository.get_nodes_by_id(nodes_to_pause)

        # group nodes with the same provider
        for _, nodes in groupby(nodes_to_pause, lambda x: x.configuration.provider.provider_config_id):
            nodes = list(nodes)
            provider_config = nodes[0].configuration.provider
            task_check_name = f"Pausing nodes " \
                              f"`{', '.join(sorted([node.node_id for node in nodes]))}`"
            events = self.execute_common_template(
                nodes, provider_config, task_check_name, state)
            if not events:
                raise Exception('No events')

            # remove instances...
            task_event = self._get_named_event(events, task_check_name)
            already_paused_instance_ids = task_event['event_data']['res']['instance_ids']
            paused_instances = {i['id']: i for i in
                                task_event['event_data']['res']['instances']}

            for node in nodes:
                if node.cloud_instance_id in paused_instances:
                    pass
                elif node.cloud_instance_id in already_paused_instance_ids:
                    pass
                else:
                    logger.error(f"Node `{node.node_id}` with invalid aws "
                                 f"instance id: {node.cloud_instance_id}")
                    continue

                node.ip = None
                node.status = NodeStatus.PAUSED
                self.repository.upsert_node(node)
                paused_nodes.append(node.node_id)

        return paused_nodes

    def resume_instances(self, nodes_to_resume: List[str], timeout: int = 600) -> List[str]:
        state = 'running'
        resumed_nodes = []
        nodes_to_resume = self.repository.get_nodes_by_id(nodes_to_resume)

        # group nodes with the same provider
        for _, nodes in groupby(nodes_to_resume, lambda x: x.configuration.provider.provider_config_id):
            nodes = list(nodes)
            provider_config = nodes[0].configuration.provider
            task_check_name = f"Resuming nodes " \
                              f"`{', '.join(sorted([node.node_id for node in nodes]))}`"
            events = self.execute_common_template(
                nodes, provider_config, task_check_name, state, wait='yes')
            if not events:
                raise Exception('No events')

            # remove instances...
            task_event = self._get_named_event(events, task_check_name)
            already_running_instances = task_event['event_data']['res']['instance_ids']
            resumed_instances = {i['id']: i for i in task_event['event_data']['res']['instances']}

            for node in nodes:
                if node.cloud_instance_id in resumed_instances:
                    instance = resumed_instances[node.cloud_instance_id]
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
                    node.status = NodeStatus.STARTED

                elif node.cloud_instance_id in already_running_instances:
                    pass
                else:
                    logger.error(f"Node `{node.node_id}` with invalid aws instance id: {node.cloud_instance_id}")
                    continue

                self.repository.upsert_node(node)
                resumed_nodes.append(node.node_id)

        return resumed_nodes

    def update_instance_info(self, nodes_to_check: List[str], timeout: int = 600) -> Dict[str, str]:
        nodes_to_check = self.repository.get_nodes_by_id(nodes_to_check)
        # group nodes with the same provider
        checked_nodes = dict()
        for _, nodes in groupby(nodes_to_check, lambda x: x.configuration.provider.provider_config_id):
            nodes = list(nodes)
            provider_config = nodes[0].configuration.provider
            task_check_name = f"Checking nodes " \
                              f"`{', '.join(sorted([node.node_id for node in nodes]))}`"
            events = self.execute_check_template(
                nodes, provider_config, task_check_name, quiet=True)
            if not events:
                raise Exception('No events')

            # remove instances...
            task_event = self._get_named_event(events, task_check_name)
            instances_status = {i['instance_id']: i for i in
                                task_event['event_data']['res']['instances']}

            for node in nodes:
                if node.cloud_instance_id not in instances_status:
                    logger.error(f"Node `{node.node_id}` with invalid aws "
                                 f"instance id: {node.cloud_instance_id}")
                    continue
                instance = instances_status[node.cloud_instance_id]

                if instance['state']['name'] == 'running':
                    node.status = NodeStatus.STARTED
                elif instance['state']['name'] == 'stopped':
                    node.status = NodeStatus.PAUSED
                elif instance['state']['name'] == 'terminated':
                    node.status = NodeStatus.STOPPED
                else:
                    node.status = NodeStatus.UNKNOWN

                if node.status != NodeStatus.STOPPED:
                    node.ip = instance['public_ip_address'] \
                        if 'public_ip_address' in instance else None
                    node.cloud_instance_id = instance['instance_id']
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

                self.repository.upsert_node(node)
                checked_nodes[node.node_id] = node.status

        return checked_nodes
