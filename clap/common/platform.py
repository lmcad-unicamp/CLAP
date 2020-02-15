import setuptools
import importlib.util
import os
from typing import List, Dict, Tuple
from paramiko import SSHClient

from clap.common.config import Defaults
from clap.common.driver import AbstractInstanceInterface
from clap.common.cluster_repository import RepositoryOperations, NodeInfo


# TODO: Surround try/except in starting nodes/cluster
# TODO: Treat SPOT instances; NodeInfo --(add)--> temporary field, spoted time
from clap.common.utils import path_extend, log


class ModuleInterface:
    """ Interface to get clap modules from the modules repository
    """
    __modules_map__ = dict()

    @staticmethod
    def __find_modules():
        if not ModuleInterface.__modules_map__:
            pass
            # for pkg_name in setuptools.find_packages(Defaults.modules_path):
            #     pkg = importlib.import_module('clap.modules.{}'.format(pkg_name))
            #     ModuleInterface.__modules_map__[pkg.name] = pkg
            # log.debug("Found {} modules."
            #           "{}".format(len(ModuleInterface.__modules_map__), ModuleInterface.__modules_map__))

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
        return list(self.__modules_map__.values())

    def get_module_names(self) -> List[str]:
        """ Get the name of all the modules in the clap modules repository

        :return: List containing the module names
        :rtype: List[str]
        """

        return [str(k) for k in self.__modules_map__.keys()]


class GroupInterface:
    __groups_actions_map__ = dict()

    GROUP_SCHEMA = None

    # TODO, must validate schema
    @staticmethod
    def __find_groups():
        if not GroupInterface.__groups_actions_map__:
            for pkg_name in setuptools.find_packages(Defaults.groups_path):
                spec = importlib.util.spec_from_file_location(pkg_name, path_extend(Defaults.groups_path, pkg_name, '__init__.py'))
                cls = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(cls)
                GroupInterface.__groups_actions_map__[pkg_name] = cls.actions

    def __init__(self):
        self.__find_groups()

    def get_group(self, group_name: str) -> Tuple[str, Dict[str, str]]:
        return path_extend(Defaults.groups_path, group_name), GroupInterface.__groups_actions_map__[group_name]

    def get_group_names(self) -> List[str]:
        return list(GroupInterface.__groups_actions_map__.keys())


