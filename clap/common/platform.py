import setuptools
import pkgutil
import inspect
import importlib.util
import os
import sys
import time
from typing import List, Dict, Tuple, Union, Any
from paramiko import SSHClient

import clap.drivers
import clap.modules

from clap.common.module import AbstractParser
from clap.common.config import Defaults
from clap.common.driver import AbstractInstanceInterface
from clap.common.cluster_repository import RepositoryOperations, NodeInfo
from clap.common.utils import path_extend, log, yaml_load
from clap.common.exceptions import ConfigurationError


class ModuleInterface:
    """ Interface to get clap modules from the modules repositories
    """
    __modules_map__ = dict()

    @staticmethod
    # Check module dependencies, if any...
    def __check_dependencies__():
        pass

    @staticmethod
    def __find_modules__(module_paths: List[str] = None, force: bool = False):
        """ Find CLAP modules located at CLAP search paths

        :param module_paths: List of pathsto search CLAP modules
        :type module_paths: List[str]
        :param force: Search even if it is already searched once
        :type force: bool
        """
        if ModuleInterface.__modules_map__ and not force:
            return

        # No additional module paths? Use CLAP clap.modules package directory. Else append clap.modules package directory
        if not module_paths:
            module_paths = [os.path.dirname(clap.modules.__file__)]
        else:
            module_paths.append(os.path.dirname(clap.modules.__file__))

        log.debug("Searching modules in paths: {}".format(", ".join(module_paths)))

        # Iterate through module packages...
        for importer, package_name, _ in pkgutil.iter_modules(module_paths):
            # Skip pycache directories
            if 'pycache' in package_name or '.' in package_name:
                continue
            # Try to import the CLAP module package module...
            try:
                mod =  importer.find_module(package_name).load_module(package_name) 
                mod_values = {
                    'name': mod.__module_name__ if '__module_name__' in mod.__dict__ else package_name,
                    'description': mod.__module_description__ if '__module_description__' in mod.__dict__ else '',
                    'dependencies': mod.__module_dependencies__ if '__module_dependencies__' in mod.__dict__ else [],
                    'module': mod,
                    'loaded time': time.time()
                }

                # Append to module dict
                ModuleInterface.__modules_map__[mod_values['name']] = mod_values
            except Exception as e:
                log.error("At module: `{}`: {}".format(package_name, e))
                log.error("Discarding module `{}`".format(package_name))

        log.debug("Found {} modules: {}".format( len(ModuleInterface.__modules_map__),
            ', '.join(list(ModuleInterface.__modules_map__.keys())) ) )

        # Check module dependencies
        ModuleInterface.__check_dependencies__()

    def __init__(self, module_paths: List[str] = None, force=False):
        self.__find_modules__(module_paths=module_paths, force=force)

    def get_module(self, module_name: str) -> list:
        """ Get the module package

        :param module_name: Name of the clap's module (as python module)
        :type module_name: str
        :return: The module
        :rtype: Module
        """
        return self.__modules_map__[module_name]['module']

    def get_modules(self) -> Dict[str, Any]:
        """ Get the module package

        :return: Dictionaty with modules information. Theinformation are:
          - name: Name of the module
          - description: Module's description
          - dependencies: Module's depencencies
          - module: The loaded module (as python module)
          - loaded_time: Date when the module was loaded
        :rtype: Dict[str, Any]
        """
        return self.__modules_map__

    def get_module_names(self) -> List[str]:
        """ Get the name of all the modules in the clap modules repository

        :return: List containing the all module names
        :rtype: List[str]
        """

        return list(self.__modules_map__.keys())


