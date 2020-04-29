import os

from typing import List, Dict, Tuple
from jinja2 import Template, StrictUndefined

from clap.common.factory import PlatformFactory
from clap.common.cluster_repository import NodeInfo
from clap.common.driver import Codes
from clap.common.utils import log, yaml_load
from .repository import ClusterData, ClusterRepositoryOperations
from .conf import ClusterDefaults


class ConfigurationError(Exception):
    pass

class ClusterState:
    CLUSTER_RUNNING = 'running'
    CLUSTER_PAUSED = 'paused'


def __check_if_in_or_default__(data: dict, key: str, default: str, valids: tuple):
    if key not in data:
        if default is not None:
            data[key] = default
        else:
            raise ConfigurationError("Must set a valid `{}` value. Choose from: {}".format(key, valids))
    elif data[key] not in valids:
        raise ConfigurationError('Invalid {} option `{}`. Choose from: {}'.format(key, data[key], valids))
    return data

def __check_if_in_or_default_positive_int__(data: dict, key: str, default: int):
    if key not in data:
        data[key] = int(default)
    if data[key] <= 0:
        raise ConfigurationError('Invalid {} option `{}`. Value must be a positive integer'.format(key, data[key]))
    else:
        data[key] = int(data[key])
    return data

def __check_if_list_is_valid(list_data: list, valids: List[str], at: str = None):
    for data in list_data:
        if data not in valids:
            raise ConfigurationError("Invalid value `{}` at {}. Choose from {}".format(data, at, valids))
    return list_data

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
            extra = __get_extra__(depth_keys+[action_dict['name']], action_dict['extra'])
        return {'name': action_dict['name'], 'group': action_dict['group'], 'type': 'action', 'extra': extra}

    def __check_valid_command_action__(depth_keys: List[str], action_dict: dict) -> dict:
        # Check if action has a command and is a valid str
        if 'commmand' not in action_dict:
            raise ConfigurationError("Error in setup `{}`. All command actions must have the command key (command to execute)".format('.'.join(depth_keys)))
        if not action_dict['commmand'] or type(action_dict['commmand']) is not str:
            raise ConfigurationError("Error in setup `{}`. Invalid string for command: `{}`".format('.'.join(depth_keys), action_dict['commmand']))
        return {'name': action_dict['name'], 'type': 'command', 'command': action_dict['command']}

    def __check_valid_playbook_action__(depth_keys: List[str], action_dict: dict) -> dict:
        extra = {}
        # Check if action has a name and is a valid str
        if 'path' not in action_dict:
            raise ConfigurationError("Error in setup `{}`. All playbook actions must have the path key (representing the playbook path)".format('.'.join(depth_keys)))
        if not action_dict['path'] or type(action_dict['path']) is not str:
            raise ConfigurationError("Error in setup `{}`. Invalid string for playbook: `{}`".format('.'.join(depth_keys), action_dict['path']))
            # If extra exists, check extra
        if 'extra' in action_dict:
            extra = __get_extra__(depth_keys+[action_dict['path']], action_dict['extra'])
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
                in_use_actions.append(__check_valid_group_action__('.'.join(depth_keys+[action['name']]), action_values))
            elif action_values['type'] == 'command':
                in_use_actions.append(__check_valid_command_action__('.'.join(depth_keys+[action['name']]), action_values))
            elif action_values['type'] == 'playbook':
                in_use_actions.append(__check_valid_playbook_action__('.'.join(depth_keys+[action['name']]), action_values))
            else:
                raise ConfigurationError("Error in setup `{}`. Invalid action type: `{}` (choose from {}) ".format(
                    '.'.join(depth_keys), action_values['type'], ', '.join(valid_action_types)))

        return in_use_actions
    
    for setup_name, setup_values in config_dict['setups'].items():
        groups, actions = [], []
        if 'groups' in setup_values:
            groups = __get_groups__([setup_name], setup_values['groups'])
        if 'actions' in setup_values:
            actions = __get_groups__([setup_name], setup_values['actions'])
        setups[setup_name] = {'groups': groups, 'actions': actions}

    return setups

