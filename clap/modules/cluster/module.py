from typing import List, Dict

from clap.common.factory import PlatformFactory
from clap.common.cluster_repository import NodeInfo
from clap.common.driver import Codes
from clap.common.utils import log, yaml_load
from .repository import ClusterData, ClusterRepositoryOperations


class ConfigurationError(Exception):
    pass


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

def __get_cluster_options__(cluster_data: dict):
    options = {} if 'options' not in cluster_data else cluster_data['options']
    if type(options) is not dict:
        raise ConfigurationError("Option values must be a dictionary")

    instantiation_options = ['create']
    on_instantiate_fail_options = ['delete']
    strategy_options = ['auto']

    options = __check_if_in_or_default__(options, 'instantiation', instantiation_options[0], instantiation_options)
    options = __check_if_in_or_default__(options, 'on_instantiate_fail', on_instantiate_fail_options[0], on_instantiate_fail_options)
    options = __check_if_in_or_default__(options, 'strategy', strategy_options[0], strategy_options)
    return options

def __get_nodes_values__(cluster_data: dict, valid_instance_types: List[str], valid_groups: Dict[str, List[str]]):
    if 'nodes' not in cluster_data:
        raise ConfigurationError("Nodes value not found in configuration")

    nodes = cluster_data['nodes']
    added_nodes = []

    if type(nodes) is not list:
        raise ConfigurationError("Node values must be a list")

    for node in nodes:
        valid_keys = ['type', 'count', 'min_count','actions', 'groups']
        invalid_keys = [k for k in list(node.keys()) if k not in valid_keys]
        if invalid_keys:
            raise ConfigurationError("The node contain the following invalid key values: {}. Choose from {}".format(invalid_keys, valid_keys))

        node = __check_if_in_or_default__(node, 'type', None, valid_instance_types)
        node = __check_if_in_or_default_positive_int__(node, 'count', 1)
        node = __check_if_in_or_default_positive_int__(node, 'min_count', node['count'])
        if node['min_count'] > node['count']:
            raise ConfigurationError("min_count must be less or equal count value")

        if 'groups' in node:
            __check_if_list_is_valid([g['name'] for g in node['groups']], list(valid_groups.keys()), 'groups')
            for group in node['groups']:
                if 'extra' not in group:
                    group['extra'] = {}
        else:
            node['groups'] = []
        
        if 'actions' in node:
            for action in node['actions']:
                if 'action' not in action:
                    raise ConfigurationError("All actions listed must have the `action` key")
                if 'group' not in action:
                    raise ConfigurationError('Action `{}` without belonging to any group. All actions must have a group'.format(
                            action['action']))

                __check_if_list_is_valid([action['group']], list(valid_groups.keys()), 'groups')
                if action['action'] not in valid_groups[action['group']]:
                    raise ConfigurationError("Action `{}` is not a valid action from group `{}`".format(action['action'], action['group']))

                if action['group'] not in [g['name'] for g in node['groups']]:
                    raise ConfigurationError("Action `{}` is being performed, but node not belong to group `{}`".format(
                                action['action'], action['group']))

                if 'extra' not in action:
                    action['extra'] = {}

        else:
            node['actions'] = []
        
        added_nodes.append(node)

    return added_nodes



def cluster_create(cluster_filepath: str) -> List[NodeInfo]:
    node_module = PlatformFactory.get_module_interface().get_module('node')
    tag_module = PlatformFactory.get_module_interface().get_module('tag')
    group_module = PlatformFactory.get_module_interface().get_module('group')
    template_module = PlatformFactory.get_module_interface().get_module('template')

    repository = ClusterRepositoryOperations()

    cluster_data = yaml_load(cluster_filepath)

    try:
        cluster_name = next(iter(list(cluster_data.keys())))
    except StopIteration:
        raise Exception("Invalid cluster name")

    cluster_data = cluster_data[cluster_name]
    
    valid_instance_types = template_module.list_instance_types()
    valid_groups = {group['name']: group['actions'] for group in group_module.list_groups()}

    options = __get_cluster_options__(cluster_data)
    nodes = __get_nodes_values__(cluster_data, valid_instance_types, valid_groups)

    to_create_nodes_dict = dict()
    min_nodes_count = dict()

    for node in nodes:
        if node['type'] in to_create_nodes_dict:
            to_create_nodes_dict[node['type']] += node['count']
            min_nodes_count[node['type']] += node['min_count']
        else:
            to_create_nodes_dict[node['type']] = node['count']
            min_nodes_count[node['type']] = node['min_count']

    created_nodes = node_module.start_nodes(to_create_nodes_dict)

    # Check if the mininum was reached for each node type
    for node_type, min_count in min_nodes_count.items():
        if len([node for node in created_nodes if node.instance_type == node_type and node.status == Codes.NODE_STATUS_REACHABLE]) < min_count:
            # Failed to instantiate the minumum number
            if options['on_instantiate_fail'] == 'delete':
                log.error("Minimum number of reachable `{}` nodes was not reached.".format(node_type))
                log.error("Terminating the instantiated cluster nodes: {}".format(', '.join([node.node_id for node in created_nodes])))
                node_module.stop_nodes([node.node_id for node in created_nodes])
                return []

    # Terminate non-reachable nodes
    non_reachable_node_ids = [node for node in created_nodes if node.status != Codes.NODE_STATUS_REACHABLE]
    if non_reachable_node_ids:
        log.error("Terminating non-reachable nodes: {}".format(', '.join(non_reachable_node_ids)))
        node_module.stop_nodes(non_reachable_node_ids)
        created_nodes = [node for node in created_nodes if node.node_id not in non_reachable_node_ids]

    # Distribute remaing nodes
    for instance_type, _ in to_create_nodes_dict.items():
        instantiated_nodes_of_type = [node for node in created_nodes if node.instance_type == instance_type]
        nodes_of_type = [node for node in nodes if node['type'] == instance_type]
        
        for node in nodes_of_type:
            node['instantiated_nodes'] = instantiated_nodes_of_type[:node['min_count']]
            instantiated_nodes_of_type = instantiated_nodes_of_type[node['min_count']:]
        
        for node in nodes_of_type:
            needed_len = node['count'] - len(node['instantiated_nodes'])
            if needed_len > len(instantiated_nodes_of_type):
                node['instantiated_nodes'] += instantiated_nodes_of_type
                break
            else:
                node['instantiated_nodes'] += instantiated_nodes_of_type[:needed_len]
                instantiated_nodes_of_type = instantiated_nodes_of_type[needed_len:]

    cluster_no = repository.get_new_cluster_index()
    tags = {
        'cluster_name': cluster_name,
        'cluster_index': str(cluster_no)
    }

    tag_module.node_add_tag([node.node_id for node in created_nodes], tags)


    for node in nodes:
        for group in node['groups']:
            group_name = group['name']
            group_args = group['extra']
            ret = group_module.add_group_to_node([node.node_id for node in node['instantiated_nodes']], group_name, group_args)

        node['group_valid'] = True


    for node in nodes:
        for action in node['actions']:
            action_name = action['action']
            group_name = action['group']
            group_args = action['extra']
            ret = group_module.execute_group_action([node.node_id for node in node['instantiated_nodes']], group_name, action_name, group_args)

        node['action_valid'] = True


    return created_nodes