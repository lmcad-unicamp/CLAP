import os
import jinja2

from typing import List, Dict, Tuple, Any
from jinja2 import Template, StrictUndefined

from clap.common.factory import PlatformFactory
from clap.common.cluster_repository import NodeInfo
from clap.common.driver import Codes
from clap.common.utils import log, yaml_load, tmpdir, path_extend
from .repository import ClusterData, ClusterRepositoryOperations
from .conf import ClusterDefaults


class ConfigurationError(Exception):
    pass

class ClusterState:
    CLUSTER_RUNNING = 'running'
    CLUSTER_PAUSED = 'paused'

def __get_setups__(config_dict: dict) -> dict:
    if 'setups' not in config_dict:
        return {}

    setups = dict()

    def __get_extra__(depth_keys: List[str], extra_dict: dict) -> dict:
        extra = {}
        if type(extra_dict) is not dict:
            raise ConfigurationError("Error in setup `{}`. Extra must be a dictionary".format('.'.join(depth_keys)))
        if not extra_dict:
            raise ConfigurationError("Error in setup `{}`. Extra dictionary must not be empty (omit extra instead)".format('.'.join(depth_keys)))
        for key, val in extra_dict.items():
            val_type = type(val)
            if val_type is not str and val_type is not int and val_type is not float:
                raise ConfigurationError("Error in setup `{}`. Extra values must be a string, integer or float".format('.'.join(depth_keys)))
            extra[key] = val
        
        return extra

    def __get_groups__(depth_keys: List[str], group_list: List[dict]) -> List[dict]:
        in_use_groups = []

        for group_values in group_list:
            extra = {}
            # Check if group has a name and is a valid str
            if 'name' not in group_values:
                raise ConfigurationError("Error in setup `{}`. All groups must have the name key (group name)".format('.'.join(depth_keys)))
            if not group_values['name'] or type(group_values['name']) is not str:
                raise ConfigurationError("Error in setup `{}`. Invalid string for group name: `{}`".format('.'.join(depth_keys), group_values['name']))
            
            # If extra exists, check extra
            if 'extra' in group_values:
                extra = __get_extra__(depth_keys+[group_values['name']], group_values['extra'])

            in_use_groups.append({'name': group_values['name'], 'extra': extra})

        return in_use_groups

    def __check_valid_group_action__(depth_keys: List[str], action_dict: dict) -> dict:
        invalid_keys = [key for key in action_dict.keys() if key not in ['name', 'group', 'extra', 'type']]
        if invalid_keys:
            raise ConfigurationError("Invalid keys `{}` at `{}".format(', '.join(sorted(invalid_keys)), '.'.join(depth_keys)))

        extra = {}
        # Check if action has a name and is a valid str
        if 'name' not in action_dict:
            raise ConfigurationError("Error in setup `{}`. All group actions must have the name key (action name)".format('.'.join(depth_keys)))
        if not action_dict['name'] or type(action_dict['name']) is not str:
            raise ConfigurationError("Error in setup `{}`. Invalid string for action name: `{}`".format('.'.join(depth_keys), action_dict['name']))
        # Check if action has a group and is a valid str
        if 'group' not in action_dict:
            raise ConfigurationError("Error in setup `{}`. All group actions must have the group key (group that will perform the action)".format('.'.join(depth_keys)))
        if not action_dict['group'] or type(action_dict['group']) is not str:
            raise ConfigurationError("Error in setup `{}`. Invalid string for group name: `{}`".format('.'.join(depth_keys), action_dict['group']))
        # If extra exists, check extra
        if 'extra' in action_dict:
            extra = __get_extra__(depth_keys, action_dict['extra'])
        return {'name': action_dict['name'], 'group': action_dict['group'], 'type': 'action', 'extra': extra}

    def __check_valid_command_action__(depth_keys: List[str], action_dict: dict) -> dict:
        invalid_keys = [key for key in action_dict.keys() if key not in ['command', 'type']]
        if invalid_keys:
            raise ConfigurationError("Invalid keys `{}` at `{}".format(', '.join(sorted(invalid_keys)), '.'.join(depth_keys)))

        # Check if action has a command and is a valid str
        if 'command' not in action_dict:
            raise ConfigurationError("Error in setup `{}`. All command actions must have the command key (command to execute)".format('.'.join(depth_keys)))
        if not action_dict['command'] or type(action_dict['command']) is not str:
            raise ConfigurationError("Error in setup `{}`. Invalid string for command: `{}`".format('.'.join(depth_keys), action_dict['commmand']))
        return {'type': 'command', 'command': action_dict['command']}

    def __check_valid_playbook_action__(depth_keys: List[str], action_dict: dict) -> dict:
        invalid_keys = [key for key in action_dict.keys() if key not in ['extra', 'path', 'type']]
        if invalid_keys:
            raise ConfigurationError("Invalid keys `{}` at `{}".format(', '.join(sorted(invalid_keys)), '.'.join(depth_keys)))

        extra = {}
        # Check if action has a name and is a valid str
        if 'path' not in action_dict:
            raise ConfigurationError("Error in setup `{}`. All playbook actions must have the path key (representing the playbook path)".format('.'.join(depth_keys)))
        if not action_dict['path'] or type(action_dict['path']) is not str:
            raise ConfigurationError("Error in setup `{}`. Invalid string for playbook: `{}`".format('.'.join(depth_keys), action_dict['path']))
            # If extra exists, check extra
        if 'extra' in action_dict:
            extra = __get_extra__(depth_keys, action_dict['extra'])
        return {'path': action_dict['path'], 'type': 'playbook', 'extra': extra} 
    
    def __get_actions__(depth_keys: List[str], action_list: List[dict]) -> List[dict]:
        in_use_actions = []
        valid_action_types = ['action', 'playbook', 'command']

        for action_values in action_list:
            action = {}
            # Check the action type: action, playbook or command
            if 'type' not in action_values:
                raise ConfigurationError("Error in setup `{}`. All actions must have the type key (action type)".format('.'.join(depth_keys)))
            if not action_values['type'] or type(action_values['type']) is not str:
                raise ConfigurationError("Error in setup `{}`. Invalid string for action type: `{}`".format('.'.join(depth_keys), action_values['type']))
                
            if action_values['type'] == 'action':
                in_use_actions.append(__check_valid_group_action__(depth_keys+['action'], action_values))
            elif action_values['type'] == 'command':
                in_use_actions.append(__check_valid_command_action__(depth_keys+['command'], action_values))
            elif action_values['type'] == 'playbook':
                in_use_actions.append(__check_valid_playbook_action__(depth_keys+['playbook'], action_values))
            else:
                raise ConfigurationError("Error in setup `{}`. Invalid action type: `{}` (choose from {}) ".format(
                    '.'.join(depth_keys), action_values['type'], ', '.join(valid_action_types)))

        return in_use_actions
    
    for setup_name, setup_values in config_dict['setups'].items():
        invalid_keys = [key for key in setup_values.keys() if key not in ['groups', 'actions']]
        if invalid_keys:
            raise ConfigurationError("Invalid keys `{}` at setup `{}`".format(', '.join(sorted(invalid_keys)), setup_name)) 

        groups, actions = [], []
        if 'groups' in setup_values:
            groups = __get_groups__([setup_name], setup_values['groups'])
        if 'actions' in setup_values:
            actions = __get_actions__([setup_name], setup_values['actions'])
        setups[setup_name] = {'groups': groups, 'actions': actions}

    return setups