def __get_clusters__(config_dict: dict) -> dict:
    if 'clusters' not in config_dict:
        return {}

    clusters = dict()

    def __get_options__(depth_keys: List[str], options_dict: dict, cluster_nodes: dict) -> dict:
        options = {}
        if 'ssh_to' not in options_dict:
            options['ssh_to'] = ''
        else:
            if options_dict['ssh_to'] not in cluster_nodes:
                raise ConfigurationError("Error in cluster configuration `{}`. Option ssh_to must have a valid node".format('.'.join(depth_keys)))
            options['ssh_to'] = options_dict['ssh_to']
        
        if 'before' not in options_dict:
            options['before'] = []
        else:
            if type(options_dict['before']) is not list:
                raise ConfigurationError("Error in cluster configuration `{}`. Before option takes a list".format('.'.join(depth_keys)))
            options['before'] = []
            for before in options_dict['before']:
                if not before or type(before) is not str:
                    raise ConfigurationError("Error in cluster configuration `{}`. All before values must be string".format('.'.join(depth_keys)))
                options['before'].append(before)

        if 'after' not in options_dict:
            options['after'] = []
        else:
            if type(options_dict['after']) is not list:
                raise ConfigurationError("Error in cluster configuration `{}`. After option takes a list".format('.'.join(depth_keys)))
            options['after'] = []
            for after in options_dict['after']:
                if not after or type(after) is not str:
                    raise ConfigurationError("Error in cluster configuration `{}`. All after values must be string".format('.'.join(depth_keys)))
                options['after'].append(after)

        return options

    def __get_nodes__(depth_keys: List[str], nodes_dict: dict) -> dict:
        nodes = {}
        for node_name, node_vals in nodes_dict.items():
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

    for cluster_name, cluster_values in config_dict['clusters'].items():
        if 'nodes' not in cluster_values:
            raise ConfigurationError("Cluster `{}` does not have any node".format(cluster_name))
        nodes = __get_nodes__([cluster_name], cluster_values['nodes'])
        options = __get_options__([cluster_name], cluster_values['options'] if 'options' in cluster_values else {}, nodes)
        clusters[cluster_name] = {'options': options, 'nodes': nodes}
        
    return clusters

def __validate_cluster_setups__(cluster_name: str, cluster_dict: dict, setups: dict) -> dict:
    befores, afters = [], []
    for before in cluster_dict['options']['before']:
        if before not in setups:
            raise ConfigurationError("Error in cluster configuration `{}` (options before). Setup `{}` was not found".format(cluster_name, before))
        befores.append(setups[before])
    
    for after in cluster_dict['options']['after']:
        if after not in setups:
            raise ConfigurationError("Error in cluster configuration `{}` (options after). Setup `{}` was not found".format(cluster_name, after))
        afters.append(setups[after])

    cluster_dict['options']['before'] = befores
    cluster_dict['options']['after'] = afters

    for node_name, node_vals in cluster_dict['nodes'].items():
        setups_vals = []
        for setup in node_vals['setups']:
            if setup not in setups:
                raise ConfigurationError("Error in cluster configuration `{}.{}`. Setup `{}` was not found".format(cluster_name, node_name, setup))
            setups_vals.append(setups[setup])
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


def _get_cluster_data(cluster_files: List[str], cluster_name: str, extra_args: Dict[str, str] = None):
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

    return cluster_data


