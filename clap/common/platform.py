import setuptools
import inspect
import importlib.util
import os
import sys
from typing import List, Dict, Tuple, Union, Any
from paramiko import SSHClient

import clap.drivers
import clap.modules

from clap.common.module import AbstractParser
from clap.common.config import Defaults
from clap.common.driver import AbstractInstanceInterface
from clap.common.cluster_repository import RepositoryOperations, NodeInfo
from clap.common.utils import path_extend, log, yaml_load


class ModuleInterface:
    """ Interface to get clap modules from the modules repository
    """
    __modules_map__ = dict()

    @staticmethod
    def __find_modules():
        if ModuleInterface.__modules_map__:
            return

        module_paths = [os.path.dirname(clap.modules.__file__)]#, Defaults.modules_path]
        log.debug("Searching modules in paths: {}".format(", ".join(module_paths)))

        for path in module_paths:
            sys.path.append(path)
            
            for pkg_name in setuptools.find_packages(path):
                try:
                    mod =  __import__(pkg_name)
                    ModuleInterface.__modules_map__[pkg_name] = mod
                except Exception as e:
                    log.error(e)

        log.debug("Found {} modules. {}".format( len(ModuleInterface.__modules_map__),
            ', '.join(list(ModuleInterface.__modules_map__.keys())) ) )

    def __init__(self):
        self.__find_modules()

    def get_module(self, module_name: str):
        """ Get the module package

        :param module_name: Name of the clap module
        :type module_name: str
        :return: The module
        :rtype: Module
        """
        return self.__modules_map__[module_name]

    def get_modules(self):
        """ Get the module package

        :return: List of modules
        :rtype: List[module]
        """
        return self.__modules_map__

    def get_module_names(self) -> List[str]:
        """ Get the name of all the modules in the clap modules repository

        :return: List containing the module names
        :rtype: List[str]
        """

        return list(self.__modules_map__.keys())



class GroupInterface:
    __groups_actions_map__ = dict()

    GROUP_SCHEMA = None

    @staticmethod
    def __find_groups():
        if GroupInterface.__groups_actions_map__:
            return

        groups_path = path_extend(Defaults.groups_path, 'groups')
        for group_file in os.listdir(groups_path):
            try:
                if not group_file.endswith('.py') or group_file.startswith('__'):
                    continue

                spec = importlib.util.spec_from_file_location(
                    groups_path, path_extend(groups_path, group_file))
                cls = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(cls)
                GroupInterface.__groups_actions_map__[group_file.split('.')[0]] = cls
            except Exception as e:
                log.error(e)

    def __init__(self):
        self.__find_groups()

    def get_group(self, group_name: str) -> Tuple[List[str], List[str], str]:
        if group_name not in GroupInterface.__groups_actions_map__:
            raise Exception("Invalid group: `{}`".format(group_name))
        group = GroupInterface.__groups_actions_map__[group_name]
        actions = getattr(group, 'actions', list())
        hosts = getattr(group, 'hosts', list())
        playbook = getattr(group, 'playbook', str)
        return actions, hosts, playbook

    def get_group_names(self) -> List[str]:
        return list(GroupInterface.__groups_actions_map__.keys())