def __get_clusters__(config_dict: dict) -> dict:
    if 'clusters' not in config_dict:
        return {}

    clusters = dict()

    def __get_options__(depth_keys: List[str], options_dict: dict, cluster_nodes: dict) -> dict:
        invalid_keys = [key for key in options_dict.keys() if key not in ['ssh_to']]
        if invalid_keys:
            raise ConfigurationError("Invalid keys `{}` at `{}".format(', '.join(sorted(invalid_keys)), '.'.join(depth_keys+['options']))) 
        options = {}
        if 'ssh_to' not in options_dict:
            options['ssh_to'] = ''
        else:
            if options_dict['ssh_to'] not in cluster_nodes:
                raise ConfigurationError("Error in cluster configuration `{}`. Option ssh_to must have a valid node".format('.'.join(depth_keys)))
            options['ssh_to'] = options_dict['ssh_to']
        
        return options

    def __get_nodes__(depth_keys: List[str], nodes_dict: dict) -> dict:
        nodes = {}
        for node_name, node_vals in nodes_dict.items():
            invalid_keys = [key for key in node_vals.keys() if key not in ['type', 'count', 'min_count', 'setups']]
            if invalid_keys:
                raise ConfigurationError("Invalid keys `{}` at `{}".format(', '.join(sorted(invalid_keys)), '.'.join(depth_keys+[node_name])))

            min_count = 1
            setups = []

            if 'type' not in node_vals:
                raise ConfigurationError("Error in cluster configuration `{}`. All cluster nodes must have a type".format('.'.join(depth_keys+[node_name])))
            if type(node_vals['type']) is not str or not node_vals['type']:
                raise ConfigurationError("Error in cluster configuration `{}`. Invalid node type (must be a string)".format('.'.join(depth_keys+[node_name])))
            
            if 'count' not in node_vals:
                raise ConfigurationError("Error in cluster configuration `{}`. All cluster nodes must have a count".format('.'.join(depth_keys+[node_name])))
            if type(node_vals['count']) is not int or node_vals['count'] < 1:
                raise ConfigurationError("Error in cluster configuration `{}`. Invalid count number {} (must be a positive integer)".format(
                    '.'.join(depth_keys+[node_name]), node_vals['count']))
            
            if 'min_count' not in node_vals:
                min_count = node_vals['count']
            elif type(node_vals['min_count']) is not int or node_vals['min_count'] > node_vals['count']:
                raise ConfigurationError("Error in cluster configuration `{}`. Invalid min_count number {} (must be a positive integer and less then count)".format(
                    '.'.join(depth_keys+[node_name]), node_vals['min_count']))
            else:
                min_count = node_vals['min_count']

            if 'setups' in node_vals:
                if type(node_vals['setups']) is not list:
                    raise ConfigurationError("Error in cluster configuration `{}`. Setups must be a list".format('.'.join(depth_keys+[node_name])))
                for setup_name in node_vals['setups']:
                    if not setup_name and type(setup_name) is not str:
                        raise ConfigurationError("Error in cluster configuration `{}`. All setups must be strings".format('.'.join(depth_keys+[node_name])))
                    setups.append(setup_name)
            nodes[node_name] = {'type': node_vals['type'], 'count': node_vals['count'], 'min_count': min_count, 'setups': setups}
        return nodes

    def __get_befores_and_afters__(depth_keys: List[str], cluster_dict: dict):
        checked_vals = {}
        checks = ['before', 'before_all', 'after', 'after_all']
        for check in checks:
            checked_vals[check] = []
            if check not in cluster_dict:
                continue
            if type(cluster_dict[check]) is not list:
                raise ConfigurationError("Error in cluster configuration `{}`. {} option takes a list".format('.'.join(depth_keys), check))
            for val in cluster_dict[check]:
                if not val or type(val) is not str:
                    raise ConfigurationError("Error in cluster configuration `{}`. All {} values must be string".format('.'.join(depth_keys), check))
                checked_vals[check].append(val)
        
        return tuple([checked_vals[check] for check in checks])

    for cluster_name, cluster_values in config_dict['clusters'].items():
        invalid_keys = [key for key in cluster_values.keys() if key not in ['options', 'nodes', 'before', 'before_all', 'after', 'after_all']]
        if invalid_keys:
            raise ConfigurationError("Invalid keys `{}` at cluster configuration `{}`".format(', '.join(sorted(invalid_keys)), cluster_name))

        if 'nodes' not in cluster_values:
            raise ConfigurationError("Cluster `{}` does not have any node".format(cluster_name))
        nodes = __get_nodes__([cluster_name], cluster_values['nodes'])
        options = __get_options__([cluster_name], cluster_values['options'] if 'options' in cluster_values else {}, nodes)
        befores, before_all, afters, after_all = __get_befores_and_afters__([cluster_name], cluster_values)
        clusters[cluster_name] = {
                'options': options, 
                'before': befores, 
                'before_all': before_all,
                'after': afters, 
                'after_all': after_all,
                'nodes': nodes
            }
        
    return clusters