def __check_clusters__(config_dict: dict, valid_instance_types: List[str], valid_setups: List[str]) -> dict:
    clusters = dict()

    if 'clusters' not in config_dict:
        return {}

    for cluster_name, cluster_values in config_dict['clusters'].items():
        nodes = {}
        options = {}

        if 'nodes' not in cluster_values or len(cluster_values['nodes']) == 0:
            raise ConfigurationError("Error in cluster `{}`. Cluster must have the nodes section and at least one node".format(cluster_name))
        
        for node_name, node_vals in cluster_values['nodes'].items():
            if 'type' not in node_vals:
                raise ConfigurationError("Error in cluster `{}.{}`. All nodes must have a type".format(cluster_name, node_name))
            if not node_vals['type'] or type(node_vals['type']) is not str:
                raise ConfigurationError("Error in cluster `{}.{}`. Node type must be a str".format(cluster_name, node_name))

            if 'count' not in node_vals:
                raise ConfigurationError("Error in cluster `{}.{}`. All nodes must have a count".format(cluster_name, node_name))
            if not node_vals['count'] or type(node_vals['count']) is not int or node_vals['count'] < 1:
                raise ConfigurationError("Error in cluster `{}.{}`. Node count must be a positive int".format(cluster_name, node_name))

            if 'min_count' in node_vals:
                if not node_vals['min_count'] or type(node_vals['min_count']) is not int or node_vals['min_count'] > node_vals['count']:
                    raise ConfigurationError("Error in cluster `{}.{}`. Node min_count must be a positive int (and less than or equal count value)".format(cluster_name, node_name))
            else:
                node_vals['min_count'] = node_vals['count']

            if 'setups' in node_vals:
                if type(node_vals['setups']) is not list:
                    raise ConfigurationError("Error in cluster `{}`.{}.nodes. Node setups must be a list".format(cluster_name, node_name))
                __check_if_list_is_valid(node_vals['setups'], valid_setups, "{}.{}.setups".format(cluster_name, node_name))
            else:
                node_vals['setups'] = []

            nodes[node_name] = node_vals
        
        __check_if_list_is_valid([node_vals['type'] for node_name, node_vals in nodes.items()], valid_instance_types, cluster_name)

        # Check options
        if 'options' in cluster_values:
            __check_if_list_is_valid(list(cluster_values['options'].keys()), ['ssh_to'], "{}.options".format(cluster_name))
            if 'ssh_to' in cluster_values['options']:
                if not cluster_values['options']['ssh_to'] or type(cluster_values['options']['ssh_to']) is not str:
                    raise ConfigurationError("Error in cluster `{}`.options. ssh_to must be a str".format(cluster_name))
                __check_if_list_is_valid([cluster_values['options']['ssh_to']], [node_name for node_name, node_vals in nodes.items()], "{}.options.ssh_to".format(cluster_name))

            options = cluster_values['options']

        clusters[cluster_name] = {'options': options, 'nodes': nodes}

    return clusters

def get_cluster_data(cluster_files: List[str], cluster_name: str, extra_args: Dict[str, str] = None):
    group_module = PlatformFactory.get_module_interface().get_module('group')
    template_module = PlatformFactory.get_module_interface().get_module('template')

    extra_args = extra_args if extra_args else {}

    # Get all cluster and setups information
    cluster_datas = [yaml_load(f) for f in cluster_files]

    if not cluster_datas:
        raise ConfigurationError("No files to search")

    # Get the name of instances in the instance module
    valid_instance_types = template_module.list_instance_types()
    # Get the name of the valid groups
    valid_groups = {group['name']: group['actions'] for group in group_module.list_groups()}

    setups = dict()
    clusters = dict()

    # Read and validate setup information
    for cluster_data in cluster_datas:
        setups.update(__check_setup__(cluster_data, valid_groups, extra_args))
    # Read and validate cluster information
    for cluster_data in cluster_datas:
        clusters.update(__check_clusters__(cluster_data, valid_instance_types, list(setups.keys())))

    # Cluster name is not a valid one?
    if cluster_name not in clusters:
        raise KeyError("Cluster `{}` not found in configuration files".format(cluster_name))

    # Get the cluster configuration
    cluster_data = clusters[cluster_name]

    for node_name, node_vals in cluster_data['nodes'].items():
        node_vals['setups'] = [{setup: setups[setup]}for setup in node_vals['setups']]

    return cluster_data