class MultiInstanceAPI:
    """ API used to manage and perform operations in cluster and nodes from different driver implementations,
    and cloud providers in a transparently manner.
    """
    __interfaces_map__ = dict()

    @staticmethod
    def __find_ifaces():
        if not MultiInstanceAPI.__interfaces_map__:
            from clap.drivers.elasticluster.driver import ElasticlusterInterface
            MultiInstanceAPI.__interfaces_map__[ElasticlusterInterface.__interface_id__] = ElasticlusterInterface

            # for pkg_name in setuptools.find_packages(Defaults.drivers_path):
            #     pkg = importlib.import_module('clap.drivers.{}'.format(pkg_name))
            #     MultiInstanceAPI.__interfaces_map__[pkg.interface.__interface_id__] = pkg.interface
            # log.debug("Found {} interfaces. "
            #           "{}".format(len(MultiInstanceAPI.__interfaces_map__), MultiInstanceAPI.__interfaces_map__))

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

        return self.__interfaces_map__[driver_id](self.__repository_operations)

    def start_nodes(self, instances_num: Dict[str, int]) -> List[NodeInfo]:
        return self._get_instance_iface(self.__default_driver).start_nodes(instances_num)

    def stop_nodes(self, node_ids: List[str]):
        nodes = self.get_nodes(node_ids)
        for cluster in self.__repository_operations.get_clusters(list(set(node.cluster_id for node in nodes))):
            self._get_instance_iface(cluster.driver_id).stop_nodes([
                node.node_id for node in nodes if node.cluster_id == cluster.cluster_id])

    def pause_nodes(self, node_ids: List[str]):
        nodes = self.get_nodes(node_ids)
        for cluster in self.__repository_operations.get_clusters(list(set(node.cluster_id for node in nodes))):
            self._get_instance_iface(cluster.driver_id).pause_nodes([
                node.node_id for node in nodes if node.cluster_id == cluster.cluster_id])

    def check_nodes_alive(self, node_ids: List[str]) -> Dict[str, bool]:
        nodes = self.get_nodes(node_ids)
        checked_nodes = dict()
        for cluster in self.__repository_operations.get_clusters(list(set(node.cluster_id for node in nodes))):
            checked_nodes.update(self._get_instance_iface(cluster.driver_id).check_nodes_alive([
                node.node_id for node in nodes if node.cluster_id == cluster.cluster_id]))
        return checked_nodes

    def execute_playbook_in_nodes(self, node_ids: List[str], playbook_path: str, *args, **kwargs) -> Dict[str, bool]:
        if not os.path.isfile(playbook_path):
            raise Exception("Invalid playbook at `{}`".format(playbook_path))

        if not node_ids:
            return {}

        nodes = self.get_nodes(node_ids)
        executed_nodes = {}

        for node in nodes:
            if not node.ip:
                log.error("Node `{}` does not have an connection ip. Try checking if it is alive first! "
                          "Discarding it".format(node.node_id))
                nodes.remove(node)
                executed_nodes[node.node_id] = False

        for cluster in self.__repository_operations.get_clusters(list({node.cluster_id for node in nodes})):
            to_exec_nodes = [node.node_id for node in nodes if node.cluster_id == cluster.cluster_id]

            if not to_exec_nodes:
                continue

            executed_nodes.update(self._get_instance_iface(cluster.driver_id).execute_playbook_in_nodes(
                to_exec_nodes, playbook_path, *args, **kwargs))

        return executed_nodes

    def get_connection_to_nodes(self, node_ids: List[str], *args, **kwargs) -> Dict[str, SSHClient]:
        nodes = self.get_nodes(node_ids)
        connections = dict()
        for cluster in self.__repository_operations.get_clusters(list({node.cluster_id for node in nodes})):
            connections.update(self._get_instance_iface(cluster.driver_id).get_connection_to_nodes([
                node.node_id for node in nodes if node.cluster_id == cluster.cluster_id], *args, **kwargs))
        return connections

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

    def get_groups(self):
        return GroupInterface().get_group_names()

    def __execute_group_action_sequence(self, node_ids: List[str], actions: List[str], group_path: str,
                                        group_args: Dict, error_action: str):
        for action in actions:
            log.info("Setting up nodes `{}` with setup playbook: `{}`".format(', '.join(node_ids),
                                                                              path_extend(group_path, action)))

            executeds = self.execute_playbook_in_nodes(node_ids, path_extend(group_path, action), **group_args)
            error_nodes = [node_id for node_id, status in executeds.items() if not status]

            if error_action != 'ignore':
                raise Exception("Error executing setup playbook `{}` in nodes `{}`. Aborting...".format(
                    action, ', '.join(error_nodes)))

            if error_nodes:
                log.error("Error executing setup playbook `{}` in nodes `{}`. Ignoring these nodes...".format(
                    action, ', '.join(error_nodes)))

                node_ids = list(set(node_ids).difference(set(error_nodes)))
        return node_ids

    def __check_nodes_in_group(self, node_ids: List[str], group: str):
        nodes = self.__repository_operations.get_nodes(node_ids)
        return [node.node_id for node in nodes if group in node.groups]

    def add_nodes_to_group(self, node_ids: List[str], group: str, group_args: Dict = None, error_action='ignore'):
        log.info("Adding nodes `{}` to group `{}`".format(', '.join(node_ids), group))
        group_path, group_actions = GroupInterface().get_group(group)

        if 'setup' in group_actions:
            setup_actions = [group_actions['setup']] if isinstance(group_actions['setup'], str) else group_actions['setup']
            group_args = group_args if group_args else {}

            node_ids = self.__execute_group_action_sequence(node_ids, setup_actions, group_path, group_args, error_action)

            if len(node_ids) == 0:
                log.error("No nodes successfully executed setup")
                return []

        nodes = self.__repository_operations.get_nodes(node_ids)
        for node in nodes:
            node.groups[group] = group_args
            self.__repository_operations.write_node_info(node)

        return node_ids

    def execute_action_in_nodes_of_group(self, group: str, action: str, group_args: Dict = None, error_action='ignore'):
        node_ids = [node.node_id for node in self.__repository_operations.get_all_nodes() if group in list(node.groups.keys())]
        if not node_ids:
            raise Exception("No nodes in group `{}`".format(group))
        return self.execute_group_action(node_ids, group, action, group_args, error_action)

    def execute_group_action(self, node_ids: List[str], group: str, action: str, group_args: Dict = None, error_action='ignore'):
        log.info("Executing action `{}` of group `{}` in nodes `{}`".format(action, group, ', '.join(node_ids)))
        group_path, group_actions = GroupInterface().get_group(group)

        node_with_group = self.__check_nodes_in_group(node_ids, group)
        if len(node_ids) != len(node_with_group):
            raise Exception("Nodes `{}` are not members of group `{}`".format(
                ', '.join(set(node_ids).difference(set(node_with_group))), group))

        actions = [group_actions[action]] if isinstance(group_actions[action], str) else group_actions[action]
        group_args = group_args if group_args else {}

        node_ids = self.__execute_group_action_sequence(node_ids, actions, group_path, group_args, error_action)

        if len(node_ids) == 0:
            log.error("No nodes successfully executed action `{}`".format(action))
            return []

        nodes = self.__repository_operations.get_nodes(node_ids)
        for node in nodes:
            node.groups[group] = group_args
            self.__repository_operations.write_node_info(node)

        return node_ids

    def remove_node_from_group(self, node_ids: List[str], group: str, group_args: Dict = None, error_action='ignore'):
        log.info("Removing group `{}` from nodes `{}`".format(group, ', '.join(node_ids)))
        group_path, group_actions = GroupInterface().get_group(group)

        node_with_group = self.__check_nodes_in_group(node_ids, group)
        if len(node_ids) != len(node_with_group):
            raise Exception("Nodes `{}` are not members of group `{}`".format(
                ', '.join(set(node_ids).difference(set(node_with_group))), group))

        if 'stop' in group_actions:
            stop_actions = [group_actions['stop']] if isinstance(group_actions['stop'], str) else group_actions['stop']
            group_args = group_args if group_args else {}

            node_ids = self.__execute_group_action_sequence(node_ids, stop_actions, group_path, group_args, error_action)

        if len(node_ids) == 0:
            log.error("No nodes successfully executed stop")
            return []

        nodes = self.__repository_operations.get_nodes(node_ids)
        for node in nodes:
            node.groups.pop(group)
            self.__repository_operations.write_node_info(node)

        return node_ids