def __validate_cluster_setups__(cluster_name: str, cluster_dict: dict, setups: dict) -> dict:
    check_before_after_setups = {}
    checks = ['before', 'before_all', 'after', 'after_all']

    for check in checks:
        check_before_after_setups[check] = []
        for val in cluster_dict[check]:
            if val not in setups:
                raise ConfigurationError("Error in cluster configuration `{}` (options {}). Setup `{}` was not found".format(cluster_name, check, before))
            check_before_after_setups[check].append({val: setups[val]})

    cluster_dict.update(check_before_after_setups)

    for node_name, node_vals in cluster_dict['nodes'].items():
        setups_vals = []
        for setup in node_vals['setups']:
            if setup not in setups:
                raise ConfigurationError("Error in cluster configuration `{}.{}`. Setup `{}` was not found".format(cluster_name, node_name, setup))
            setups_vals.append({setup: setups[setup]})
        cluster_dict['nodes'][node_name]['setups'] = setups_vals
        
    return cluster_dict

def __perform_replacements__(config, extra_args: Dict[str, str]):
    if type(config) is str:
        return Template(config, undefined=StrictUndefined).render(**extra_args)
    elif type(config) is list or type(config) is tuple:
        return [__perform_replacements__(val, extra_args) for val in config]
    elif type(config) is dict:
        return {__perform_replacements__(k, extra_args): __perform_replacements__(v, extra_args) for k, v in config.items()}
    return config

def __validate_nodes__(cluster_name: str, cluster_data: dict, valid_instances: List[str]) -> dict:
    for node_name, node_vals in cluster_data['nodes'].items():
        if node_vals['type'] not in valid_instances:
            raise ConfigurationError("Error in node `{}`. Invalid instance type `{}`".format(
                '.'.join([cluster_name, node_name]), node_vals['type']))
    return cluster_data

def __validate_groups_and_actions__(cluster_name: str, cluster_data: dict, valid_groups: Dict[str, List[str]]) -> dict:
    def __validate_setup__(depth_keys: List[str], setup_values: dict, valid_groups: Dict[str, List[str]]):
        for group in setup_values['groups']:
            if group['name'].split('/')[0] not in valid_groups:
                raise ConfigurationError("Error in setup: `{}`. Group `{}` does not exists".format(
                    '.'.join(depth_keys), group['name']))
        
        for action in setup_values['actions']:
            if action['type'] == 'action':
                if action['group'].split('/')[0] not in valid_groups:
                    raise ConfigurationError("Error in setup: `{}`. Invalid group `{}` for action `{}`".format(
                        '.'.join(depth_keys), action['group'], action['name']))
                if action['name'] not in valid_groups[action['group']]:
                    raise ConfigurationError("Error in setup: `{}`. Invalid action `{}` for group `{}`".format(
                        '.'.join(depth_keys), action['name'], action['group']))
            
            elif action['type'] == 'playbook':
                if not os.path.exists(action['path']) or not os.path.isfile(action['path']):
                    raise ConfigurationError("Error in setup: `{}`. Invalid playbook file at `{}`".format(
                        '.'.join(depth_keys), action['path']))
    
    checks = ['before', 'before_all', 'after', 'after_all']
    for check in checks:
        for val in cluster_data[check]:
            for setup_name, setup in val.items():
                __validate_setup__([cluster_name, check, setup_name], setup, valid_groups)

    return cluster_data

