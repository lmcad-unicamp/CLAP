import jinja2
import os

from typing import List, Dict, Union, Optional
from dataclasses import dataclass, field
from marshmallow_dataclass import class_schema

from common.clap import AbstractModule, Runner
from common.config import Config as BaseDefaults
from common.utils import path_extend, yaml_load, get_logger, Singleton
from modules.node import NodeModule

logger = get_logger(__name__)


class GroupDefaults(metaclass=Singleton):
    def __init__(self):
        self.base_defaults = BaseDefaults()
        self.groups_path = path_extend(self.base_defaults.clap_path, 'groups')

@dataclass
class VariableInfo:
    name: str
    description: Optional[str] = ''
    optional: Optional[bool] = False


@dataclass
class ActionInfo:
    playbook: str
    description: Optional[str]
    vars: Optional[List[VariableInfo]] = field(default_factory=list)


@dataclass
class GroupInfo:
    actions: Optional[Dict[str, ActionInfo]] = field(default_factory=dict)
    hosts: Optional[List[str]] = field(default_factory=list)


class GroupLoader(object):
    VariableInfoSchema = class_schema(VariableInfo)
    ActionInfoSchema = class_schema(ActionInfo)
    GroupInfoSchema = class_schema(GroupInfo)

    def __init__(self, action_path: str):
        self.action_path = action_path
        self.variable_info_schema = self.VariableInfoSchema()
        self.action_info_schema = self.ActionInfoSchema()
        self.group_info_schema = self.GroupInfoSchema()

    def load_groups(self) -> Dict[str, GroupInfo]:
        groups = dict()

        for group_file in os.listdir(self.action_path):
            if not group_file.endswith('.yml'):
                continue
            group_name = group_file[:-4]

            try:
                group_values = yaml_load(path_extend(self.action_path, group_file))
                groups[group_name] = self.group_info_schema.load(group_values)
            except Exception as e:
                logger.error(f"Discarding group `{group_name}`: {type(e).__name__}: {e}")
                continue

        return groups