class GroupInterface:
    """ This interface collects and maintains information about groups in the CLAP system
    """
    __groups_actions_map__ = dict()

    @staticmethod
    def __find_groups(force: bool = False):
        """ Find CLAP groups at group's path

        :param force: Force to research groups, even if it is already searched once
        :type force: bool
        """
        if GroupInterface.__groups_actions_map__ and not force:
            return

        # Search for all files in the actions directory and parse then!
        for group_file in os.listdir(Defaults.actions_path):
            if not group_file.endswith('.yml'):
                continue
            try:
                # Get the group name (name of file without yml)
                group_name = group_file[:-4]
                # Load the YAML file as a dict
                group_values = yaml_load(path_extend(Defaults.actions_path, group_file))
                __new_group = dict()

                # ************** HOST VALIDATION *****************
                # Hosts does not exists?
                if 'hosts' not in group_values:
                    __new_group['hosts'] = []
                else:
                    # Check if it is a list and if all elements are str
                    if type(group_values['hosts']) is not list:
                        raise ConfigurationError("Host values must be a list")
                    invalid_hosts = [host for host in group_values['hosts'] if type(host) is not str or not host]
                    if invalid_hosts:
                        raise ConfigurationError("Hosts `{}` are invalid".format(', '.join(sorted(invalid_hosts))))
                    # Hosts validation -- ok
                    __new_group['hosts'] = list(group_values['hosts'])

                # ************** ACTIONS VALIDATION *****************
                if 'actions' not in group_values:
                    raise ConfigurationError("All groups must have `actions` values") 
                actions = {}

                # Iterate through actions...
                for action_name, action in group_values['actions'].items():
                    action_values = {}

                    # Action's playbook variable is required!
                    if 'playbook' not in action:
                        raise ConfigurationError("All actions must specify a playbook")

                    action_values['playbook'] = action['playbook']

                    # Check if 'description' variable exists in the action or set it to default (empty string)
                    action_values['description'] = '' if 'description' not in action else action['description']
                    
                    # Check if 'vars' variable exists in action, else set to an empty list
                    action_vars = []
                    if 'vars' in action:
                        # Iterate through vars variable
                        for var in action['vars']:
                            __vars = {}
                            # Var name is required!
                            if 'name' not in var:
                                raise ConfigurationError("All vars must have a name")
                            __vars['name'] = var['name']

                            # Check if description exists in the variable or set it to default (empty string)
                            __vars['description'] = '' if 'description' not in var else var['description']
                            # Check if the variable is optional or set it to default (false --> var is required for this action)
                            __vars['optional'] = False if 'optional' not in var else var['optional']
                            # Variable successfully validated!
                            action_vars.append(__vars)

                    action_values['vars'] = action_vars
                    # Group's actions successfully validated!
                    actions[action_name] = action_values

                __new_group['actions'] = actions

                # ************** DEPENDENCIES VALIDATION *****************
                # Check if group has any dependencies. If not, set to default: empty list
                if 'dependencies' not in group_values:
                    __new_group['dependencies'] = []
                else:
                    # Check if dependencies is a list of str
                    if type(group_values['dependencies']) is not list:
                        raise ConfigurationError("Dependencies must be a list")
                    invalid_dependencies = [dep for dep in group_values['dependencies'] if type(dep) is not str or not dep]
                    if invalid_dependencies:
                        raise ConfigurationError("Dependencies `{}` are invalid".format(', '.join(sorted(invalid_dependencies))))
                    # Dependencies validation -- ok
                    __new_group['dependencies'] = list(group_values['dependencies'])

                # ****************** OK *******************
                # Group successfully validated!
                GroupInterface.__groups_actions_map__[group_name] = __new_group
                
            except Exception as e:
                log.error("At group `{}`: {}".format(group_file, e))
                log.error("Discarding group `{}`".format(group_file))

    def __init__(self):
        self.__find_groups()

    def get_group(self, group_name: str) -> Dict[str, Any]:
        """ Get group based on the group name

        :param group_name: Name of the group to get
        :type group_name: str
        :return: Dictionary with group's information. The dictionary contains the following keys:
            * name: Group's name
            * actions: List of group's actions
            * hosts: List of group's hosts
            * dependecies: List of group's dependencies
        :rtype: Dict[str, Any]
        """
        if group_name not in GroupInterface.__groups_actions_map__:
            raise Exception("Invalid group: `{}`".format(group_name))
        group = GroupInterface.__groups_actions_map__[group_name]
        return dict(name=group_name, actions=group['actions'], hosts=group['hosts'], dependencies=group['dependencies'])

    def get_group_names(self) -> List[str]:
        """ Get name of all groups in CLAP's system 

        :return: List of group's names
        :rtype: List[str]
        """
        return list(GroupInterface.__groups_actions_map__.keys())