def __add_nodes_to_cluster__(cluster: ClusterData, node_types: Dict[str, Tuple[int, int]]) -> Dict[str, List[str]]: 
    node_module = PlatformFactory.get_module_interface().get_module('node')
    tag_module = PlatformFactory.get_module_interface().get_module('tag')

    # To nodes dict has instance type as key and holds the following information:
    # * [minimum] The minimum number of each instance type
    # * [desired] The desired number of each intance type
    # * [names] The list of nodes of the cluster which uses this instance type
    # * [instantiateds] Nodes created with this instance type
    nodes = dict()

    # Iterate over nodes and count minimum and maximum instance types
    for node_name, (count, min_count) in node_types.items():
        # Instance type not in the nodes dict yet?
        if node_name not in cluster.cluster_config['nodes']:
            raise Exception("Invalid node type `{}` for cluster `{}`".format(node_name, cluster.cluster_name))
        node_type = cluster.cluster_config['nodes'][node_name]['type']
        if node_type not in nodes:
            nodes[node_type] = {
                'desired': count,
                'minimum': min_count,
                'names': [node_name],
                'instantiateds': []
            }
        else:
            nodes[node_type]['desired'] += count
            nodes[node_type]['minimum'] += min_count
            nodes[node_type]['names'].append(node_name)
    
    # Start each instance with their desired counts
    created_nodes = node_module.start_nodes({instance_type: instance_vals['desired'] 
        for instance_type, instance_vals in nodes.items()})

    try:
        # Append each created node to their respective instance type in nodes dict
        for instance_type, instance_vals in nodes.items():
            instance_vals['instantiateds'] = [node for node in created_nodes if node.instance_type == instance_type]

        # Check if the minimum number of each instance type was reached
        non_reachable_nodes = []
        for instance_type, instance_vals in nodes.items():
            # Filter reachable nodes
            reachable_nodes = [node for node in instance_vals['instantiateds'] if node.status == Codes.NODE_STATUS_REACHABLE] 
            # Reacheble nodes of this type reached the minimum?
            if len(reachable_nodes) < instance_vals['minimum']:
                # Failed to instantiate the minumum number
                log.error("Minimum number of reachable `{}` instances were not reached for nodes: {} of cluster `{}`".format(
                        instance_type, ', '.join(instance_vals['names']), cluster.cluster_name))
                log.error("Terminating all instantiated cluster nodes: {}".format(', '.join([node.node_id for node in created_nodes])))
                node_module.stop_nodes([node.node_id for node in created_nodes])
                raise Exception("Failed to create cluster")

            # Filter non-reachable nodes and replace the instantiateds of this type only with reachable ones
            non_reachable_nodes += [node for node in instance_vals['instantiateds'] if node.status != Codes.NODE_STATUS_REACHABLE]
            instance_vals['instantiateds'] = reachable_nodes

        # Is there any non_reachable nodes? Stop them
        if non_reachable_nodes:
            stopped_ones = node_module.stop_nodes([node.node_id for node in non_reachable_nodes])
            # Error stopping nodes
            if len(stopped_ones) != len(non_reachable_nodes):
                log.error("Only {} of {} non reachable nodes were stopped.".format(len(stopped_ones), len(non_reachable_nodes)))

        nodes_of_cluster_type = dict()

        # Distribute the instantiated instances to each node types of the cluster
        for instance_type, instance_vals in nodes.items():
            cluster_nodes_types = {
                node_name: {    
                    'min_count': node_types[node_name][1], 
                    'count': node_types[node_name][0],
                    'type': instance_type,
                    'nodes': []
                } 
                for node_name in instance_vals['names']
            }
            
            for node_type_name, node_vals in cluster_nodes_types.items():
                node_vals['nodes'] = instance_vals['instantiateds'][:node_vals['min_count']]
                instance_vals['instantiateds'] = instance_vals['instantiateds'][node_vals['min_count']:]

            for node_type_name, node_vals in cluster_nodes_types.items():
                needed_len = node_vals['count'] - len(node_vals['nodes'])
                if needed_len >= len(instance_vals['instantiateds']):
                    node_vals['nodes'] += instance_vals['instantiateds']
                    instance_vals['instantiateds'] = []
                    break

                else:
                    node_vals['nodes'] += instance_vals['instantiateds'][:needed_len]
                    instance_vals['instantiateds'] = instance_vals['instantiateds'][needed_len:]

            nodes_of_cluster_type.update({node_name: [node.node_id for node in node_vals['nodes']] for node_name, node_vals in cluster_nodes_types.items()})

        for node_type, node_vals in nodes_of_cluster_type.items():
            tags = {
                'clusters': cluster.cluster_id,
                'cluster_node_type': "{}:{}".format(cluster.cluster_id, node_type)
                #'cluster_setup': "{}:{}".format(cluster.cluster_id, 'no')
            }
            
            tag_module.node_add_tag(node_vals, tags)
        
        return nodes_of_cluster_type
    except Exception as e:
        log.error("Caugth exception: {}".format(e))
        log.error("Stopping started nodes... please wait...")
        node_module.stop_nodes([node.node_id for node in created_nodes])
        raise
    
def __add_to_group__(setup_name: str, group: dict, node_ids: List[str], tags: Dict[str, str] = None, re_add_to_group: bool = False) -> List[str]:
    group_module = PlatformFactory.get_module_interface().get_module('group')
    node_ids = node_ids if node_ids else []
    tags = tags if tags else {}
    return group_module.add_group_to_node(node_ids, group['name'], group['extra'], tags=tags, re_add_to_group=re_add_to_group)

def __execute_action__(setup_name: str, action: dict, node_ids: List[str] = None, tags: Dict[str, str] = None):
    node_module = PlatformFactory.get_module_interface().get_module('node')
    group_module = PlatformFactory.get_module_interface().get_module('group')
    
    node_ids = node_ids if node_ids else []
    tags = tags if tags else {}

    if action['type'] == 'action':
        log.info("Performing `{}` action `{}` from setup: `{}` (extra: {})".format(
                action['group'], action['name'], setup_name, action['extra']))
        return group_module.execute_group_action(node_ids, action['group'], action['name'], action['extra'], tags=tags)
    elif action['type'] == 'playbook':
        log.info("Running playbook `{}` from setup: `{}`(extra:{})".format(
                action['path'], setup_name, action['extra']))
        return run_playbook_in_nodes(action['path'], [node.node_id for node in node_module.list_nodes(node_ids, tags=tags)], action['extra'])
    elif action['type'] == 'command':
        log.info("Executing command `{}` from setup: `{}`".format(action['command'], setup_name))
        return run_command([node.node_id for node in node_module.list_nodes(node_ids, tags=tags)], action['command'])
    else:
        raise Exception("Invalid action type `{}`".format(action['type']))

def __run_setup__(  cluster_name: str, setup_name: str, setup_dict: dict, node_ids: List[str] = None, 
                    tags: Dict[str, str] = None, re_add_to_group: bool = False):
    log.info("Executing setup `{}` in nodes `{}`".format(setup_name, ', '.join(sorted(node_ids))))

    for group in setup_dict['groups']:
        __add_to_group__(setup_name, group, node_ids, tags, re_add_to_group=re_add_to_group)
    for action in setup_dict['actions']:
        __execute_action__(setup_name, action, node_ids, tags)

def __run_setup_list__(cluster_name: str, setup_list: List[Dict[str, Any]], node_ids: List[str], re_add_to_group: bool):
    if not node_ids or not setup_list:
        return

    for _setup in setup_list:
        for setup_name, setup in _setup.items():
             __run_setup__(cluster_name, setup_name, setup, node_ids=node_ids, re_add_to_group=re_add_to_group)