def cluster_create(cluster_files: List[str], cluster_name: str, extra_args: Dict[str, str] = None, no_setup: bool = False) -> Tuple[ClusterData, List[NodeInfo]]:
    # TODO start cluster with 0 nodes
    node_module = PlatformFactory.get_module_interface().get_module('node')
    tag_module = PlatformFactory.get_module_interface().get_module('tag')

    # Create a new repository 
    repository = ClusterRepositoryOperations()
    cluster_data = _get_cluster_data(cluster_files, cluster_name, extra_args)
    
    # To nodes dict has instance type as key and holds the following information:
    # * [minimum] The minimum number of each instance type
    # * [desired] The desired number of each intance type
    # * [names] The list of nodes of the cluster which uses this instance type
    # * [instantiateds] Nodes created with this instance type
    nodes = dict()

    # Iterate over nodes and count minimum and maximum instance types
    for node_name, node_vals in cluster_data['nodes'].items():
        # Instance type not in the nodes dict yet?
        if node_vals['type'] not in nodes:
            nodes[node_vals['type']] = {
                'desired': node_vals['count'],
                'minimum': node_vals['min_count'],
                'names': [node_name],
                'instantiateds': []
            }
        else:
            nodes[node_vals['type']]['desired'] += node_vals['count']
            nodes[node_vals['type']]['minimum'] += node_vals['min_count']
            nodes[node_vals['type']]['names'].append(node_name)


    # Start each instance with their desired numbers
    created_nodes = node_module.start_nodes({instance_type: instance_vals['desired'] 
        for instance_type, instance_vals in nodes.items()})
    # created_nodes = node_module.list_nodes(['node-0', 'node-1', 'node-2', 'node-3', 'node-4'])

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
                    instance_type, ', '.join(instance_vals['names']), cluster_name))
            log.error("Terminating all instantiated cluster nodes: {}".format(', '.join([node.node_id for node in created_nodes])))
            node_module.stop_nodes([node.node_id for node in created_nodes])
            return None, []

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
            node_type: {    
                'min_count': cluster_data['nodes'][node_type]['min_count'], 
                'count': cluster_data['nodes'][node_type]['count'],
                'type': cluster_data['nodes'][node_type]['type'],
                'nodes': []
            } 
            for node_type in instance_vals['names']
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

        nodes_of_cluster_type.update(cluster_nodes_types)

    cluster = repository.new_cluster(cluster_name, cluster_data)
    
    for node_type, node_vals in nodes_of_cluster_type.items():
        tags = {
            'clusters': cluster.cluster_id,
            'cluster_node_type': "{}:{}".format(cluster.cluster_id, node_type)
        }
        
        tag_module.node_add_tag([node.node_id for node in node_vals['nodes']], tags)

    if not no_setup:
        cluster_setup(cluster.cluster_id)

    return cluster, node_module.list_nodes(tags={'clusters': cluster.cluster_id})