class MultiInstanceAPI:
    """ API used to manage and perform operations in nodes from different driver implementations,
    and cloud providers in a transparently manner.
    """
    __interfaces_map__ = dict()

    @staticmethod
    def __find_ifaces():
        if MultiInstanceAPI.__interfaces_map__:
            return

        for pkg_name in setuptools.find_packages(os.path.dirname(clap.drivers.__file__)):
            if '.' in pkg_name:
                continue
            try:
                mod = importlib.import_module('clap.drivers.{}'.format(pkg_name))
                drivers = [ obj for name, obj in inspect.getmembers(mod,
                            predicate=lambda mod: inspect.isclass(mod) and issubclass(mod, AbstractInstanceInterface))
                            if name != 'AbstractInstanceInterface' ]

                MultiInstanceAPI.__interfaces_map__.update({obj.__interface_id__: obj for obj in drivers})
            except Exception as e:
                log.error("At driver `{}`: {}".format(pkg_name, e))
                log.error("Discarding driver `{}`".format(pkg_name))
        
        log.debug("Found {} interfaces: {}".format( len(MultiInstanceAPI.__interfaces_map__),
            ', '.join(list(MultiInstanceAPI.__interfaces_map__.keys())) ) )

    def __init__(self, platform_db: str, repository_type: str, default_driver: str):
        """ Create a MultiInstance API used to manage several clusters and nodes in a transparent manner

        :param platform_db: Path of the platform repository to use. The repository is used to store nodes information
        :type platform_db: str
        :param repository_type: Type of the repository storage
        :type repository_type: str
        :param default_driver: Default driver used to manage nodes
        :type default_driver: str
        """
        self.__repository_operations = RepositoryOperations(platform_db, repository_type)
        self.__repository_operations.create_platform_db(exists='pass')
        self.__default_driver = default_driver
        self.__find_ifaces()

    def _get_instance_iface(self, driver_id: str = None) -> AbstractInstanceInterface:
        if not driver_id:
            driver_id = self.__default_driver

        driver =  self.__interfaces_map__[driver_id](self.__repository_operations)
        log.debug("Using driver: `{}`".format(driver.__interface_id__))
        return driver

    @staticmethod
    def get_instance_templates() -> Dict[str, Any]:
        """ Get the instance templates defined in the instance configuration files.

        :return:    Dictionary with instance templates. The keys are the instance name and the value are the values for the instance. 
                    The dictionary have the same values for the instance configuration files
        :rtype: Dict[str, Any]
        """
        return yaml_load(Defaults.instances_conf)

    # --------------------------------------------------------------------------------
    # ########################### Operations with driver ############################
    # The following operations directly uses a driver interface to interact with nodes
    # --------------------------------------------------------------------------------

    def start_nodes(self, instances_num: Dict[str, int]) -> List[NodeInfo]:
        """ Start instances based on the configuration values

        :param instances_num: Dictionary containing the instance name as key and number of instances as value. The instance name must match the instance name at instances configuration file
        :type instances_num: Dict[str, int]
        :return: A list of created nodes 
        :rtype: List[NodeInfo]
        """
        print("Starting instances: {}...".format(instances_num))
        return self._get_instance_iface(self.__default_driver).start_nodes(instances_num)

    def stop_nodes(self, node_ids: List[str], force: bool = True) -> List[str]:
        """ Stop started nodes based on their node ids

        :param node_ids: List of node ids to stop
        :type node_ids: List[str]
        :return: A list of stopped nodes 
        :rtype: List[str]
        """      
        nodes = self.get_nodes(node_ids)
        stopped_nodes = []
        for cluster in self.__repository_operations.get_clusters(list(set(node.cluster_id for node in nodes))):
            node_ids = [node.node_id for node in nodes if node.cluster_id == cluster.cluster_id]
            print("Stopping nodes: `{}`...".format(', '.join(sorted(node_ids))))
            stopped_nodes += self._get_instance_iface(cluster.driver_id).stop_nodes(node_ids, force)
        return stopped_nodes

    def pause_nodes(self, node_ids: List[str]) -> List[str]:
        """ Pause started nodes based on their node ids

        :param node_ids: List of node ids to pause
        :type node_ids: List[str]
        :return: A list of paused nodes 
        :rtype: List[str]
        """
        nodes = self.get_nodes(node_ids)
        paused_nodes = []
        for cluster in self.__repository_operations.get_clusters(list(set(node.cluster_id for node in nodes))):
            node_ids = [node.node_id for node in nodes if node.cluster_id == cluster.cluster_id]
            print("Pausing nodes: `{}`...".format(', '.join(sorted(node_ids))))
            paused_nodes += self._get_instance_iface(cluster.driver_id).pause_nodes(node_ids)
        return paused_nodes

    def resume_nodes(self, node_ids: List[str]) -> List[str]:
        """ Resume paused nodes based on their node ids

        :param node_ids: List of node ids to resume
        :type node_ids: List[str]
        :return: A list of resumed nodes 
        :rtype: List[str]
        """
        nodes = self.get_nodes(node_ids)
        resumed_nodes = []
        for cluster in self.__repository_operations.get_clusters(list(set(node.cluster_id for node in nodes))):
            node_ids = [node.node_id for node in nodes if node.cluster_id == cluster.cluster_id]
            print("Resuming nodes: `{}`...".format(', '.join(sorted(node_ids))))
            resumed_nodes += self._get_instance_iface(cluster.driver_id).resume_nodes(node_ids)
        return resumed_nodes

    def check_nodes_alive(self, node_ids: List[str]) -> Dict[str, bool]:
        """ Check if nodes are alive, based on their node ids. The nodes are alive if a successfully SSH connection is performed

        :param node_ids: List of node ids to check for aliveness.
        :type node_ids: List[str]
        :return: A dictionary telling which nodes are alive. The dictionary keys correspond to the node id and the value is a boolean that is true if node is alive or false otherwise. 
        :rtype: Dict[str, bool]
        """
        nodes = self.get_nodes(node_ids)
        checked_nodes = dict()
        for cluster in self.__repository_operations.get_clusters(list(set(node.cluster_id for node in nodes))):
            node_ids = [node.node_id for node in nodes if node.cluster_id == cluster.cluster_id]
            print("Cheking if nodes `{}` are alive...".format(', '.join(sorted(node_ids))))
            checked_nodes.update(self._get_instance_iface(cluster.driver_id).check_nodes_alive(node_ids))
        return checked_nodes

    def execute_playbook_in_nodes(self, playbook_path: str, hosts: Union[List[str], Dict[str, List[str]]],
                                  extra_args: Dict[str, str] = None) -> Dict[str, bool]:
        """ Execute an Ansible Playbook at nodes based on their node ids.

        :param playbook_path: Path of the Ansible playbook to execute.
        :type playbook_path: str
        :param hosts: Nodes which playbooks will be executed. The variables can be, one of them:
          - A List of node ids, telling which nodes the playbook will be executed
          - A Dictionary telling the ansible host name (as key) and a list of node ids as value. The ansible inventory will be generated putting each node list inside the respective host.
        :type hosts: Union[List[str], Dict[str, List[str]]]
        :param extra_args: Key-valued dictionary containing the extra variables to be passed to the playbook. Both key and value are strings
        :type extra_args: Dict[str, str]
        :return: A dictionary telling which nodes have sucessfully executed the playbook. The dictionary keys correspond to the node id and the value is a boolean that is true if node successfully executed the playbook or false otherwise. 
        :rtype: Dict[str, bool]
        """
        # Check if playbook file exists
        if not os.path.isfile(playbook_path):
            raise Exception("Invalid playbook at `{}`".format(playbook_path))
        # Check if any host is set
        if not hosts:
            raise Exception("No nodes to execute playbook `{}`".format(playbook_path))
        # If hosts var is  list. Create a inventory file with all hosts to a __default__ group
        if isinstance(hosts, list):
            hosts = {'default': hosts}
        # Get all nodes ids, merging node ids from all host lists
        nodes = [node_id for group_name, node_list in hosts.items() for node_id in node_list]
        if not nodes:
            raise Exception("No nodes to execute playbook `{}`".format(playbook_path))

        # Get nodes detailed information
        nodes = self.get_nodes(nodes)
        executed_nodes = {}
        # Any extra args?
        extra_args = extra_args if extra_args else {}

        # Filter the drivers of all nodes and iterate over driver 
        for driver_id in set([node.driver_id for node in nodes]):
            new_hosts = dict()

            # Iterate over the hosts dict and filter only nodes with the same driver_id
            for group, node_list in hosts.items():
                # Filter the host's node list only with nodes with the same driver_id
                node_ids = [node.node_id for node in self.__repository_operations.get_nodes(node_list)
                            if node.driver_id == driver_id]
                if len(node_ids) == 0:
                    log.error("Discarding group `{}` because there is no nodes".format(group))
                else:
                    new_hosts[group] = node_ids

            # Check if there is at least one node to execute at any host(redundant)
            #if all(host_list for host_list in new_hosts.values()):
            #    raise Exception("No nodes to execute")

            # Execute the playbook with the driver at hosts
            executeds = self._get_instance_iface(driver_id).execute_playbook_in_nodes(playbook_path, new_hosts, extra_args)
            
            # Map each host to a it's execution status (true, if sucessfully executed and false otherwise)
            for node_id, status in executeds.items():
                if node_id in executed_nodes:
                    executed_nodes[node_id] = executed_nodes[node_id] and status
                else:
                    executed_nodes[node_id] = status

        return executed_nodes

    def get_connection_to_nodes(self, node_ids: List[str], *args, **kwargs) -> Dict[str, SSHClient]:
        """ Get a SSH client to nodes.

        :param node_ids: List of node ids to get the clients.
        :type node_ids: List[str]
        :return: A dictionary with the SSH clients. The key is the node id and each value is the SSH client (from Paramiko library)
        :rtype: Dict[str, Paramiko.SSHClient]
        """
        nodes = self.get_nodes(node_ids)
        connections = dict()
        for cluster in self.__repository_operations.get_clusters(list({node.cluster_id for node in nodes})):
            connections.update(self._get_instance_iface(cluster.driver_id).get_connection_to_nodes([
                node.node_id for node in nodes if node.cluster_id == cluster.cluster_id], *args, **kwargs))
        return connections

    # --------------------------------------------------------------------------------
    # ########################### Operations with repository #########################
    # The following operations directly uses the reporitory
    # --------------------------------------------------------------------------------
    def get_nodes(self, node_ids: List[str]) -> List[NodeInfo]:
        """ Get the information of nodes from the node repository

        :param node_ids: List of node ids to get the node information.
        :type node_ids: List[str]
        :return: A list with nodes information 
        :rtype: List[NodeInfo]
        """
        if not node_ids:
            raise Exception("No nodes informed")

        node_set = set(node_ids)
        nodes = self.__repository_operations.get_nodes(list(node_set))
        if len(nodes) != len(node_set):
            raise Exception("Some nodes are invalid: `{}`".format(', '.join(sorted(
                node_set.difference([node.node_id for node in nodes])))))

        return nodes
    
    def get_all_nodes(self) -> List[NodeInfo]:
        """ Get all nodes information from the repository

        :return: A list with nodes information 
        :rtype: List[NodeInfo]
        """
        return self.__repository_operations.get_all_nodes()

    def get_nodes_with_tags(self, tags: Dict[str, str]) -> List[NodeInfo]:
        """ Get the information of nodes from the node repository that match the tags informed

        :param tags: Key-valued dictionary with informing tags to be searched in nodes. A matched node is a node which contains the tags and the tag value match the informed tags value. The node must match all tags passed.
        :type tags: Dict[str, str]
        :return: A list with nodes information 
        :rtype: List[NodeInfo]
        """
        tagged_nodes = []
        for node in self.__repository_operations.get_all_nodes():
            add_node = True
            if not tags:
                continue
            for tag, val in tags.items():
                if not node.tags or tag not in node.tags or val not in node.tags[tag]:
                    add_node = False
                    break
            if add_node:
                tagged_nodes.append(node)

        return tagged_nodes

    # --------------------------------------------------------------------------------
    # ########################### Operations with tags ###############################
    # The following operations add/remove tags from nodes
    # --------------------------------------------------------------------------------

    def add_tags_to_nodes(self, node_ids: List[str], tags: Dict[str, str]) -> List[str]:
        """ Add tags to nodes

        :param node_ids: List of node ids to add the tags.
        :type node_ids: List[str]
        :param tags: Key-valued dictionary with informing the tags key and value. Each tag may contain a set of value, so if a value a tag with the same key already exists in node, the value will be added to the tag set.
        :type tags: Dict[str, str]
        :return: A list of nodes which the tags were added 
        :rtype: List[str]
        """
        added_nodes = []
        for node in self.get_nodes(node_ids):
            for tag, val in tags.items():
                if tag in node.tags:
                    if val not in node.tags[tag]:
                        node.tags[tag].append(val)
                else:
                    node.tags[tag] = [val]

            added_nodes.append(node)

        for node in added_nodes:
            self.__repository_operations.update_node(node)

        return [node.node_id for node in added_nodes]

    def remove_tags_from_nodes(self, node_ids: List[str], tags: Dict[str, str]) -> List[str]:
        """ Remove a tag value from a node tag set 

        :param node_ids: List of node ids to remove the tags.
        :type node_ids: List[str]
        :param tags: Key-valued dictionary with informing the tags key and value. The value will be removed from each tag set. If the tag set contains no value, the node tag will be removed.
        :type tags: Dict[str, str]
        :return: A list of nodes which the tags were removed 
        :rtype: List[str]
        """
        removed_nodes = []
        for node in self.get_nodes(node_ids):
            for tag, value in tags.items():
                if tag in node.tags and value in node.tags[tag]:
                    tag_vals = node.tags[tag]
                    tag_vals.remove(value)
                    if not tag_vals:
                        node.tags.pop(tag)
                    else:
                        node.tags[tag] = tag_vals
                    removed_nodes.append(node)

        for node in removed_nodes:
             self.__repository_operations.update_node(node)
        
        return [node.node_id for node in removed_nodes]

    def remove_tags_from_nodes_by_key(self, node_ids: List[str], tags: List[str]) -> List[str]:
        """ Remove all values from a tag set from nodes

        :param node_ids: List of node ids to remove the tags.
        :type node_ids: List[str]
        :param tags: List of tags to remove from nodes (all tag values will be removed from the tag set of the node)
        :type tags: List[str]
        :return: A list of nodes which the tags were removed 
        :rtype: List[str]
        """
        removed_nodes = []
        for node in self.get_nodes(node_ids):
            for tag in tags:
                if tag in node.tags:
                    node.tags.pop(tag)
                    self.__repository_operations.update_node(node)
                    removed_nodes.append(node)

        for node in removed_nodes:
             self.__repository_operations.update_node(node)
        
        return [node.node_id for node in removed_nodes]

    # --------------------------------------------------------------------------------
    # ########################### Operations with groups ###############################
    # The following perform group operations 
    # --------------------------------------------------------------------------------

    def get_groups(self) -> List[Dict[str, Any]]:
        """ Get all CLAP groups

        :return: A List of dictionary with groups information. Each dictionary's element of the list contains:
          - name: The group's name (string)
          - actions: The list of group's actions (list of string)
          - hosts: The list group's host (list of string)
        :rtype: List[Dict[str, Any]]
        """
        groups = []
        # Iterate over all groups and get all dicts
        for group_name in GroupInterface().get_group_names():
            group_dict = GroupInterface().get_group(group_name)
            groups.append(group_dict)
        return groups

    def __execute_group_action__(self, hosts: Dict[str, List[str]], action_dict: str, action_name: str, extra_args: Dict[str, str]):
        log.info("Executing action `{}` in hosts: {}".format(action_name, hosts))
        full_playbook_path = path_extend(Defaults.groups_path, action_dict['playbook'])
        for var in action_dict['vars']:
            if var['name'] not in extra_args:
                if var['optional']:
                    continue
                else:
                    raise Exception("Action `{}` requires that variable `{}` is informed".format(action_name, var['name']))

        executeds = self.execute_playbook_in_nodes(playbook_path=full_playbook_path, hosts=hosts, extra_args=extra_args)
        if not all(executeds.values()):
            raise Exception("Nodes `{}` does not successfully executed playbook `{}`".format(
                ', '.join(sorted([node for node, status in executeds.items() if not status])), full_playbook_path))
        return list(executeds.keys())

    def __get_nodes_in_group__(self, group: str, node_ids: List[str] = None) -> List[str]:
        # Get full node information from nodes that is in the group
        nodes = self.__repository_operations.get_nodes(node_ids) if node_ids else self.__repository_operations.get_all_nodes()
        members = []
        for node in nodes:
            if '/' in group:
                if group in node.groups:
                    members.append(node.node_id)
            elif group in {group_name.split('/')[0] for group_name in list(node.groups.keys())}:
                members.append(node.node_id)

        return members

    def __check_nodes_in_group__(self, group_name: str, node_ids: List[str] = None):
        # Split group_name variable
        split_vals = group_name.split('/')
        # If not in format: group_name or group_name/hostname --> Error
        if len(split_vals) > 2:
            raise Exception("Invalid group and hosts `{}`".format(group_name))

        # Node IDS are already passed, get list of nodes in the group
        if node_ids:
            node_with_group = self.__get_nodes_in_group__(group_name, node_ids)
            # Check if all nodes passed belong to the group
            if len(node_ids) != len(node_with_group):
                raise Exception("Nodes `{}` are not members of group `{}`".format(
                    ', '.join(sorted(set(node_ids).difference(set(node_with_group)))), group_name))
        # Get all nodes belonging to the group and set the node ids
        else:
            node_ids = self.__get_nodes_in_group__(group_name)

        # If no nodes belong to group, stop.
        if not node_ids:
            raise Exception("No nodes in group `{}`".format(group_name))

        if len(split_vals) > 1:
            # Check nodes of group with host (not only with group name)
            node_with_group = [node.node_id for node in self.__repository_operations.get_nodes(node_ids)
                               if group_name in list(node.groups.keys())]
            # If nodes does not belong to group with same node, stop.
            if len(node_ids) != len(node_with_group):
                raise Exception("Nodes `{}` are not members of group `{}`".format(
                    ', '.join(sorted(set(node_ids).difference(set(node_with_group)))), group_name))
        return node_ids

    def add_nodes_to_group(self, node_ids: List[str], group_name: str, group_args: Dict[str, str] = None, 
            __processing_dependencies__: List[str] = None) -> List[str]:
        """ Add nodes to a informed group

        :param node_ids: List of node ids to add the the group.
        :type node_ids: List[str]
        :param group_name: Name of the group which the nodes will be added. If the group has a setup action, the setup action will be executed.
        :type group_name: str
        :param group_args: Key-valued dictionary with the extra arguments to be passed to the setup's action.
        :type group_args: Dict[str, str]
        :param __processing_dependencies__: Internal parameter used to check ciclycal dependencies
        :type __processing_dependencies__: List[str]
        :return: A list of nodes that was successfully added to group. A node is sucessfully added to the group if the setup action was sucessfully performed (if any)
        :rtype: List[str] 
        """
        # Split group_name variable
        split_vals = group_name.split('/')
        # If not in format: group_name or group_name/hostname --> Error
        if len(split_vals) > 2:
            raise ValueError("Invalid group and hosts `{}`".format(group_name))

        group_name = split_vals[0]
  
          # Set dependency chain list if None
        __processing_dependencies__ = [] if not __processing_dependencies__ else __processing_dependencies__

        # Is this one already in processing? If true --> Cyclical dependency chain!
        if group_name in __processing_dependencies__:
            raise Exception("Cyclical dependencies when processing group dependencies! Dependency chain: `{}`".format(', '.join(__processing_dependencies__)))

        # Add this one to dependency chain
        __processing_dependencies__.append(group_name)

        # Get dependencies for this group and process each one
        for dependency in GroupInterface().get_group(group_name)['dependencies']:
            print("Processing group `{}` dependency: `{}`...".format(group_name, dependency))
            self.add_nodes_to_group( node_ids=node_ids, group_name=dependency, group_args=group_args, 
                                __processing_dependencies__=__processing_dependencies__)
            log.info("Dependency `{}` sucessfully processed!".format(dependency))

        # Remove this one from dependency chain
        __processing_dependencies__.pop()
        
        # And process!
        return self.__add_nodes_to_group({split_vals[0]: node_ids if len(split_vals) == 1 else {split_vals[1]: node_ids}}, group_args)

    def __add_nodes_to_group(self, group_hosts_map: Dict[str, Union[List[str], Dict[str, List[str]]]], group_args: Dict = None):
        node_ids = set()

        for group_name, hosts in group_hosts_map.items():
            group_dict = GroupInterface().get_group(group_name)
            group_actions, group_hosts = group_dict['actions'], group_dict['hosts'] 

            if isinstance(hosts, dict):
                host_names = list(hosts.keys())
                invalid_hosts = [i for i in host_names if i not in group_hosts]
                if invalid_hosts:
                    raise Exception("Invalid hosts `{}` for group `{}`".format(', '.join(sorted(invalid_hosts)), group_name))
            elif isinstance(hosts, list):
                hosts = {h: hosts for h in group_hosts} if group_hosts else {'__default__': hosts}
            else:
                raise Exception("Invalid type for hosts (must be a list or a dict)")

            group_args = group_args if group_args else {}
            
            if 'setup' in group_actions:
                self.__execute_group_action__(hosts, group_actions['setup'], 'setup', group_args)

            if 'elasticluster' in group_args:
                group_args.pop('elasticluster')

            for host_name, host_list in hosts.items():
                for node_id in host_list:
                    node = self.get_nodes([node_id])[0]
                    value = {'extra': group_args, 'time': time.time()}
                    if host_name == '__default__':
                        node.groups[group_name] = value
                    else:
                        node.groups["{}/{}".format(group_name, host_name)] = value

                    self.__repository_operations.update_node(node)
                    node_ids.add(node.node_id)

        return list(node_ids)

    def execute_group_action(self, group_name: str, action: str, group_args: Dict = None, node_ids: List[str] = None):
        """ Perform a group action in all nodes belonging to a group

        :param group_name: Name of the group which the action will be performed
        :type group_name: str
        :param action: Name of the group's action to be perfomed
        :type action: str 
        :param group_args: Key-valued dictionary with the extra arguments to be passed to the action.
        :type group_args: Dict[str, str]
        :param node_ids: List of node ids which the action will be performed. If None is informed, the action will be performed to all nodes belonging to the group informed. 
        :type node_ids: List[str]
        :return: A list of nodes that successfully performed the action.
        :rtype: List[str] 
        """
        # Check nodes of the group
        node_ids = self.__check_nodes_in_group__(group_name, node_ids)
        return self.__execute_group_action(node_ids, group_name, action, group_args)

    def __execute_group_action(self, node_ids: List[str], group_name: str, action: str, group_args: Dict = None):
        split_vals = group_name.split('/')
        group_name = split_vals[0]

        group_dict = GroupInterface().get_group(group_name)
        group_actions, group_hosts = group_dict['actions'], group_dict['hosts'] 
        hosts_map = dict()
        extra_args = {}

        if action not in group_actions:
            raise Exception("Invalid action `{}` for group `{}`".format(action, group_name))

        if not group_hosts:
            if len(split_vals) > 1:
                raise Exception("Invalid host `{}` (the group does not have any hosts to be specified)".format(split_vals[1]))
            hosts_map['__default__'] = node_ids
        else:
            if len(split_vals) > 1:
                if split_vals[1] not in group_hosts:
                    raise Exception("Invalid host `{}` for group `{}`".format(split_vals[1], group_name))
                else:
                    group_hosts = [split_vals[1]]

            for host_name in group_hosts:
                for node in self.__repository_operations.get_nodes(node_ids):
                    final_host_name = "{}/{}".format(group_name, host_name)

                    if final_host_name not in node.groups:
                        continue
                    if host_name not in hosts_map:
                        hosts_map[host_name] = [node.node_id]
                    else:
                        hosts_map[host_name].append(node.node_id)

        if not hosts_map:
            raise Exception("No nodes to perform action `{}` from group `{}`".format(action, group_name))

        for _, host_list in hosts_map.items():
            nodes = self.get_nodes(host_list)
            for node in nodes:
                if group_name in node.groups:
                    extra_args.update(node.groups[group_name]['extra'])

        extra_args.update(group_args)
        #log.info("Executing action `{}` of group `{}` in nodes `{}`".format(action, group_name, ', '.join(sorted(node_ids))))
        return self.__execute_group_action__(hosts_map, group_actions[action], action, extra_args)

    def remove_nodes_from_group(self, group_name: str, node_ids: List[str] = None, remove_action: str = None,
                                group_args: Dict = None):
        # Check nodes of the group
        split_vals = group_name.split('/')
        node_ids = self.__check_nodes_in_group__(group_name, node_ids)

        # Is there any remove action?
        if remove_action:
            # Perform it!
            removeds = self.__execute_group_action(node_ids, group_name, remove_action, group_args)
            if len(removeds) != len(node_ids):
                raise Exception("Nodes `{}` have failed to execute action `{}`".format(
                    ', '.join(set(node_ids).difference(set(removeds))), remove_action))

        # Iterate over all nodes in the group
        for node in self.get_nodes(node_ids):
            # If group name is of format: group/host --> Remove group/host from list
            if len(split_vals) > 1:
                node.groups.pop(group_name)
            # Else, if is the format: groupname --> Must remove all hosts (if any) from nodes
            else:
                # Iterate over all groups of the node
                for gname in list(node.groups.keys()):
                    # If the got group is same as group_name or startswith 'group_name/'
                    if gname == group_name or gname.startswith("{}/".format(group_name)):
                        node.groups.pop(gname)
            # Update repository
            self.__repository_operations.update_node(node)

        return node_ids