class MultiInstanceAPI:
    """ API used to manage and perform operations in cluster and nodes from different driver implementations,
    and cloud providers in a transparently manner.
    """
    __interfaces_map__ = dict()

    @staticmethod
    def __find_ifaces():
        if MultiInstanceAPI.__interfaces_map__:
            return

        for pkg_name in setuptools.find_packages(os.path.dirname(clap.drivers.__file__)):
            try:
                mod = importlib.import_module('clap.drivers.{}'.format(pkg_name))
                drivers = [ obj for name, obj in inspect.getmembers(mod,
                            predicate=lambda mod: inspect.isclass(mod) and issubclass(mod, AbstractInstanceInterface))
                            if name != 'AbstractInstanceInterface' ]

                MultiInstanceAPI.__interfaces_map__.update({obj.__interface_id__: obj for obj in drivers})
            except Exception as e:
                log.error(e)
        
        log.debug("Found {} interfaces: {}".format( len(MultiInstanceAPI.__interfaces_map__),
            ', '.join(list(MultiInstanceAPI.__interfaces_map__.keys())) ) )

    def __init__(self, platform_db: str, repository_type: str, default_driver: str):
        """ Create a MultiInstance API used to manage several clusters and nodes in a transparent manner

        :param platform_db: Path of the platform repository to use. The repository is used to store clusters and nodes information
        :type platform_db: str
        :param repository_type: Type of the repository storage
        :type repository_type: str
        :param default_driver: Default driver used to manage clusters (if no other one is provided)
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
        return yaml_load(Defaults.instances_conf)

    # --------------------------------------------------------------------------------
    # ########################### Operations with driver ############################
    # The following operations directly uses a driver interface to interact with nodes
    # --------------------------------------------------------------------------------

    def start_nodes(self, instances_num: Dict[str, int]) -> List[NodeInfo]:
        """ Start instances based on the configuration values

        :param instances_num: Dictionary containing the instance name as key and number of instances as value]
        :type instances_num: Dict[str, int]
        :return: List of created nodes 
        :rtype: List[NodeInfo]
        """
        return self._get_instance_iface(self.__default_driver).start_nodes(instances_num)

    def stop_nodes(self, node_ids: List[str]) -> List[str]:
        """ Stop started nodes based on their node ids

        :param node_ids: List of node ids to stop
        :type node_ids: List[str]
        """
        nodes = self.get_nodes(node_ids)
        stopped_nodes = []
        for cluster in self.__repository_operations.get_clusters(list(set(node.cluster_id for node in nodes))):
            stopped_nodes += self._get_instance_iface(cluster.driver_id).stop_nodes([
                node.node_id for node in nodes if node.cluster_id == cluster.cluster_id])
        return stopped_nodes

    def pause_nodes(self, node_ids: List[str]) -> List[str]:
        """ Pause started nodes based on their node ids

        :param node_ids: List of node ids to pause
        :type node_ids: List[str]
        """
        nodes = self.get_nodes(node_ids)
        paused_nodes = []
        for cluster in self.__repository_operations.get_clusters(list(set(node.cluster_id for node in nodes))):
            paused_nodes += self._get_instance_iface(cluster.driver_id).pause_nodes([
                node.node_id for node in nodes if node.cluster_id == cluster.cluster_id])
        return paused_nodes

    def resume_nodes(self, node_ids: List[str]) -> List[str]:
        """ Resume paused nodes based on their node ids

        :param node_ids: List of node ids to resume
        :type node_ids: List[str]
        """
        nodes = self.get_nodes(node_ids)
        resumed_nodes = []
        for cluster in self.__repository_operations.get_clusters(list(set(node.cluster_id for node in nodes))):
            resumed_nodes += self._get_instance_iface(cluster.driver_id).resume_nodes([
                node.node_id for node in nodes if node.cluster_id == cluster.cluster_id])
        return resumed_nodes

    def check_nodes_alive(self, node_ids: List[str]) -> Dict[str, bool]:
        nodes = self.get_nodes(node_ids)
        checked_nodes = dict()
        for cluster in self.__repository_operations.get_clusters(list(set(node.cluster_id for node in nodes))):
            checked_nodes.update(self._get_instance_iface(cluster.driver_id).check_nodes_alive([
                node.node_id for node in nodes if node.cluster_id == cluster.cluster_id]))
        return checked_nodes

    def execute_playbook_in_nodes(self, playbook_path: str, hosts: Union[List[str], Dict[str, List[str]]],
                                  extra_args: Dict[str, str] = ()) -> Dict[str, bool]:
        if not os.path.isfile(playbook_path):
            raise Exception("Invalid playbook at `{}`".format(playbook_path))

        if not hosts:
            raise Exception("No nodes to execute playbook `{}`".format(playbook_path))

        if isinstance(hosts, list):
            hosts = {'default': hosts}

        nodes = self.get_nodes([node_id for group_name, node_list in hosts.items() for node_id in node_list])
        executed_nodes = {}
        extra_args = extra_args if extra_args else {}

        for cluster in self.__repository_operations.get_clusters(list(set([node.cluster_id for node in nodes]))):
            new_hosts = dict()

            for group, node_list in hosts.items():
                node_ids = [node.node_id for node in self.__repository_operations.get_nodes(node_list)
                            if node.cluster_id == cluster.cluster_id]
                invalids = [node.node_id for node in self.__repository_operations.get_nodes(node_ids) if not node.ip]
                if invalids:
                    log.error("Nodes `{}` do not have a valid connection ip. Discarding it!".format(', '.join(invalids)))
                    for invalid in invalids:
                        executed_nodes[invalid] = False

                    node_ids = list(set(node_ids).difference(set(invalids)))

                if len(node_ids) == 0:
                    log.error("Discarding group `{}` because there is no nodes".format(group))
                else:
                    new_hosts[group] = node_ids

            if not new_hosts:
                raise Exception("No nodes to execute")

            executeds = self._get_instance_iface(cluster.driver_id).execute_playbook_in_nodes(
                playbook_path, new_hosts, extra_args)

            for node_id, status in executeds.items():
                if node_id in executed_nodes:
                    executed_nodes[node_id] = executed_nodes[node_id] and status
                else:
                    executed_nodes[node_id] = status

        return executed_nodes

    def get_connection_to_nodes(self, node_ids: List[str], *args, **kwargs) -> Dict[str, SSHClient]:
        nodes = self.get_nodes(node_ids)
        connections = dict()
        for cluster in self.__repository_operations.get_clusters(list({node.cluster_id for node in nodes})):
            connections.update(self._get_instance_iface(cluster.driver_id).get_connection_to_nodes([
                node.node_id for node in nodes if node.cluster_id == cluster.cluster_id], *args, **kwargs))
        return connections

    # --------------------------------------------------------------------------------
    # ########################### Operations with repository ##########################
    # The following operations directly uses the reporitory
    # --------------------------------------------------------------------------------

    def get_node(self, node_id: str) -> NodeInfo:
        try:
            return self.__repository_operations.get_node(node_id)
        except Exception:
            raise Exception("Invalid node with id `{}`".format(node_id))

    def get_nodes(self, node_ids: List[str] = None) -> List[NodeInfo]:
        if not node_ids:
            return self.__repository_operations.get_all_nodes()

        node_set = set(node_ids)
        nodes = self.__repository_operations.get_nodes(list(node_set))
        if len(nodes) != len(node_set):
            raise Exception("Some nodes are invalid: `{}`".format(', '.join(
                node_set.difference([node.node_id for node in nodes]))))

        return nodes

    def get_nodes_with_tags(self, tags: Dict[str, str]) -> List[NodeInfo]:
        tagged_nodes = []
        for node in self.__repository_operations.get_all_nodes():
            to_add = True
            for tag, val in tags.items():
                if tag not in node.tags or node.tags[tag] != val:
                    to_add = False
                    break

            if to_add:
                tagged_nodes.append(node)

        return tagged_nodes

    # --------------------------------------------------------------------------------
    # ########################### Operations with tags ###############################
    # The following operations add/remove tags from nodes
    # --------------------------------------------------------------------------------

    def add_tags_to_nodes(self, node_ids: List[str], tags: Dict[str, str]) -> List[str]:
        added_nodes = []
        for node in self.get_nodes(node_ids):
            node.tags.update(tags)
            self.__repository_operations.write_node_info(node, create=False)
            added_nodes.append(node.node_id)
        return added_nodes

    def remove_tags_from_nodes(self, node_ids: List[str], tags: List[str]) -> List[str]:
        removed_nodes = []
        for node in self.get_nodes(node_ids):
            for tag in tags:
                if tag in list(node.tags.keys()):
                    node.tags.pop(tag)
                    self.__repository_operations.write_node_info(node)
                    removed_nodes.append(node.node_id)

        return removed_nodes

    # --------------------------------------------------------------------------------
    # ########################### Operations with groups ###############################
    # The following perform group operations 
    # --------------------------------------------------------------------------------

    def get_groups(self) -> List[Tuple[str, List[str], List[str], str]]:
        groups = []
        for group_name in GroupInterface().get_group_names():
            group_actions, group_hosts, group_playbook = GroupInterface().get_group(group_name)
            groups.append((group_name, group_actions, group_hosts, group_playbook))
        return groups

    def __execute_group_action_sequence(self,  hosts: Dict[str, List[str]], actions: List[str], group_path: str,
                                        extra_args: Dict[str, str], error_action: str = 'error') -> List[str]:

        executeds = dict()

        for action in actions:
            # log.info("Setting up nodes `{}` with setup playbook: `{}`".format(', '.join(node_ids),
            #                                                                  path_extend(group_path, action)))
            extra_args['playbook_path'] = path_extend(group_path, action)
            executeds = self.execute_playbook_in_nodes(Defaults.execution_playbook, hosts, extra_args=extra_args)
            error_nodes = [node_id for node_id, status in executeds.items() if not status]

            if error_nodes:
                if error_action != 'ignore':
                    raise Exception("Error executing setup playbook `{}` in nodes `{}`. Aborting...".format(
                        action, ', '.join(error_nodes)))
                else:
                    ## Must handle ignore. Remove host from next iteration....
                    #             for group, host_list in hosts.items():
                    log.error("Error executing setup playbook `{}` in nodes `{}`. Ignoring these nodes...".format(
                        action, ', '.join(error_nodes)))
                    raise Exception("Not handling ignore...")

        return list(executeds.keys())

    def __check_nodes_in_group(self, group: str, node_ids: List[str] = None) -> List[str]:
        nodes = self.__repository_operations.get_nodes(node_ids) if node_ids else self.__repository_operations.get_all_nodes()
        members = []
        for node in nodes:
            if group in {group_name.split('/')[0] for group_name in list(node.groups.keys())}:
                members.append(node.node_id)

        return members

    def add_nodes_to_group(self, node_ids: List[str], group_name: str, group_args: Dict = None, error_action: str = 'error') -> List[str]:
        split_vals = group_name.split('/')

        if len(split_vals) > 2:
            raise Exception("Invalid group and hosts `{}`".format(group_name))

        return self.__add_nodes_to_group(
            {split_vals[0]: node_ids if len(split_vals) == 1 else {split_vals[1]: node_ids}},
            group_args,
            error_action)

    def __add_nodes_to_group(self, group_hosts_map: Dict[str, Union[List[str], Dict[str, List[str]]]],
                             group_args: Dict = None, error_action: str = 'error'):
        node_ids = []

        for group_name, hosts in group_hosts_map.items():
            group_actions, group_hosts, group_playbook = GroupInterface().get_group(group_name)

            if isinstance(hosts, dict):
                host_names = list(hosts.keys())
                invalid_hosts = [i for i in host_names if i not in group_hosts]
                if invalid_hosts:
                    raise ValueError("Invalid hosts `{}` for group `{}`".format(', '.join(invalid_hosts), group_name))

            elif isinstance(hosts, list):
                # All hosts if none, else default
                hosts = {h: hosts for h in group_hosts} if group_hosts else {'__default__': hosts}

            else:
                raise Exception("Invalid type for hosts (must be a list or a dict)")

            if 'setup' not in group_actions:
                raise Exception("Missing action `setup` in the playbook")

            group_args = group_args if group_args else {}
            group_args['action'] = 'setup'

            node_ids = self.__execute_group_action_sequence(
                hosts, [group_playbook], Defaults.groups_path, group_args, error_action)

            if len(node_ids) == 0:
                log.error("No nodes successfully executed setup")
                return []

            for host_name, host_list in hosts.items():
                for node_id in node_ids:
                    if node_id in host_list:
                        node = self.__repository_operations.get_node(node_id)
                        # TODO update or replace?
                        if host_name == '__default__':
                            node.groups[group_name] = group_args
                        else:
                            node.groups["{}/{}".format(group_name, host_name)] = group_args

                        self.__repository_operations.write_node_info(node)

        return node_ids

    def execute_group_action(self, group_name: str, action: str, group_args: Dict = None, node_ids: List[str] = None,
                             error_action='ignore'):
        split_vals = group_name.split('/')
        if len(split_vals) > 2:
            raise Exception("Invalid group and hosts `{}`".format(group_name))

        if node_ids:
            node_with_group = self.__check_nodes_in_group(split_vals[0], node_ids)
            if len(node_ids) != len(node_with_group):
                raise Exception("Nodes `{}` are not members of group `{}`".format(
                    ', '.join(set(node_ids).difference(set(node_with_group))), group_name))
        else:
            node_ids = self.__check_nodes_in_group(split_vals[0])

        if not node_ids:
            raise Exception("No nodes in group `{}` to perform action `{}`".format(group_name, action))

        # Verify in subgroup
        # TODO check subgroup not group
        if len(split_vals) > 1:
            node_with_group = [node.node_id for node in self.__repository_operations.get_nodes(node_ids)
                               if group_name in list(node.groups.keys())]

            if len(node_ids) != len(node_with_group):
                raise Exception("Nodes `{}` are not members of group `{}`".format(
                    ', '.join(set(node_ids).difference(set(node_with_group))), group_name))

        return self.__execute_group_action(node_ids, group_name, action, group_args, error_action)

    def __execute_group_action(self, node_ids: List[str], group_name: str, action: str, group_args: Dict = None,
                               error_action='error'):
        split_vals = group_name.split('/')
        group_name = split_vals[0]

        group_actions, group_hosts, group_playbook = GroupInterface().get_group(group_name)
        hosts_map = dict()

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

        log.info("Executing action `{}` of group `{}` in nodes `{}`".format(action, group_name, ', '.join(node_ids)))
        group_args['action'] = action
        node_ids = self.__execute_group_action_sequence(hosts_map, [group_playbook], Defaults.groups_path,
                                                        group_args, error_action)

        if len(node_ids) == 0:
            log.error("No nodes successfully executed action `{}`".format(action))
            return []

        return node_ids

    def remove_nodes_from_group(self, group_name: str, node_ids: List[str] = None, remove_action: str = None,
                                group_args: Dict = None):
        split_vals = group_name.split('/')

        if len(split_vals) > 2:
            raise Exception("Invalid group and hosts `{}`".format(group_name))

        if node_ids:
            node_with_group = self.__check_nodes_in_group(split_vals[0], node_ids)
            if len(node_ids) != len(node_with_group):
                raise Exception("Nodes `{}` are not members of group `{}`".format(
                    ', '.join(set(node_ids).difference(set(node_with_group))), group_name))
        else:
            node_ids = self.__check_nodes_in_group(split_vals[0])

        if not node_ids:
            raise Exception("No nodes in group `{}`".format(group_name))

        # Verify in subgroup
        # TODO check subgroup not group
        if len(split_vals) > 1:
            node_with_group = [node.node_id for node in self.__repository_operations.get_nodes(node_ids)
                               if group_name in list(node.groups.keys())]

            if len(node_ids) != len(node_with_group):
                raise Exception("Nodes `{}` are not members of group `{}`".format(
                    ', '.join(set(node_ids).difference(set(node_with_group))), group_name))

        if remove_action:
            removeds = self.__execute_group_action(node_ids, group_name, remove_action, group_args)
            if len(removeds) != len(node_ids):
                raise Exception("Nodes `{}` have failed to execute action `{}`".format(
                    ', '.join(set(node_ids).difference(set(removeds))), remove_action))

        for node_id in node_ids:
            node = self.__repository_operations.get_node(node_id)

            if len(split_vals) > 1:
                node.groups.pop(group_name)

            else:
                for gname in list(node.groups.keys()):
                    if gname == group_name or gname.startswith("{}/".format(gname)):
                        node.groups.pop(gname)
                    # else:
                    #    raise Exception()
            self.__repository_operations.write_node_info(node)

        return node_ids

    # --------------------------------------------------------------------------------
    # ########################### Save/Restore operations ##############################
    # The following perform group operations 
    # --------------------------------------------------------------------------------

    def export_platform(self, output_filename: str):
        pass

    def import_platform(self, zip_filename: str):
        pass
