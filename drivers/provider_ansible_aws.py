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
from common.node import NodeDescriptor, NodeRepositoryController, NodeStatus, NodeLifecycle, \
    NodeType
from common.provider import AbstractInstanceProvider
from common.repository import RepositoryController, InvalidEntryError
from common.schemas import InstanceInfo, ProviderConfigAWS
from common.utils import path_extend, tmpdir, get_logger

logger = get_logger(__name__)

@dataclass
class NodeExtraInfo:
    extra_id: str
    default_keyname: str = ''
    default_security_group: str = ''


class NodeExtraRepositoryController(RepositoryController):
    def get_extra(self, extra_id: str):
        with self.repository.connect('extra') as db:
            return NodeExtraInfo(**db.get(extra_id))

    def upsert_extra(self, extra: NodeExtraInfo):
        with self.repository.connect('extra') as db:
            db.upsert(extra.extra_id, asdict(extra))


class AnsibleAWSProvider(AbstractInstanceProvider):
    provider = 'aws'
    version = '0.1.0'

    def __init__(self, repository: NodeRepositoryController, verbosity: int = 0):
        super(AnsibleAWSProvider, self).__init__(repository, verbosity)
        self.config = Config()
        self.templates_path = path_extend(os.path.dirname(os.path.abspath(__file__)), 'templates')
        self.jinjaenv = jinja2.Environment(loader=jinja2.FileSystemLoader(self.templates_path), trim_blocks=True,
                                           lstrip_blocks=True)
        extra_repository = self.config.repository_type(
            path_extend(self.config.storage_path, f'provider_ansible_aws{self.config.repository_type.extension}'))
        self.extra_repository = NodeExtraRepositoryController(extra_repository)

    def __run_template_and_collect__(self, filename: str, rendered_template: str, envvars: Dict[str, str],
                                     quiet: bool = False) -> Tuple[int, List[Any]]:
        with tmpdir(suffix='.aws') as tdir:
            filename = path_extend(tdir, filename)
            with open(filename, 'w') as f:
                f.write(rendered_template)

            ret = ansible_runner.run(
                private_data_dir=tdir, playbook=filename, verbosity=self.verbosity, envvars=envvars,
                debug=True if self.verbosity >= 3 else False, quiet=quiet)

            return ret.rc, list(ret.host_events('localhost'))

    def __get_extra__(self, provider_id, login_id):
        extra_id: str = f'{provider_id}-{login_id}'
        try:
            return self.extra_repository.get_extra(extra_id)
        except InvalidEntryError:
            return NodeExtraInfo(extra_id=extra_id)

    def __get_envvars__(self, provider_config: ProviderConfigAWS):
        envvars = os.environ.copy()
        envvars['AWS_ACCESS_KEY'] = open(path_extend(Config().private_path, provider_config.access_keyfile), 'r').read().strip()
        envvars['AWS_SECRET_KEY'] = open(path_extend(Config().private_path, provider_config.secret_access_keyfile), 'r').read().strip()
        envvars['AWS_REGION'] = provider_config.region
        return envvars

    def __start_instances__(self, instance: InstanceInfo, count: int, instance_wait_timeout: int) -> List[str]:
        task_check_name = f"Starting {count} {instance.instance.instance_config_id} instances (timeout {instance_wait_timeout} seconds)"
        envvars = self.__get_envvars__(instance.provider)
        extra = self.__get_extra__(instance.provider.provider_config_id, instance.login.login_config_id)
        if not instance.login.keypair_name:
            instance.login.keypair_name = extra.default_keyname
            instance.login.keypair_private_file = f"{extra.default_keyname}.pem"
            instance.login.keypair_public_file = f"{extra.default_keyname}.pub"
        instance.instance.security_group = instance.instance.security_group or extra.default_security_group

        ec2_vals = {
            'keypair_name': instance.login.keypair_name,
            'instance_type': instance.instance.flavor,
            'image_id': instance.instance.image_id,
            'count': count,
            'wait': 'yes',
            'security_group': instance.instance.security_group,
            'instance_wait_timeout': instance_wait_timeout,
            'instance_tags': {
                'CreatedWith': 'CLAP'
            }
        }

        # If there is a placement group at config..
        if instance.instance.placement_group:
            ec2_vals['placement_group'] = instance.instance.placement_group
        # If there is a network ids at config...
        if instance.instance.network_ids:
            ec2_vals['vpc_subnet_id'] = instance.instance.network_ids
        # Creating volumes
        if instance.instance.boot_disk_size or instance.instance.boot_disk_type or instance.instance.boot_disk_iops or \
                instance.instance.boot_disk_device or instance.instance.boot_disk_snapshot:
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
            count_tag = 'spot-{}'.format(str(random.random())[2:])
            ec2_vals['spot_price'] = instance.instance.price
            ec2_vals['spot_timeout'] = instance.instance.timeout or 600
            ec2_vals['count_tag'] = count_tag
            ec2_vals['instance_tags']['Spot'] = True
            ec2_vals['instance_tags'][count_tag] = True
            ec2_vals['instance_tags']['SpotCountTag'] = count_tag
            task_check_name = f"Starting {count} {instance.instance.instance_config_id} spot instances (timeout {instance_wait_timeout} seconds)"

        ec2_vals['task_name'] = task_check_name

        rendered_template = self.jinjaenv.get_template('ec2_start_instances.j2').render(ec2_vals)
        ret_val, events = self.__run_template_and_collect__('start_instances.yml', rendered_template, envvars)
        if ret_val != 0:
            logger.error("Error executing start instances playbook (non-zero return code)")
            return []

        # Get the instance creation event
        instance_event = [e for e in events if e['event'] == 'runner_on_ok' and e['event_data']['task'] == task_check_name]
        instance_event = instance_event[0]
        created_instances = instance_event['event_data']['res']['instances']
        created_nodes = []

        for fresh_instance in created_instances:
            # Create a new CLAP node
            node_info = self.repository.create_node(
                instance_descriptor=instance,
                cloud_instance_id=fresh_instance['id'],
                ip=fresh_instance['public_ip'],
                status=NodeStatus.STARTED,
                cloud_lifecycle=NodeLifecycle.PREEMPTIBLE if instance.instance.price else NodeLifecycle.NORMAL,
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
            logger.info(f"Created an AWS node: `{node_info.node_id}` - {node_info.nickname} (cloud-instance-id: `{node_info.cloud_instance_id}`)")

        return created_nodes

    def __tag_instances__(self, node_list: List[str]) -> List[str]:
        task_check_name = 'Tagging instances'
        # Group by provider
        node_list = self.repository.get_nodes_by_id(node_list)
        tagged_instances = []

        for _, nodes in groupby(node_list, lambda x: x.configuration.provider.provider_config_id):
            nodes = list(nodes)
            envvars = self.__get_envvars__(nodes[0].configuration.provider)
            names = [{
                'id': node.cloud_instance_id,
                'name': f"{node.configuration.provider.provider_config_id}-{node.node_id}-{node.nickname.replace(' ', '')}"
            } for node in nodes]

            ec2_vals = {
                'task_name': task_check_name,
                'names': names,
            }

            rendered_template = self.jinjaenv.get_template('ec2_tag_instances.j2').render(ec2_vals)
            ret_val, events = self.__run_template_and_collect__('ec2_tag_instances.yml', rendered_template, envvars)
            if ret_val != 0:
                logger.error(f"Error tagging instances `{', '.join(sorted([node.node_id for node in nodes]))}` (non-zero return code)")
            else:
                tagged_instances += [node.node_id for node in nodes]

        return tagged_instances

    def execute_common_template(self, nodes: List[NodeDescriptor], provider_config: ProviderConfigAWS,
                                task_check_name: str, state: str, wait: str = 'no'):
        envvars = self.__get_envvars__(provider_config)
        ec2_vals = {
            'task_name': task_check_name,
            'instance_ids': [node.cloud_instance_id for node in nodes],
            'wait': wait,
            'state': state
        }

        rendered_template = self.jinjaenv.get_template('ec2_common.j2').render(ec2_vals)
        ret_val, events = self.__run_template_and_collect__(
            'ec2_common_{}.yml'.format(state), rendered_template, envvars)
        if ret_val != 0:
            logger.error(f"Error changing state of nodes {','.join([node.node_id for node in nodes])} to {state} (non-zero return code)")
            return []

        return events

    def execute_check_template(self, nodes: List[NodeDescriptor], provider_config: ProviderConfigAWS,
                               task_check_name: str, quiet: bool = False):
        envvars = self.__get_envvars__(provider_config)
        ec2_vals = {
            'task_name': task_check_name,
            'instance_ids': [node.cloud_instance_id for node in nodes],
        }

        rendered_template = self.jinjaenv.get_template('ec2_check.j2').render(ec2_vals)
        ret_val, events = self.__run_template_and_collect__('ec2_check.yml', rendered_template, envvars, quiet=quiet)
        if ret_val != 0:
            logger.error(f"Error checking nodes {','.join([node.node_id for node in nodes])} (non-zero return code)")
            return []

        return events

    def create_extras(self, instance_count_list: List[Tuple[InstanceInfo, int]]):
        successful_instances = []
        for instance, count in instance_count_list:
            extra = self.__get_extra__(instance.provider.provider_config_id, instance.login.login_config_id)
            # No keypair exists yet --> Create a new one
            envvars = self.__get_envvars__(instance.provider)
            if not instance.login.keypair_name and not extra.default_keyname:
                extra.default_keyname = f"key-{extra.extra_id}-{str(random.random())[2:]}"
                values = {
                    'keypair_name': extra.default_keyname,
                    'key_destination': path_extend(self.config.private_path, f"{extra.default_keyname}.pem")
                }
                rendered_template = self.jinjaenv.get_template('ec2_key_create.j2').render(values)
                ret_val, events = self.__run_template_and_collect__('create_keys.yml', rendered_template, envvars)
                if ret_val == 0:
                    self.extra_repository.upsert_extra(extra)
                else:
                    raise Exception(f"Error creating keypair `{extra.default_keyname}` (non-zero return code)")

            if not instance.instance.security_group and not extra.default_security_group:
                extra.default_security_group = f"secgroup-{extra.extra_id}-{str(random.random())[2:]}"
                values = {'security_group': extra.default_security_group}
                rendered_template = self.jinjaenv.get_template('ec2_secgroup_create.j2').render(values)
                ret_val, events = self.__run_template_and_collect__('create_secgroup.yml', rendered_template, envvars)
                if ret_val == 0:
                    self.extra_repository.upsert_extra(extra)
                else:
                    raise Exception(f"Error creating security group `{extra.default_security_group}` (non-zero return code)")

            # Append only if sec group and keypair was generated
            # successful_instances.append(instance)
        # return successful_instances

    def start_instances(self, instance_count_list: List[Tuple[InstanceInfo, int]], timeout: int = 600) -> List[str]:
        created_nodes = []
        for (instance, count) in instance_count_list:
            created_nodes += self.__start_instances__(instance, count, timeout)

        self.__tag_instances__(created_nodes)
        return created_nodes

    def stop_instances(self, nodes_to_stop: List[str], force: bool = True, timeout: int = 600) -> List[str]:
        state = 'absent'
        stopped_nodes = []
        nodes_to_stop = self.repository.get_nodes_by_id(nodes_to_stop)

        # group nodes with the same provider
        for _, nodes in groupby(nodes_to_stop, lambda x: x.configuration.provider.provider_config_id):
            nodes = list(nodes)
            provider_config = nodes[0].configuration.provider
            task_check_name = f"Stopping nodes `{', '.join(sorted([node.node_id for node in nodes]))}`"
            events = self.execute_common_template(nodes, provider_config, task_check_name, state, wait='no')
            if not events:
                raise Exception('No events')

            # remove instances...
            instance_event = next(e for e in list(events) if e['event'] == 'runner_on_ok' and
                                  e['event_data']['task'] == task_check_name)
            removed_instance_ids = instance_event['event_data']['res']['instance_ids']

            successfully_stopped = [node.node_id for node in nodes if node.cloud_instance_id in removed_instance_ids] if not force else [node.node_id for node in nodes]
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
            task_check_name = f"Pausing nodes `{', '.join(sorted([node.node_id for node in nodes]))}`"
            events = self.execute_common_template(nodes, provider_config, task_check_name, state)
            if not events:
                raise Exception('No events')

            # remove instances...
            instance_event = next(e for e in list(events) if e['event'] == 'runner_on_ok' and
                                  e['event_data']['task'] == task_check_name)

            already_paused_instance_ids = instance_event['event_data']['res']['instance_ids']
            paused_instances = {i['id']: i for i in instance_event['event_data']['res']['instances']}

            for node in nodes:
                if node.cloud_instance_id in paused_instances:
                    pass
                elif node.cloud_instance_id in already_paused_instance_ids:
                    pass
                else:
                    logger.error(f"Node `{node.node_id}` with invalid aws instance id: {node.cloud_instance_id}")
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
            task_check_name = f"Resuming nodes `{', '.join(sorted([node.node_id for node in nodes]))}`"
            events = self.execute_common_template(nodes, provider_config, task_check_name, state, wait='yes')
            if not events:
                raise Exception('No events')

            # remove instances...
            instance_event = next(e for e in list(events) if e['event'] == 'runner_on_ok' and
                                  e['event_data']['task'] == task_check_name)

            already_running_instances = instance_event['event_data']['res']['instance_ids']
            resumed_instances = {i['id']: i for i in instance_event['event_data']['res']['instances']}

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
            task_check_name = f"Checking nodes `{', '.join(sorted([node.node_id for node in nodes]))}`"
            events = self.execute_check_template(nodes, provider_config, task_check_name, quiet=True)
            if not events:
                raise Exception('No events')

            # remove instances...
            instance_event = next(e for e in list(events) if e['event'] == 'runner_on_ok' and
                                  e['event_data']['task'] == task_check_name)

            instances_status = {i['instance_id']: i for i in instance_event['event_data']['res']['instances']}

            for node in nodes:
                if node.cloud_instance_id not in instances_status:
                    logger.error(f"Node `{node.node_id}` with invalid aws instance id: {node.cloud_instance_id}")
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
                    node.ip = instance['public_ip_address'] if 'public_ip_address' in instance else None
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