def cluster_setup(cluster_id: str, re_add_to_group: bool = False, nodes_type: Dict[str, List[str]] = None):
    node_module = PlatformFactory.get_module_interface().get_module('node')
    group_module = PlatformFactory.get_module_interface().get_module('group')
    repository = ClusterRepositoryOperations()

    cluster = repository.get_cluster(cluster_id)
    log.info("Setting up cluster `{}`".format(cluster_id))

    # Add nodes to group
    for node_name, node_vals in cluster.cluster_config['nodes'].items():
        tags = {
            'clusters': cluster.cluster_id,
            'cluster_node_type': "{}:{}".format(cluster.cluster_id, node_name)
        }

        for setup in node_vals['setups']:
            for setup_name, setup_vals in setup.items():
                for group in setup_vals['groups']:
                    if not nodes_type:
                        log.info("Adding nodes `{}` from cluster `{}` to group `{}` from setup: `{}` (extra: {})".format(
                            node_name, cluster.cluster_id, group['name'], setup_name, group['extra']))
                        final_nodes = group_module.add_group_to_node([], group['name'], group['extra'], tags, re_add_to_group=re_add_to_group)
                        if not final_nodes:
                            raise Exception("No nodes was of type `{}` added to group `{}`".format(node_name, group['name']))
                    elif node_name in nodes_type:
                        log.info("Adding nodes `{}` from cluster `{}` to group `{}` from setup: `{}` (extra: {})".format(
                            node_name, cluster.cluster_id, group['name'], setup_name, group['extra']))
                        final_nodes = group_module.add_group_to_node(nodes_type[node_name], group['name'], group['extra'], re_add_to_group=re_add_to_group)
                        if not final_nodes:
                            raise Exception("No nodes was of type `{}` added to group `{}`".format(node_name, group['name']))
                    else:
                        log.info("Skipping node type `{}`. No match".format(node_name))

        # Setup OK for nodes XXXX
        pass
    

    # Perform actions
    for node_name, node_vals in cluster.cluster_config['nodes'].items():
        tags = {
            'clusters': cluster.cluster_id,
            'cluster_node_type': "{}:{}".format(cluster.cluster_id, node_name)
        }

        for setup in node_vals['setups']:
            for setup_name, setup_vals in setup.items():
                for action in setup_vals['actions']:
                    if action['type'] == 'action':
                        if not nodes_type:
                            log.info("Performing `{}` group's action `{}` (setup: `{}`) on nodes `{}` from cluster `{}` (extra: {})".format(
                                action['group'], action['name'], setup_name, node_name, cluster.cluster_id, action['extra']))
                            ret = group_module.execute_group_action([], action['group'], action['name'], action['extra'], tags)
                            # TODO False not?
                            if False:
                                raise Exception("Some `{}` nodes from cluster `{}` does not successfully executed action `{}` from group `{}`".format(
                                    node_name, cluster.cluster_id, action['name'], action['group']))
                        elif node_name in nodes_type:
                            log.info("Performing `{}` group's action `{}` (setup: `{}`) on nodes `{}` from cluster `{}` (extra: {})".format(
                                action['group'], action['name'], setup_name, node_name, cluster.cluster_id, action['extra']))
                            ret = group_module.execute_group_action(nodes_type[node_name], action['group'], action['name'], action['extra'])
                            # TODO False not?
                            if False:
                                raise Exception("Some `{}` nodes from cluster `{}` does not successfully executed action `{}` from group `{}`".format(
                                    node_name, cluster.cluster_id, action['name'], action['group']))
                        else:
                            log.info("Skipping node type `{}`. No match".format(node_name))

                    elif action['type'] == 'playbook':
                        if not nodes_type:
                            log.info("Running playbook `{}` on nodes `{}` (setup: `{}`) from cluster `{}` (extra:{})".format(
                                action['playbook'], node_name, setup_name, cluster.cluster_id, action['extra']))
                            ret = run_playbook_in_nodes(action['playbook'], node_module.list_nodes(tags=tags), action['extra'])
                            if not all(ret.values()):
                                raise Exception("Some `{}` nodes from cluster `{}` does not successfully executed the playbook `{}`".format(
                                    node_name, cluster.cluster_id, action['playbook']))
                        elif node_name in nodes_type: 
                            log.info("Running playbook `{}` on nodes `{}` (setup: `{}`) from cluster `{}` (extra:{})".format(
                                action['playbook'], node_name, setup_name, cluster.cluster_id, action['extra']))
                            ret = run_playbook_in_nodes(action['playbook'], node_module.list_nodes(nodes_type[node_name]), action['extra'])
                            if not all(ret.values()):
                                raise Exception("Some `{}` nodes from cluster `{}` does not successfully executed the playbook `{}`".format(
                                    node_name, cluster.cluster_id, action['playbook']))
                        else:
                            log.info("Skipping node type `{}`. No match".format(node_name))

                    elif action['type'] == 'command':
                        if not nodes_type:
                            log.info("Executing command `{}` (setup: `{}`) in nodes `{}` of cluster `{}`".format(
                                action['command'], setup_name, node_name, cluster.cluster_id))
                            run_command(node_module.list_nodes(tags=tags), action['command'])
                        elif node_name in nodes_type:
                            log.info("Executing command `{}` (setup: `{}`) in nodes `{}` of cluster `{}`".format(
                                action['command'], setup_name, node_name, cluster.cluster_id))
                            run_command(node_module.list_nodes(nodes_type[node_name]), action['command'])
                        else:
                            log.info("Skipping node type `{}`. No match".format(node_name))

                    else:
                        raise ValueError("Invalid action type `{}`".format(action['type']))

        # Setup OK for nodes XXXX
        pass