def __get_nodes_to_stop__(cluster_id: str, node_ids: List[str]) -> Tuple[List[str], List[str]]:
    node_module = PlatformFactory.get_module_interface().get_module('node')
    tag_module = PlatformFactory.get_module_interface().get_module('tag')
    repository = ClusterRepositoryOperations()
    cluster = repository.get_cluster(cluster_id)

    if not node_ids:
        return [], []

    nodes = node_module.list_nodes(node_ids)
    for node in nodes:
        if 'clusters' not in node.tags:
            raise Exception("Node `{}` does not belong to cluster `{}`".format(node.node_id, cluster_id))
        if cluster_id not in node.tags['clusters']:
            raise Exception("Node `{}` does not belong to cluster `{}`".format(node.node_id, cluster_id))

    node_types = ["{}:{}".format(cluster_id, node_name) for node_name in list(cluster.cluster_config['nodes'].keys())]
    tag_module.node_remove_tag(node_ids, {'clusters': cluster_id})
    for node_type in node_types:
        tag_module.node_remove_tag(node_ids, {'cluster_node_type': node_type})
    
    to_stop_nodes = []
    to_not_stop_nodes = []
 
    for node in node_module.list_nodes(node_ids):
        if 'clusters' not in node.tags:
            to_stop_nodes.append(node.node_id)
        else:
            to_not_stop_nodes.append(node.node_id)

    return to_stop_nodes, to_not_stop_nodes

#
# PUBLIC FUNCTIONS
#

def get_cluster_config(cluster_files: List[str], cluster_name: str, extra_args: Dict[str, str] = None):
    group_module = PlatformFactory.get_module_interface().get_module('group')
    template_module = PlatformFactory.get_module_interface().get_module('template')

    setups = dict()
    clusters = dict()
    extra_args = extra_args if extra_args else {}

    cluster_datas = [yaml_load(f) for f in cluster_files]

    # Read setup information
    for cluster_data in cluster_datas:
        setups.update(__get_setups__(cluster_data))
    # Read cluster information
    for cluster_data in cluster_datas:
        clusters.update(__get_clusters__(cluster_data))

    # Cluster name is not a valid one?
    if cluster_name not in clusters:
        raise KeyError("Cluster `{}` not found in configuration files".format(cluster_name))

    # Get the cluster configuration
    cluster_data = clusters[cluster_name]

    # Check cluster configuration
    cluster_data = __validate_cluster_setups__(cluster_name, cluster_data, setups)

        # Perform jinja substitutions
    cluster_data = __perform_replacements__(cluster_data, extra_args)

    # Validate nodes
    valid_instances = template_module.list_instance_types()
    cluster_data = __validate_nodes__(cluster_name, cluster_data, valid_instances)

    # Validate Groups
    valid_group_actions = {group['name']: group['actions'] for group in group_module.list_groups()}
    cluster_data = __validate_groups_and_actions__(cluster_name, cluster_data, valid_group_actions)

    return cluster_data

def cluster_create( cluster_files: List[str], cluster_name: str, extra_args: Dict[str, str] = None, 
                    no_setup: bool = False) -> Tuple[ClusterData, List[NodeInfo], bool]:
    node_module = PlatformFactory.get_module_interface().get_module('node')
    
    # Create a new repository 
    repository = ClusterRepositoryOperations()
    cluster_data = get_cluster_config(cluster_files, cluster_name, extra_args)
    cluster = repository.new_cluster(cluster_name, cluster_data)
    try:
        created_nodes = __add_nodes_to_cluster__(
            cluster, {node_name: (node_vals['count'], node_vals['min_count']) for node_name, node_vals in cluster_data['nodes'].items()})
    except Exception:
        repository.remove_cluster(cluster.cluster_id)
        raise
    
    is_setup = False

    if not no_setup:
        try:
            cluster_setup(cluster.cluster_id, nodes_type=created_nodes)
            is_setup = True
        except Exception as e:
            log.error(e)

    node_ids = set([node_id for node_name, node_list in created_nodes.items() for node_id in node_list])
    return cluster, node_module.list_nodes(list(node_ids)), is_setup

def add_nodes_to_cluster(cluster_id: str, node_types: Dict[str, int] = None, no_setup: bool = False, re_add_to_group: bool = False, at: str = 'before_all') -> Tuple[ClusterData, List[NodeInfo]]:
    node_module = PlatformFactory.get_module_interface().get_module('node')
    cluster = ClusterRepositoryOperations().get_cluster(cluster_id)
    created_nodes = __add_nodes_to_cluster__(cluster, {node_type: (qtde, qtde) for node_type, qtde in node_types.items()})
    if not no_setup:
        cluster_setup(cluster_id, nodes_type=created_nodes, re_add_to_group=re_add_to_group, at=at)
    node_ids = set([node for node_name, node_list in created_nodes.items() for node in node_list])
    return cluster, node_module.list_nodes(list(node_ids))

def add_existing_nodes_to_cluster(cluster_id: str, node_types: Dict[str, List[str]], no_setup: bool = False, re_add_to_group: bool = False, at: str = 'before_all'):
    node_module = PlatformFactory.get_module_interface().get_module('node')
    tag_module = PlatformFactory.get_module_interface().get_module('tag')

    repository = ClusterRepositoryOperations()
    cluster = repository.get_cluster(cluster_id)
    node_ids = []

    for node_name, node_list in node_types.items():
        valids = node_module.list_nodes(node_list)
        if node_name not in cluster.cluster_config['nodes']:
            raise ValueError("Invalid node `{}` for cluster `{}`".format(node_name, cluster.cluster_name))
        node_ids += node_list
    
    # Tag them
    for node_type, node_vals in node_types.items():
        tags = {
            'clusters': cluster_id,
            'cluster_node_type': "{}:{}".format(cluster_id, node_type)
        }
        
        tag_module.node_add_tag(node_vals, tags)

    if not no_setup:
        cluster_setup_in_specific_nodes(cluster_id, node_ids=node_ids, re_add_to_group=re_add_to_group, at=at)

