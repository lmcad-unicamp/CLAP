import os
import random
import time
import uuid

import jinja2

from typing import List, Dict

from clap.executor import AnsiblePlaybookExecutor
from clap.node import NodeDescriptor, NodeStatus, NodeLifecycle, NodeType
from clap.abstract_provider import AbstractInstanceProvider, InstanceDeploymentError
from clap.configs import InstanceInfo, ProviderConfigAWS
from clap.utils import path_extend, tmpdir, get_logger, get_random_name, \
    sorted_groupby

logger = get_logger(__name__)


class AnsibleAWSProvider(AbstractInstanceProvider):
    provider: str = 'aws'
    version: str = '0.1.0'

    def __init__(self, private_dir: str, verbosity: int = 0):
        self.private_path = private_dir
        self.verbosity = verbosity
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
                output_filename, self.private_path, inventory=None,
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
                         wait_timeout: int) -> List[NodeDescriptor]:
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
            ec2_vals['device_name'] = instance.instance.boot_disk_device or \
                                      '/dev/sda1'
            ec2_vals['boot_disk_type'] = instance.instance.boot_disk_type or \
                                         'standard'
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
            raise InstanceDeploymentError(
                "Error executing start instances playbook. "
                f"Non-zero return code ({result.ret_code})")

        # Get the instance creation event
        task_event = self._get_named_event(result.events, task_check_name)
        created_instances = task_event['event_data']['res']['instances']
        created_nodes = []

        for fresh_instance in created_instances:
            lifecycle = NodeLifecycle.PREEMPTIBLE if instance.instance.price \
                else NodeLifecycle.NORMAL
            # Create a new CLAP node
            creation_time = time.time()
            node_info = NodeDescriptor(
                node_id=str(uuid.uuid4()).replace('-', ''),
                configuration=instance,
                nickname=get_random_name().replace(' ', ''),
                cloud_instance_id=fresh_instance['id'],
                ip=fresh_instance['public_ip'],
                status=NodeStatus.STARTED,
                creation_time=creation_time,
                cloud_lifecycle=lifecycle,
                type=NodeType.TYPE_CLOUD,
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
            created_nodes.append(node_info)
            logger.info(
                f"Created an AWS node: ID: {node_info.node_id}; "
                f"NICK: {node_info.nickname}; "
                f"CLOUD ID: {node_info.cloud_instance_id}")

        return created_nodes

    def _tag_instances(self, node_list: List[NodeDescriptor]) -> List[NodeDescriptor]:
        task_check_name = 'Tagging instances'
        tagged_instances = []

        for _, nodes in sorted_groupby(
                node_list, lambda x: x.configuration.provider.provider_config_id).items():
            nodes = list(nodes)
            envvars = self.create_envvars(nodes[0].configuration.provider)
            names = [{
                'id': node.cloud_instance_id,
                'name': f"{node.nickname.replace(' ', '')}-{node.node_id[:8]}"
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
                tagged_instances += nodes

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

    def start_instances(self, instance: InstanceInfo, count: int,
                        timeout: int = 600) -> List[NodeDescriptor]:
        created_nodes = self._start_instances(instance, count, timeout)
        self._tag_instances(created_nodes)
        return created_nodes

    def stop_instances(self, nodes_to_stop: List[NodeDescriptor],
                       timeout: int = 180) -> List[NodeDescriptor]:
        state = 'absent'
        stopped_nodes: List[NodeDescriptor] = []

        # group nodes with the same provider
        for _, nodes in sorted_groupby(
                nodes_to_stop,
                lambda x: x.configuration.provider.provider_config_id).items():
            provider_config = nodes[0].configuration.provider
            task_check_name = f"Stopping nodes " \
                              f"{', '.join(sorted([node.nickname for node in nodes]))}"
            events = self.execute_common_template(
                nodes, provider_config, task_check_name, state, wait='no')
            if not events:
                raise Exception('Stop task returned no events to process')

            # remove instances...
            task_event = self._get_named_event(events, task_check_name)
            removed_instance_ids = task_event['event_data']['res']['instance_ids']
            successfully_stopped = []
            for node in nodes:
                if node.cloud_instance_id in removed_instance_ids:
                    node.status = NodeStatus.STOPPED
                    node.ip = None
                    successfully_stopped.append(node)

            stopped_nodes += successfully_stopped

        return stopped_nodes

    def pause_instances(self, nodes_to_pause: List[NodeDescriptor],
                        timeout: int = 600) -> List[NodeDescriptor]:
        state = 'stopped'
        paused_nodes = []

        # group nodes with the same provider
        for _, nodes in sorted_groupby(
                nodes_to_pause,
                lambda x: x.configuration.provider.provider_config_id).items():
            provider_config = nodes[0].configuration.provider
            task_check_name = f"Pausing nodes " \
                              f"`{', '.join(sorted([node.nickname for node in nodes]))}`"
            events = self.execute_common_template(
                nodes, provider_config, task_check_name, state)
            if not events:
                raise Exception('Pause task returned no events to process')

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
                if node.cloud_instance_id not in paused_instances and \
                        node.cloud_instance_id not in already_paused_instance_ids:
                    logger.error(f"Node '{node.node_id}' has an invalid aws "
                                 f"instance id: {node.cloud_instance_id}")
                    continue

                node.ip = None
                node.status = NodeStatus.PAUSED
                paused_nodes.append(node)

        return paused_nodes

    def resume_instances(self, nodes_to_resume: List[NodeDescriptor],
                         timeout: int = 600) -> List[NodeDescriptor]:
        state = 'running'
        resumed_nodes = []

        # group nodes with the same provider
        for _, nodes in sorted_groupby(
                nodes_to_resume,
                lambda x: x.configuration.provider.provider_config_id).items():
            provider_config = nodes[0].configuration.provider
            task_check_name = f"Resuming nodes " \
                              f"`{', '.join(sorted([node.nickname for node in nodes]))}`"
            events = self.execute_common_template(
                nodes, provider_config, task_check_name, state, wait='yes')
            if not events:
                raise Exception('Resume task returned no events to process')

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
                    logger.error(f"Node `{node.node_id}` with invalid aws "
                                 f"instance id: {node.cloud_instance_id}")
                    continue

                resumed_nodes.append(node)

        return resumed_nodes

    # TODO may run to a race condition
    def update_instance_info(self, nodes_to_check: List[NodeDescriptor],
                             timeout: int = 600) -> List[NodeDescriptor]:
        # group nodes with the same provider
        checked_nodes = list()
        for _, nodes in sorted_groupby(
                nodes_to_check, lambda x: x.configuration.provider.provider_config_id).items():
            nodes = list(nodes)
            provider_config = nodes[0].configuration.provider
            task_check_name = f"Checking nodes " \
                              f"`{', '.join(sorted([node.nickname for node in nodes]))}`"
            events = self.execute_check_template(
                nodes, provider_config, task_check_name, quiet=True)
            if not events:
                raise Exception('Update task returned no events to process')

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

                checked_nodes.append(node)

        return checked_nodes


if __name__ == '__main__':
    from clap.configs import ConfigurationDatabase
    from clap.utils import setup_log
    from clap.node import NodeDescriptor
    from clap.node_manager import NodeRepositoryController
    from clap.repository import RepositoryFactory
    setup_log(verbosity_level=3)

    c = ConfigurationDatabase(
     providers_file='/home/lopani/.clap/configs/providers.yaml',
     logins_file='/home/lopani/.clap/configs/logins.yaml',
     instances_file='/home/lopani/.clap/configs/instances.yaml'
    )

    instance_info = c.instance_descriptors['type-a']
    print(instance_info)

    node_repository_path = '/home/lopani/.clap/storage/nodes.db'
    private_path = '/home/lopani/.clap/private'
    repository = RepositoryFactory().get_repository('sqlite', node_repository_path)
    repository_controller = NodeRepositoryController(repository)
    ansible_aws = AnsibleAWSProvider(private_path)
    # nodes = ansible_aws.start_instances(instance_info, 1)
    # for node in nodes:
    #    repository_controller.upsert_node(node)

    nodes = repository_controller.get_all_nodes()
    # pauseds = ansible_aws.pause_instances(nodes)
    # for p in pauseds:
    #     repository_controller.upsert_node(p)

    # print(f'Sleeping for 120 seconds...')
    # time.sleep(120)

    # resumeds = ansible_aws.resume_instances(nodes)
    # for r in resumeds:
    #     repository_controller.upsert_node(r)

    stoppeds = ansible_aws.stop_instances(nodes)
    for s in stoppeds:
        repository_controller.upsert_node(s)

    print('OK')