def update_cluster_config(cluster_files: List[str], cluster_id: str, extra_args: Dict[str, str] = None) -> ClusterData:
    repository = ClusterRepositoryOperations()
    cluster = repository.get_cluster(cluster_id)
    cluster_data = get_cluster_data(cluster_files, cluster.cluster_name, extra_args)
    cluster.cluster_config = cluster_data
    repository.update_cluster(cluster_data)
    return cluster

def add_nodes_to_cluster(cluster_id: str, node_types: Dict[str, int]) -> List[NodeInfo]:
    node_module = PlatformFactory.get_module_interface().get_module('node')
    tag_module = PlatformFactory.get_module_interface().get_module('tag')

    repository = ClusterRepositoryOperations()
    cluster = repository.get_cluster(cluster_id)
    for node_name, qtde in node_types.items():
        if node_name not in cluster.cluster_config['nodes']:
            raise ValueError("Invalid node `{}` for cluster `{}`".format(node_name, cluster.cluster_name)) 
        if qtde < 1:
            raise ValueError("Invalid quantity of `{}` nodes: {}".format(node_name, qtde))

    created_nodes = []
    nodes_of_cluster_type = {}
    # TODO more smart, starting same instance types instead of node types 
    for node_name, qtde in node_types.items():
        node_type = cluster.cluster_config['nodes'][node_name]
        nodes = node_module.start_nodes({node_type['type']: qtde})
        created_nodes += nodes
        if len(nodes) != qtde or len([node for node in nodes if node.status != Codes.NODE_STATUS_REACHABLE]) != qtde:
            log.error("Not all `{}` could be started and reachable. Undoing the operation and stopping the nodes {}".format(node_name, created_nodes))
            node_module.stop_nodes([node.node_id for node in created_nodes])
            raise Exception("Could not start nodes")

        nodes_of_cluster_type[node_name] = [node.node_id for node in nodes]

    # Tag them
    for node_type, node_vals in nodes_of_cluster_type.items():
        tags = {
            'clusters': cluster_id,
            'cluster_node_type': "{}:{}".format(cluster_id, node_type)
        }
        
        tag_module.node_add_tag(node_vals, tags)

    cluster_setup(cluster_id, nodes_type=nodes_of_cluster_type)
    return node_module.list_nodes([node.node_id for node in created_nodes])

def add_existing_nodes_to_cluster(cluster_id: str, node_types: Dict[str, List[str]]):
    node_module = PlatformFactory.get_module_interface().get_module('node')
    tag_module = PlatformFactory.get_module_interface().get_module('tag')

    repository = ClusterRepositoryOperations()
    cluster = repository.get_cluster(cluster_id)
    nodes_of_cluster_type = {}

    for node_name, qtde in node_types.items():
        if node_name not in cluster.cluster_config['nodes']:
            raise ValueError("Invalid node `{}` for cluster `{}`".format(node_name, cluster.cluster_name))
        if qtde < 1:
            raise ValueError("Invalid quantity of `{}` nodes: {}".format(node_name, qtde))

    for node_name, list_nodes in node_types.items():
        nodes_of_cluster_type[node_name] = [node.node_id for node in node_module.list_nodes(list_nodes)]
    
    # Tag them
    for node_type, node_vals in nodes_of_cluster_type.items():
        tags = {
            'clusters': cluster_id,
            'cluster_node_type': "{}:{}".format(cluster_id, node_type)
        }
        
        tag_module.node_add_tag(node_vals, tags)

    cluster_setup(cluster_id, nodes_type=nodes_of_cluster_type)