def cluster_setup(  cluster_id: str, nodes_type: Dict[str, List[str]] = None, re_add_to_group: bool = False, 
                    at: str = 'before_all'):
    node_module = PlatformFactory.get_module_interface().get_module('node')
    cluster = ClusterRepositoryOperations().get_cluster(cluster_id)

    if not nodes_type:
        nodes_type = {}
        for node_name in cluster.cluster_config['nodes'].keys():
            tags = {'cluster_node_type': "{}:{}".format(cluster.cluster_id, node_name)}
            nodes_type[node_name] = [node.node_id for node in node_module.list_nodes(tags=tags)]

    # TODO the nodes must be gotten when performing the action (avoid terminating node before....)
    all_nodes = [node_id for node_name, node_list in nodes_type.items() for node_id in node_list]
    all_cluster_nodes = [node.node_id for node in node_module.list_nodes(tags={'clusters': "{}".format(cluster.cluster_id)})]

    setups = ['before_all', 'before', 'node', 'after', 'after_all']
    if at not in setups:
        raise Exception("Invalid phase to start setup: `{}`".format(at))

    setups = setups[setups.index(at):]
    setups_to_execute = []

    if 'before_all' in setups:
        setups_to_execute.append((cluster.cluster_name, cluster.cluster_config['before_all'], all_cluster_nodes, re_add_to_group))
    
    if 'before' in setups:
        setups_to_execute.append((cluster.cluster_name, cluster.cluster_config['before'], all_nodes, re_add_to_group))
        
    if 'node' in setups:
        for node_name, node_list in nodes_type.items():
            setups_to_execute.append((cluster.cluster_name, cluster.cluster_config['nodes'][node_name]['setups'], node_list, re_add_to_group))
    
    if 'after' in setups:
        setups_to_execute.append((cluster.cluster_name, cluster.cluster_config['after'], all_nodes, re_add_to_group))

    if 'after_all' in setups:
        setups_to_execute.append((cluster.cluster_name, cluster.cluster_config['after_all'], all_cluster_nodes, re_add_to_group))

    for execute_args in setups_to_execute:
        __run_setup_list__(*execute_args)

    #tags = {'cluster_setup': "{}:{}".format(cluster.cluster_id, 'ok')}
    #tag_module.node_add_tag(all_nodes, tags)

def cluster_setup_in_specific_nodes( cluster_id: str, node_ids: List[str] = None, 
                                     re_add_to_group: bool = False, at: str = 'before_all'):
    node_module = PlatformFactory.get_module_interface().get_module('node')
    cluster = ClusterRepositoryOperations().get_cluster(cluster_id)

    all_cluster_nodes = [node.node_id for node in node_module.list_nodes(tags={'clusters': "{}".format(cluster.cluster_id)})]
    if node_ids:
        invalid_nodes = [node for node in node_ids if node not in all_cluster_nodes]
        if invalid_nodes:
            raise Exception("Nodes `{}` does not belong to cluster `{}`".format(', '.join(sorted(invalid_nodes)), cluster_id))

        nodes_type = {}
        for node_name in cluster.cluster_config['nodes'].keys():
            tags = {'cluster_node_type': "{}:{}".format(cluster.cluster_id, node_name)}
            nodes = [node.node_id for node in node_module.list_nodes(tags=tags)]
            nodes_type[node_name] = [node_id for node_id in node_ids if node_id in nodes]

        cluster_setup(cluster_id, nodes_type=nodes_type, re_add_to_group=re_add_to_group, at=at)
    else:
        cluster_setup(cluster_id, nodes_type=None, re_add_to_group=re_add_to_group, at=at)

def update_cluster_config(cluster_files: List[str], cluster_id: str, extra_args: Dict[str, str] = None) -> ClusterData:
    repository = ClusterRepositoryOperations()
    cluster = repository.get_cluster(cluster_id)
    cluster_data = get_cluster_config(cluster_files, cluster.cluster_name, extra_args)
    cluster.cluster_config = cluster_data
    repository.update_cluster(cluster)
    return cluster

def cluster_stop(cluster_id: str, do_not_stop: bool = False) -> Tuple[List[str], List[str]]:
    node_module = PlatformFactory.get_module_interface().get_module('node')
    nodes = node_module.list_nodes(tags={'clusters': cluster_id})
    repository = ClusterRepositoryOperations()
    cluster = repository.get_cluster(cluster_id)
    stopped_nodes, do_not_stopped = __get_nodes_to_stop__(cluster.cluster_id, [node.node_id for node in nodes])

    if do_not_stopped:
        log.info("Nodes `{}` belong to other clusters and will not be stopped".format(', '.join(sorted(do_not_stopped))))

    if stopped_nodes:
        log.info("Stopping nodes `{}`...".format(', '.join(sorted(stopped_nodes))))
        node_module.stop_nodes(stopped_nodes)

    repository.remove_cluster(cluster_id)

    return stopped_nodes, do_not_stopped

def cluster_alive(cluster_id: str) -> Dict[str, bool]:
    node_module = PlatformFactory.get_module_interface().get_module('node')
    repository = ClusterRepositoryOperations()
    cluster = repository.get_cluster(cluster_id)
    alive_nodes = node_module.is_alive([], tags={'clusters': cluster_id})
    cluster.cluster_state = ClusterState.CLUSTER_RUNNING if all(alive_nodes.values()) else ClusterState.CLUSTER_PAUSED
    repository.update_cluster(cluster)
    return alive_nodes

