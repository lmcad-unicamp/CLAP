import os

from typing import List, Dict, Tuple

from clap.common.factory import PlatformFactory
from clap.common.cluster_repository import NodeInfo
from clap.common.driver import Codes
from clap.common.utils import log, yaml_load
from .repository import ClusterData, ClusterRepositoryOperations
from .conf import ClusterDefaults


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

def __check_setup__(config_dict: dict, valid_groups: Dict[str, List[str]], extra_args: Dict[str, str]) -> dict:
    setups = dict()

    if 'setups' not in config_dict:
        return {}

    for setup_name, group_actions_values in config_dict['setups'].items():
        in_use_groups = []
        in_use_actions = []

        __check_if_list_is_valid(list(group_actions_values.keys()), ['actions', 'groups'], setup_name)

        # Check if 'groups' exists in the template
        if 'groups' in group_actions_values:
            for group_values in group_actions_values['groups']:
                if 'name' not in group_values:
                    raise ConfigurationError("Error in setup `{}`.groups. All groups must have a name key".format(setup_name))
                if type(group_values['name']) is not str:
                    raise ConfigurationError("Error in setup `{}`.groups. Name values must be a str".format(setup_name))
                
                extra = {}
                if 'extra' in group_values:
                    if type(group_values['extra']) is not dict:
                        raise ConfigurationError("Error in setup `{}`.groups. Extra values must be a dict".format(setup_name))
                
                    # Jinja substitutions
                    for key, value in group_values['extra'].items():
                        if type(value) is str: 
                            value = value.strip()
                            if value.startswith('{{') and value.endswith('}}'):
                                value_jinja =  value[2:-2].strip()
                                if value_jinja not in extra_args:
                                    raise ConfigurationError("Invalid substituition at extra setup `{}.groups`. Missing dynamic value for key: `{}`".format(setup_name, value_jinja))
                                extra[key] = extra_args[value_jinja]
                            else:
                                extra[key] = value
                        else:
                            extra[key] = value

                in_use_groups.append({'name': group_values['name'], 'extra': extra})
        
        # Check if all group names are valid
        __check_if_list_is_valid([g['name'] for g in in_use_groups], list(valid_groups.keys()), '{}.groups'.format(setup_name))
        
        # Check if 'actions' exists in the template
        if 'actions' in group_actions_values:
            for action_values in group_actions_values['actions']:
                if 'type' not in action_values:
                    raise ConfigurationError("Error in setup `{}`.actions. All actions must have a type key".format(setup_name))
                if type(action_values['type']) is not str or not action_values['type']:
                    raise ConfigurationError("Error in setup `{}`.actions. Action type value must be a str".format(setup_name))
                # Check if type is valid 
                __check_if_list_is_valid([action_values['type']], ['action', 'playbook', 'command'], "{}.actions".format(setup_name))
                
                # action type is an action?
                if action_values['type'] == 'action':
                    if 'group' not in action_values:
                        raise ConfigurationError("Error in actions of setup `{}`. All actions type must have a group key".format(setup_name))
                    if type(action_values['group']) is not str or not action_values['group']:
                        raise ConfigurationError("Error in setup `{}`.actions. Action group value must be a str".format(setup_name))

                    if 'name' not in action_values:
                        raise ConfigurationError("Error in actions of setup `{}`. All actions type must have a name key".format(setup_name))
                    if type(action_values['group']) is not str or not action_values['group']:
                        raise ConfigurationError("Error in setup `{}`.actions. Action name value must be a str".format(setup_name))

                    extra = {}
                    if 'extra' in action_values:
                        if type(action_values['extra']) is not dict:
                            raise ConfigurationError("Error in setup `{}`.action. Extra values must be a dict".format(setup_name))
                
                        # Jinja substitutions
                        for key, value in action_values['extra'].items():
                            if type(value) is str: 
                                value = value.strip()
                                if value.startswith('{{') and value.endswith('}}'):
                                    value_jinja =  value[2:-2].strip()
                                    if value_jinja not in extra_args:
                                        raise ConfigurationError("Invalid substituition at extra setup `{}.groups`. Missing dynamic value for key: `{}`".format(setup_name, value_jinja))
                                    extra[key] = extra_args[value_jinja]
                                else:
                                    extra[key] = value
                            else:
                                extra[key] = value
                    
                    # Check if group is valid for a group
                    __check_if_list_is_valid([action_values['group']], [g['name'] for g in in_use_groups], '{}.actions.group'.format(setup_name))
                    # Check if action name is valid
                    __check_if_list_is_valid([action_values['name']], valid_groups[action_values['group']], '{}.actions.{}.name'.format(setup_name, action_values['group']))
                    
                    # OK append!
                    action_values['extra'] = extra
                    in_use_actions.append(action_values)
                
                # Playbook type
                elif action_values['type'] == 'playbook':
                    if 'path' not in action_values:
                        raise ConfigurationError("Error in actions of setup `{}`. All playbooks type must have a path key".format(setup_name))
                    if type(action_values['path']) is not str or not action_values['path']:
                        raise ConfigurationError("Error in setup `{}`.actions. Playbook path value must be a str".format(setup_name))
                    if not os.path.exists(action_values['path']):
                        raise ConfigurationError("Error in setup `{}`.actions. Playbook path `{}` does not exists ".format(setup_name, action_values['path']))
                    if not os.path.isfile(action_values['path']):
                        raise ConfigurationError("Error in setup `{}`.actions. Playbook path `{}` is not a valid file ".format(setup_name, action_values['path']))

                    extra = {}
                    if 'extra' in action_values: 
                        if type(action_values['extra']) is not dict:
                            raise ConfigurationError("Error in setup `{}`.action. Extra values must be a dict".format(setup_name))
                                        
                        # Jinja substitutions
                        for key, value in action_values['extra'].items():
                            if type(value) is str: 
                                value = value.strip()
                                if value.startswith('{{') and value.endswith('}}'):
                                    value_jinja =  value[2:-2].strip()
                                    if value_jinja not in extra_args:
                                        raise ConfigurationError("Invalid substituition at extra setup `{}.groups`. Missing dynamic value for key: `{}`".format(setup_name, value_jinja))
                                    extra[key] = extra_args[value_jinja]
                                else:
                                    extra[key] = value
                            else:
                                extra[key] = value
                    
                    action_values['extra'] = extra
                    in_use_actions.append(action_values)

                # Command type
                elif action_values['type'] == 'command':
                    if 'command' not in action_values:
                        raise ConfigurationError("Error in actions of setup `{}`. All commands type must have a command key".format(setup_name))
                    if type(action_values['command']) is not str or not action_values['command']:
                        raise ConfigurationError("Error in setup `{}`.actions. Command must be a str".format(setup_name))

                    in_use_actions.append(action_values)

        setups[setup_name] = {'groups': in_use_groups, 'actions': in_use_actions}

    return setups

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
    node_module = PlatformFactory.get_module_interface().get_module('node')
    tag_module = PlatformFactory.get_module_interface().get_module('tag')

    # Create a new repository 
    repository = ClusterRepositoryOperations()
    cluster_data = get_cluster_data(cluster_files, cluster_name, extra_args)
    
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
            return []

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
        cluster_setup(cluster.cluster_id, extra_args)

    return cluster, node_module.list_nodes(tags={'clusters': cluster.cluster_id})