def remove_nodes_from_cluster(cluster_id: str, node_ids: List[str], do_not_stop: bool = False) -> Tuple[List[str], List[str]]:
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
    
    if do_not_stop:
        return [node.node_id for node in nodes], None
    
    to_stop_nodes = []
    to_not_stop_nodes = []
 
    for node in node_module.list_nodes(node_ids):
        if 'clusters' not in node.tags:
            to_stop_nodes.append(node.node_id)
        else:
            to_not_stop_nodes.append(node.node_id)

    log.info("Stopping nodes `{}`...".format(', '.join(sorted(to_stop_nodes))))
    if to_not_stop_nodes:
        log.info("Nodes `{}` belong to other clusters and will not be stopped".format(', '.join(sorted(to_not_stop_nodes))))
    node_module.stop_nodes(to_stop_nodes)

    return to_stop_nodes, to_not_stop_nodes

def cluster_stop(cluster_id: str) -> Tuple[List[str], List[str]]:
    node_module = PlatformFactory.get_module_interface().get_module('node')
    nodes = node_module.list_nodes(tags={'clusters': cluster_id})
    stopped_nodes, do_not_stopped = remove_nodes_from_cluster(cluster_id, [node.node_id for node in nodes])
    
    repository = ClusterRepositoryOperations()
    repository.remove_cluster(cluster_id)

    return stopped_nodes, do_not_stopped

def cluster_alive(cluster_id: str) -> Dict[str, bool]:
    node_module = PlatformFactory.get_module_interface().get_module('node')
    repository = ClusterRepositoryOperations()
    cluster = repository.get_cluster(cluster_id)

    alive_nodes = node_module.is_alive([], tags={'clusters': cluster_id})
    if all(alive_nodes.values()):
        cluster.cluster_state = ClusterState.CLUSTER_RUNNING
    else:
        cluster.cluster_state = ClusterState.CLUSTER_PAUSED
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

    
def cluster_resume(cluster_id: str) -> List[str]:
    node_module = PlatformFactory.get_module_interface().get_module('node')
    repository = ClusterRepositoryOperations()
    cluster = repository.get_cluster(cluster_id)
    resumed_nodes =  node_module.resume_nodes([], tags={'clusters': cluster_id})
    cluster.cluster_state = ClusterState.CLUSTER_RUNNING
    repository.update_cluster(cluster)
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

def list_templates():
    pass

def run_playbook_in_nodes(playbook_path: str, node_ids: List[str], extra_args: Dict[str, str]) -> Dict[str, bool]:
    multi_instance = PlatformFactory.get_instance_api()
    return multi_instance.execute_playbook_in_nodes(playbook_path, node_ids, extra_args)

def run_command(node_ids: List[str], command_string: str):
    multi_instance = PlatformFactory.get_instance_api()
    ssh_connections = multi_instance.get_connection_to_nodes(node_ids)
    
    for node_id, ssh in ssh_connections.items():
        print('Executing in node `{}` the command (via SSH): `{}`'.format(node_id, command_string))
        _, stdout, stderr = ssh.exec_command(command_string)
        print("{} STD OUTPUT {}".format('-'*40, '-'*40))
        print(''.join(stdout.readlines()))
        print("{} ERR OUTPUT {}".format('-'*40, '-'*40))
        print(''.join(stderr.readlines()))
        print('-' * 80)

        ssh.close()