def cluster_pause(cluster_id: str) -> Tuple[List[str], List[str]]:
    node_module = PlatformFactory.get_module_interface().get_module('node')
    repository = ClusterRepositoryOperations()
    cluster = repository.get_cluster(cluster_id)

    pause_nodes, not_pause_nodes = [], []
    nodes = node_module.list_nodes(tags={'clusters': cluster_id})

    for node in nodes:
        not_paused_other_clusters = [other_cluster for other_cluster in node.tags['clusters'] 
                if other_cluster != cluster_id and repository.get_cluster(other_cluster).cluster_state != ClusterState.CLUSTER_PAUSED]
        if not_paused_other_clusters:
            not_pause_nodes.append(node.node_id)
        else:
            pause_nodes.append(node.node_id)

    log.info("Pausing nodes `{}`".format(', '.join(sorted(pause_nodes))))
    if not_pause_nodes:
        log.info("Nodes `{}` belong to other clusters that are not paused. These nodes will not be paused".format(
                ', '.join(sorted(not_pause_nodes))))

    if pause_nodes:
        paused_nodes = node_module.pause_nodes(pause_nodes)

    cluster.cluster_state = ClusterState.CLUSTER_PAUSED
    repository.update_cluster(cluster)
    return pause_nodes, not_pause_nodes

def cluster_resume(cluster_id: str, setup: bool = False, at='before_all') -> List[str]:
    node_module = PlatformFactory.get_module_interface().get_module('node')
    repository = ClusterRepositoryOperations()
    cluster = repository.get_cluster(cluster_id)
    resumed_nodes =  node_module.resume_nodes([], tags={'clusters': cluster_id})
    cluster.cluster_state = ClusterState.CLUSTER_RUNNING
    repository.update_cluster(cluster)

    if setup:
        cluster_setup(cluster_id, nodes_type=None, re_add_to_group=False, at=at)

    return resumed_nodes

def list_clusters(cluster_id: str = None) -> dict:
    node_module = PlatformFactory.get_module_interface().get_module('node')
    repository = ClusterRepositoryOperations()
    cluster_node_dict = dict()
    clusters = [repository.get_cluster(cluster_id)] if cluster_id else repository.get_all_clusters()
    
    for cluster in clusters:
        nodes = dict()
        for node_name in list(cluster.cluster_config['nodes'].keys()):
            tags = {
                'clusters': cluster.cluster_id,
                'cluster_node_type': "{}:{}".format(cluster.cluster_id, node_name)
            }
            nodes[node_name] = [node.node_id for node in node_module.list_nodes(tags=tags)]

        cluster_node_dict[cluster.cluster_id] = {'cluster': cluster, 'nodes': nodes}

    return cluster_node_dict

def list_templates(cluster_files: List[str]) -> Tuple[dict, dict]:
    setups = dict()
    clusters = dict()

    cluster_datas = [yaml_load(f) for f in cluster_files]

    # Read setup information
    for cluster_data in cluster_datas:
        setups.update(__get_setups__(cluster_data))
    # Read cluster information
    for cluster_data in cluster_datas:
        clusters.update(__get_clusters__(cluster_data))
    
    # Get the cluster configuration
    return clusters, setups

def cluster_group_add(cluster_id: str, group_name: str, node_ids: List[str] = None, re_add_to_group: bool = False, extra_args: Dict[str, str] = None) -> List[str]:
    node_module = PlatformFactory.get_module_interface().get_module('node')
    repository = ClusterRepositoryOperations()
    cluster = repository.get_cluster(cluster_id)
    extra = extra_args if extra_args else {}
    all_cluster_nodes = [node.node_id for node in node_module.list_nodes(tags={'clusters': "{}".format(cluster_id)})]

    if node_ids:
        invalid_nodes = [node_id for node_id in node_ids if node_id not in all_cluster_nodes]
        if invalid_nodes:
            raise Exception("Nodes `{}` does not belong to cluster {}".format(', '.join(sorted(invalid_nodes)), cluster_id))
    else:
        node_ids = all_cluster_nodes
    
    group = {'name': group_name, 'extra': extra_args}
    return __add_to_group__(cluster.cluster_name, group, node_ids=node_ids, re_add_to_group=re_add_to_group)

def perform_group_action(cluster_id: str, group_name: str, action_name: str, node_ids: List[str] = None, extra_args: Dict[str, str] = None) -> List[str]:
    node_module = PlatformFactory.get_module_interface().get_module('node')
    repository = ClusterRepositoryOperations()
    cluster = repository.get_cluster(cluster_id)
    extra = extra_args if extra_args else {}
    all_cluster_nodes = [node.node_id for node in node_module.list_nodes(tags={'clusters': "{}".format(cluster_id)})]

    if node_ids:
        invalid_nodes = [node_id for node_id in node_ids if node_id not in all_cluster_nodes]
        if invalid_nodes:
            raise Exception("Nodes `{}` does not belong to cluster {}".format(', '.join(sorted(invalid_nodes)), cluster_id))
    else:
        node_ids = all_cluster_nodes
    
    action = {'type': 'action', 'group': group_name, 'name': action_name, 'extra': extra}
    return __execute_action__(cluster.cluster_name, action, node_ids=node_ids)

def execute_playbook(cluster_id: str, playbook_path: str, node_ids: List[str] = None, extra_args: Dict[str, str] = None) -> Dict[str, bool]:
    node_module = PlatformFactory.get_module_interface().get_module('node')
    repository = ClusterRepositoryOperations()
    cluster = repository.get_cluster(cluster_id)
    extra = extra_args if extra_args else {}
    all_cluster_nodes = [node.node_id for node in node_module.list_nodes(tags={'clusters': "{}".format(cluster_id)})]

    if node_ids:
        invalid_nodes = [node_id for node_id in node_ids if node_id not in all_cluster_nodes]
        if invalid_nodes:
            raise Exception("Nodes `{}` does not belong to cluster {}".format(', '.join(sorted(invalid_nodes)), cluster_id))
    else:
        node_ids = all_cluster_nodes

    action = {'type': 'playbook', 'path': playbook_path, 'extra': extra}
    return __execute_action__(cluster.cluster_name, action, node_ids=node_ids)