class GroupModule(AbstractModule):
    module_name = 'group'
    module_version = '0.1.0'
    module_description = 'Perform group operations in nodes'
    module_tags = ['group', 'instances']

    @staticmethod
    def get_module(**defaults_override) -> 'GroupModule':
        group_defaults = GroupDefaults()
        groups_path = defaults_override.get('groups_path', group_defaults.groups_path)
        return GroupModule(groups_path)

    def __init__(self, groups_path: str):
        self.node_module = NodeModule.get_module()
        self.groups_path = groups_path
        self.templates_path = path_extend(os.path.dirname(os.path.abspath(__file__)), 'templates')
        self.jinjaenv = jinja2.Environment(loader=jinja2.FileSystemLoader(self.templates_path), trim_blocks=True,
                                           lstrip_blocks=True)
        self.groups = self.list_groups()

    def add_group_to_nodes(self, group_name: str,
                           group_hosts_map: Union[Dict[str, List[str]], List[str]],
                           extra_args: Dict[str, str] = None,
                           group_vars: Dict[str, Dict[str, str]] = None,
                           host_vars: Dict[str, Dict[str, str]] = None,
                           quiet: bool = False) -> List[str]:
        all_nodes = set()
        # Invalid host map?
        if not group_hosts_map:
            raise Exception("Invalid host map to add group to nodes")
        # Checking group values
        if group_name not in self.groups:
            raise Exception(f"Invalid group with name `{group_name}`")

        # Is type of group a list --> Create a map with the nodes to all hosts of the group
        if type(group_hosts_map) is list:
            hosts = self.groups[group_name].hosts or ['__default__']
            group_hosts_map = {host: group_hosts_map for host in hosts}
        else:
            # Check if all groups are valid
            invalid_hosts = [host for host in group_hosts_map.keys() if
                             host not in self.groups[group_name].hosts and host != '__default__']
            if invalid_hosts:
                raise Exception(f"Invalid host `{', '.join(sorted(invalid_hosts))}` for group `{group_name}`")

        all_nodes.update(set(node_id for _, host_list in group_hosts_map.items() for node_id in host_list))

        # Check if all nodes exists...
        self.node_module.get_nodes_by_id(node_ids=list(all_nodes))

        if 'setup' in self.groups[group_name].actions:
            playbook = self.groups[group_name].actions['setup'].playbook
            path = path_extend(self.groups_path, playbook)
            logger.info(f"Executing playbook at `{path}` with host map: `{group_hosts_map}`")
            runner_res = self.node_module.execute_playbook_in_nodes(playbook_path=path, group_hosts_map=group_hosts_map,
                                                                    extra_args=extra_args, group_vars=group_vars,
                                                                    host_vars=host_vars, quiet=quiet)

            if not runner_res.ok:
                raise Exception("Playbook not executed successfully")

            not_successfully_executed = [node_id for node_id, res in runner_res.hosts.items() if not res]
            if len(not_successfully_executed) > 0:
                raise Exception(f"Nodes `{', '.join(sorted(not_successfully_executed))}` does not successfully "
                                f"executed playbook `{playbook}` (group: {group_name}, action: setup)")
            logger.info(f"Playbook at `{path}` successfully executed")

        for host, host_list in group_hosts_map.items():
            for node in self.node_module.get_nodes_by_id(node_ids=host_list):
                if group_name not in node.groups:
                    node.groups[group_name] = [host]
                else:
                    node.groups[group_name] = list(set(node.groups[group_name] + [host]))
                self.node_module.upsert_node(node)

        return list(all_nodes)

    def execute_group_action(self, group_name: str, action_name: str,
                             node_ids: Union[List[str], Dict[str, List[str]]] = None,
                             extra_args: Dict[str, str] = None,
                             group_vars: Dict[str, Dict[str, str]] = None,
                             host_vars: Dict[str, Dict[str, str]] = None,
                             quiet: bool = False) -> Runner.PlaybookResult:
        if group_name not in self.groups:
            raise Exception(f"No group called {group_name}")
        if action_name not in self.groups[group_name].actions:
            raise Exception(f"Invalid action `{action_name}` for group `{group_name}`")

        action = self.groups[group_name].actions[action_name]
        nodes_host_map = dict()
        invalid_nodes = set()

        # Does it a list?
        if not node_ids or type(node_ids) is list:
            # Iterate over all nodes
            nodes = self.node_module.get_nodes_by_id(node_ids=node_ids) if node_ids else self.node_module.get_all_nodes()
            for node in nodes:
                if group_name not in node.groups:
                    invalid_nodes.add(node.node_id)
                    continue
                for host in node.groups[group_name]:
                    if host not in nodes_host_map:
                        nodes_host_map[host] = [node.node_id]
                    else:
                        nodes_host_map[host].append(node.node_id)
        else:
            for host, host_list in node_ids.items():
                if host not in self.groups[group_name].hosts and host != '__default__':
                    raise Exception(f"Invalid host `{host}` for group `{group_name}`")
                for node in self.node_module.get_nodes_by_id(node_ids=host_list):
                    if group_name not in node.groups:
                        invalid_nodes.add(node.node_id)
                        continue
                    if host not in node.groups[group_name]:
                        invalid_nodes.add(node.node_id)
            nodes_host_map = node_ids

        if node_ids and invalid_nodes:
            raise Exception(f"Nodes `{', '.join(sorted(invalid_nodes))}` does not belong to group `{group_name}`")
        if not nodes_host_map:
            raise Exception(f"No nodes provided to perform action `{action_name}` of group `{group_name}`")

        path = path_extend(self.groups_path, action.playbook)
        logger.info(f"Executing playbook at `{path}` with host map: `{nodes_host_map}`")
        runner_res = self.node_module.execute_playbook_in_nodes(
            playbook_path=path,
            group_hosts_map=nodes_host_map,
            extra_args=extra_args,
            group_vars=group_vars,
            host_vars=host_vars,
            quiet=quiet)

        return runner_res

    def list_groups(self) -> Dict[str, GroupInfo]:
        return GroupLoader(path_extend(self.groups_path, 'actions.d')).load_groups()

    def remove_group_from_node(self, group_name: str, node_ids: Union[List[str], Dict[str, List[str]]]) -> List[str]:
        all_nodes = set()
        if type(node_ids) is list:
            for node in self.node_module.get_nodes_by_id(node_ids=node_ids):
                if group_name not in node.groups:
                    raise Exception(f"Node `{node.node_id}` does not belong to group `{group_name}`")
                node.groups.pop(group_name)
                self.node_module.upsert_node(node)
                all_nodes.add(node.node_id)
        else:
            for host, host_list in node_ids.items():
                for node in self.node_module.get_nodes_by_id(node_ids=host_list):
                    if group_name not in node.groups:
                        raise Exception(f"Node `{node.node_id}` does not belong to group `{group_name}`")
                    if host not in node.groups[group_name]:
                        raise Exception(
                            f"Node `{node.node_id}` does not belong to group `{group_name}` with host `{host}`")
                    node.groups[group_name].remove(host)
                    if len(node.groups[group_name]) == 0:
                        node.groups.pop(group_name)
                    self.node_module.upsert_node(node)
                    all_nodes.add(node.node_id)
        return list(all_nodes)