def cluster_setup(cluster_id: str, extra_args: Dict[str, str] = None, re_add_to_group: bool = False):
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
                    log.info("Adding nodes `{}` from cluster `{}` to group `{}` from setup: `{}` (extra: {})".format(
                        node_name, cluster.cluster_id, group['name'], setup_name, group['extra']))
                    final_nodes = group_module.add_group_to_node([], group['name'], group['extra'], tags, re_add_to_group=re_add_to_group)
                    if not final_nodes:
                        raise Exception("No nodes was of type `{}` added to group `{}`".format(node_name, group['name']))

        
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
                        log.info("Performing `{}` group's action `{}` (setup: `{}`) on nodes `{}` from cluster `{}` (extra: {})".format(
                            action['group'], action['name'], setup_name, node_name, cluster.cluster_id, action['extra']))
                        ret = group_module.execute_group_action([], action['group'], action['name'], action['extra'], tags)
                        # TODO False not?
                        if False:
                            raise Exception("Some `{}` nodes from cluster `{}` does not successfully executed action `{}` from group `{}`".format(
                                node_name, cluster.cluster_id, action['name'], action['group']))

                    elif action['type'] == 'playbook':
                        log.info("Running playbook `{}` on nodes `{}` (setup: `{}`) from cluster `{}` (extra:{})".format(
                            action['playbook'], node_name, setup_name, cluster.cluster_id, action['extra']))
                        ret = run_playbook_in_nodes(action['playbook'], node_module.list_nodes(tags=tags), action['extra'])
                        if not all(ret.values()):
                            raise Exception("Some `{}` nodes from cluster `{}` does not successfully executed the playbook `{}`".format(
                                node_name, cluster.cluster_id, action['playbook']))

                    elif action['type'] == 'command':
                        log.info("Executing command `{}` (setup: `{}`) in nodes `{}` of cluster `{}`".format(
                            action['command'], setup_name, node_name, cluster.cluster_id))
                        run_command(node_module.list_nodes(tags=tags), action['command'])

                    else:
                        raise ValueError("Invalid action type `{}`".format(action['type']))

        # Setup OK for nodes XXXX
        pass

def add_node_to_cluster(cluster_id: str, node_type: Dict[str, int]):
    pass

def add_existing_node_to_cluster(cluster_id: str, node_types: Dict[str, List[str]]):
    pass



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

        cluster_node_dict[cluster.cluster_id] = {'cluster': cluster.cluster_id, 'nodes': nodes}

    return cluster_node_dict




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