def execute_command(cluster_id: str, command: str, node_ids: List[str] = None) -> Dict[str, bool]:
    node_module = PlatformFactory.get_module_interface().get_module('node')
    repository = ClusterRepositoryOperations()
    cluster = repository.get_cluster(cluster_id)
    all_cluster_nodes = [node.node_id for node in node_module.list_nodes(tags={'clusters': "{}".format(cluster_id)})]

    if node_ids:
        invalid_nodes = [node_id for node_id in node_ids if node_id not in all_cluster_nodes]
        if invalid_nodes:
            raise Exception("Nodes `{}` does not belong to cluster {}".format(', '.join(sorted(invalid_nodes)), cluster_id))
    else:
        node_ids = all_cluster_nodes

    action = {'type': 'command', 'command': command}
    return __execute_action__(cluster.cluster_name, action, node_ids=node_ids)

def cluster_copy_files(cluster_id: str, copy_from: str, copy_to: str, node_ids: List[str] = None):
    playbook_path = path_extend(os.path.dirname(os.path.abspath(__file__)), 'copy-files.yml')
    return execute_playbook(cluster_id, playbook_path, node_ids, extra_args=dict(src=copy_from, dest=copy_to))

def cluster_fetch_files(cluster_id: str, copy_from: str, copy_to: str, node_ids: List[str] = None):
    playbook_path = path_extend(os.path.dirname(os.path.abspath(__file__)), 'fetch-files.yml')
    return execute_playbook(cluster_id, playbook_path, node_ids, extra_args=dict(src=copy_from, dest=copy_to))

def cluster_connect(cluster_id: str, node_id: str = None):
    node_module = PlatformFactory.get_module_interface().get_module('node')
    repository = ClusterRepositoryOperations()
    cluster = repository.get_cluster(cluster_id)

    if not cluster.cluster_config['options']['ssh_to'] and not node_id:
        raise Exception("You must supply a ssh_to option or an node_id to connect")

    if node_id:
        all_cluster_nodes = [node.node_id for node in node_module.list_nodes(tags={'clusters': "{}".format(cluster_id)})]
        if node_id not in all_cluster_nodes:
            raise Exception("Node `{}` does not belong to cluster `{}`".format(node_id, cluster_id))
        connect_to_node(node_id)
    else:
        ssh_nodes = [node.node_id for node in node_module.list_nodes(tags={
            'clusters': "{}".format(cluster_id),
            'cluster_node_type': "{}:{}".format(cluster.cluster_id, cluster.cluster_config['options']['ssh_to'])
            })]
        if not ssh_nodes:
            raise Exception("No `{}` nodes in `{}` to connect".format(cluster.cluster_config['options']['ssh_to'], cluster_id))
        connect_to_node(ssh_nodes[0])

def get_nodes_from_cluster(cluster_id: str) -> List[str]:
    node_module = PlatformFactory.get_module_interface().get_module('node')
    repository = ClusterRepositoryOperations()
    cluster = repository.get_cluster(cluster_id)
    return [node.node_id for node in node_module.list_nodes(tags={'clusters': "{}".format(cluster.cluster_id)})]

def get_node_types_from_cluster(cluster_id: str) -> Dict[str, List[str]]:
    nodes_type = dict()
    repository = ClusterRepositoryOperations()
    cluster = repository.get_cluster(cluster_id)
    for node_name in cluster.cluster_config['nodes'].keys():
        tags = {'cluster_node_type': "{}:{}".format(cluster.cluster_id, node_name)}
        nodes_type[node_name] = [node.node_id for node in node_module.list_nodes(tags=tags)]
    
    return nodes_type

def stop_nodes_from_cluster_by_type(cluster_id: str, nodes_type: Dict[str, int]) -> Tuple[List[str], List[str]]:
    node_module = PlatformFactory.get_module_interface().get_module('node')
    cluster = ClusterRepositoryOperations().get_cluster(cluster_id)
    nodes = []

    for node_name, qtde in nodes_type.items():
        if node_name not in cluster.cluster_config['nodes'].keys():
            raise Exception("Invalid node type: `{}`".format(node_name))
    
        tags = {'cluster_node_type': "{}:{}".format(cluster.cluster_id, node_name)}
        typed_nodes = node_module.list_nodes(tags=tags)
        if len(typed_nodes) < qtde:
            raise Exception("Requested to stop {} `{}` nodes but only {} exists".format(qtde, node_name, len(typed_nodes)))
        nodes += [node.node_id for node in typed_nodes[:qtde]]

    stopped_nodes, do_not_stopped = __get_nodes_to_stop__(cluster_id, nodes)

    if do_not_stopped:
        log.info("Nodes `{}` belong to other clusters and will not be stopped".format(', '.join(sorted(do_not_stopped))))

    if stopped_nodes:
        log.info("Stopping nodes `{}`...".format(', '.join(sorted(stopped_nodes))))
        node_module.stop_nodes(stopped_nodes)

    return stopped_nodes, do_not_stopped


# Default actions....
def run_playbook_in_nodes(playbook_path: str, node_ids: List[str], extra_args: Dict[str, str]) -> Dict[str, bool]:
    node_module = PlatformFactory.get_module_interface().get_module('node')
    return node_module.execute_playbook(playbook_file=playbook_path, node_ids=node_ids, extra_args=extra_args)

def run_command(node_ids: List[str], command_string: str):
    node_module = PlatformFactory.get_module_interface().get_module('node')
    ssh_connections = node_module.get_ssh_connections(node_ids=node_ids)
    
    for node_id in sorted(ssh_connections.keys()):
        ssh = ssh_connections[node_id]
        print('Executing in node `{}` the command (via SSH): `{}`'.format(node_id, command_string))
        _, stdout, stderr = ssh.exec_command(command_string)
        print("{} STD OUTPUT of `{}` {}".format('-'*40, node_id, '-'*40))
        print(''.join(stdout.readlines()))
        print("{} ERR OUTPUT of `{}` {}".format('-'*40, node_id, '-'*40))
        print(''.join(stderr.readlines()))
        print('-' * 80)

        ssh.close()

def connect_to_node(node_id: str):
    node_module = PlatformFactory.get_module_interface().get_module('node')
    print("Connecting to node `{}`".format(node_id))
    node_module.connect_to_node(node_id)
    print("Connection to node `{}` closed".format(node_id))