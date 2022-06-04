import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Union, List, Optional, Set

import dacite

from clap.executor import AnsiblePlaybookExecutor
from clap.node import NodeDescriptor
from clap.node_manager import NodeRepositoryController
from clap.utils import yaml_load, path_extend, get_logger

logger = get_logger(__name__)


class RoleError(Exception):
    pass


class InvalidRoleError(RoleError):
    def __init__(self, role_name: str):
        self.role_name = role_name
        super().__init__(f"Invalid role named: {role_name}")


class InvalidActionError(RoleError):
    def __init__(self, role_name: str, action_name: str):
        self.role_name = role_name
        self.action_name = action_name
        super().__init__(f"Invalid action '{action_name}' for role {role_name}")


class InvalidHostError(RoleError):
    def __init__(self, role_name: str, host_name: str):
        self.role_name = role_name
        self.host_name = host_name
        super().__init__(f"Invalid host '{host_name}' for role '{role_name}'")


class RoleAssignmentError(RoleError):
    pass


class NodeRoleError(RoleError):
    def __init__(self, node_id: str, role_name: str, host_name: str = None):
        self.node_id = node_id
        self.role_name = role_name
        self.host_name = host_name
        rname = role_name if not host_name else f"{role_name}/{host_name}"
        super().__init__(f"Node {node_id} does not belong to {rname}")


class MissingActionVariableError(RoleError):
    def __init__(self, role_name: str, action_name: str, var: str):
        self.role_name = role_name
        self.action_name = action_name
        self.var = var
        super().__init__(f"Missing the required variable '{var}' for action "
                         f"'{action_name}' of role '{role_name}'")


@dataclass
class RoleVariableInfo:
    name: str
    description: Optional[str]
    optional: Optional[bool] = False


@dataclass
class RoleActionInfo:
    playbook: str
    description: Optional[str]
    vars: Optional[List[RoleVariableInfo]] = field(default_factory=list)


@dataclass
class Role:
    actions: Optional[Dict[str, RoleActionInfo]] = field(default_factory=dict)
    hosts: Optional[List[str]] = field(default_factory=list)


class RoleManager:
    def __init__(self, node_repository_controller: NodeRepositoryController,
                 role_dir: str, actions_dir: str, private_dir: str,
                 discard_invalids: bool = True, load: bool = True):
        self.node_repository = node_repository_controller
        self.roles_dir: str = role_dir
        self.actions_dir: str = actions_dir
        self.private_dir: str = private_dir
        self.roles: Dict[str, Role] = dict()
        self._discard_invalids = discard_invalids
        if load:
            self.load_roles()

    def get_all_role_nodes(self, role_name: str) -> List[str]:
        nodes = self.node_repository.get_nodes_filter(
            lambda n: role_name in n.roles or f"{role_name}/" in n.roles
        )
        return [n.node_id for n in nodes]

    def get_role_node_hosts(self, role_name: str, node_id: str) -> List[str]:
        role = self.roles[role_name]
        node = self.node_repository.get_nodes_by_id([node_id])[0]

        hosts = []
        if role.hosts:
            for hname in role.hosts:
                search_for = f"{role_name}/{hname}"
                if search_for in node.roles:
                    hosts.append(hname)
        else:
            if role_name in node.roles:
                hosts = ['']

        return hosts

    def get_all_role_nodes_hosts(self, role_name: str) -> \
            Dict[str, List[str]]:
        role = self.roles[role_name]
        if role.hosts:
            search_for = [f"{role_name}/{host}" for host in role.hosts]
        else:
            search_for = [role_name]

        host_nodes_map = {
            rname.split('/')[-1]: [
                node.node_id
                for node in self.node_repository.get_nodes_filter(
                    lambda n: rname in n.roles
                )
            ]
            for rname in search_for
        }

        if not role.hosts:
            host_nodes_map = {'': host_nodes_map[role_name]}

        return host_nodes_map

    def get_role_nodes(self, role_name: str, from_node_ids: List[str] = None) -> \
            Dict[str, List[str]]:
        role = self.roles[role_name]
        if role.hosts:
            search_for = [f"{role_name}/{host}" for host in role.hosts]
        else:
            search_for = [role_name]

        if not from_node_ids:
            nodes = {
                rname.split('/')[-1]:  [
                    node.node_id
                    for node in self.node_repository.get_nodes_filter(
                        lambda n: rname in n.roles)
                ]
                for rname in search_for
            }
        else:
            nodes = {
                rname.split('/')[-1]:  [
                    node.node_id
                    for node in self.node_repository.get_nodes_filter(
                        lambda n: n.node_id in from_node_ids and rname in n.roles)
                ]
                for rname in search_for
            }
        return nodes

    def load_roles(self):
        for role_file in os.listdir(self.actions_dir):
            role_name: str = Path(role_file).stem
            try:
                role_values: dict = yaml_load(path_extend(self.actions_dir, role_file))
                role = dacite.from_dict(data_class=Role, data=role_values)
                if role.actions is None: role.actions = dict()
                self.roles[role_name] = role
            except Exception as e:
                if self._discard_invalids:
                    logger.error(
                        f"Discarding role '{role_name}'. {type(e).__name__}: {e}")
                    continue
                else:
                    raise e

    def add_role(self, role_name: str,
                 hosts_node_map: Union[List[str], Dict[str, List[str]]],
                 host_vars: Dict[str, Dict[str, str]] = None,
                 node_vars: Dict[str, Dict[str, str]] = None,
                 extra_args: Dict[str, str] = None,
                 quiet: bool = False) -> List[str]:
        if role_name not in self.roles:
            raise InvalidRoleError(role_name)
        role: Role = self.roles[role_name]

        if role.hosts:
            if type(hosts_node_map) is list:
                inventory: Dict[str, List[str]] = \
                    {h: hosts_node_map for h in role.hosts}
            else:
                for host_name in hosts_node_map.keys():
                    if host_name not in role.hosts:
                        raise InvalidHostError(role_name, host_name)
                inventory: Dict[str, List[str]] = hosts_node_map
        else:
            if type(hosts_node_map) is list:
                inventory: Dict[str, List[str]] = {'': hosts_node_map}
            else:
                if len(hosts_node_map) != 1 or role_name not in hosts_node_map:
                    raise ValueError(f"Invalid hosts {list(hosts_node_map.keys())} "
                                     f"for role {role_name}")
                inventory: Dict[str, List[str]] = {'': hosts_node_map[role_name]}

        if 'setup' in role.actions:
            result = self.perform_action(
                role_name, 'setup', inventory, host_vars, node_vars, extra_args,
                quiet=quiet, validate_nodes_in_role=False)
            if not result.ok:
                raise RoleAssignmentError(
                    f"Error executing setup action's playbook for role "
                    f"{role_name}. Nodes were not assigned to role."
                )
            if result.ret_code != 0:
                raise RoleAssignmentError(
                    f"Error executing setup action's playbook for role "
                    f"{role_name}. Playbook finished with non-zero return code "
                    f"({result.ret_code}). Nodes were not assigned to role."
                )
            # TODO check if, for each node, playbook was ok (checking result.hosts status)

        added_nodes: Set[str] = set()
        for host, list_node_ids in inventory.items():
            name = role_name if host == '' else f'{role_name}/{host}'
            for node in self.node_repository.get_nodes_by_id(list_node_ids):
                added_nodes.add(node.node_id)
                if name not in node.roles:
                    node.roles.append(name)
                    self.node_repository.upsert_node(node)

        return list(added_nodes)

    def _check_nodes_role(self, role_name: str, host_map: Dict[str, List[NodeDescriptor]]):
        if role_name not in self.roles:
            raise InvalidRoleError(role_name)
        role: Role = self.roles[role_name]

        if role.hosts:
            for hname, nodes in host_map.items():
                search_for = f"{role_name}/{hname}"
                for node in nodes:
                    if search_for not in node.roles:
                        raise NodeRoleError(node.node_id, role_name, hname)
        else:
            if '' not in host_map:
                raise ValueError(
                    "host_map variable must define key empty string key")
            for node in host_map['']:
                if role_name not in node.roles:
                    raise NodeRoleError(node.node_id, role_name)

    def perform_action(self, role_name: str, action_name: str,
                       hosts_node_map: Union[List[str], Dict[str, List[str]]],
                       host_vars: Dict[str, Dict[str, str]] = None,
                       node_vars: Dict[str, Dict[str, str]] = None,
                       extra_args: Dict[str, str] = None,
                       quiet: bool = False,
                       validate_nodes_in_role: bool = True) -> \
            AnsiblePlaybookExecutor.PlaybookResult:
        """

        :param role_name:
        :param action_name:

        """
        host_vars = host_vars or dict()
        node_vars = node_vars or dict()
        extra_args = extra_args or dict()

        if role_name not in self.roles:
            raise InvalidRoleError(role_name)
        role: Role = self.roles[role_name]

        if action_name not in role.actions:
            raise InvalidActionError(role_name, action_name)
        action = role.actions[action_name]

        # Check hosts_node_map variable
        if not role.hosts:
            if type(hosts_node_map) is list:
                _inventory = {'': hosts_node_map}
            elif type(hosts_node_map) is dict:
                if '' not in hosts_node_map:
                    raise ValueError("hosts_node_map variable must contain "
                                     "'None' key.")
                _inventory = {'': hosts_node_map['']}
            else:
                raise TypeError(f"hosts_node_map variable expects a list or a dict, "
                                f"not a {type(hosts_node_map)}")
        else:
            if type(hosts_node_map) is not dict:
                raise TypeError(f"As role {role_name} defines hosts, hosts_node_map "
                                f"variable expects a dict, not a {type(hosts_node_map)}")
            _inventory = dict()
            for hname, node_list in hosts_node_map.items():
                if hname not in role.hosts:
                    raise InvalidHostError(role_name, hname)
                _inventory[hname] = node_list

        # Expand node_ids to NodeDescriptors
        inventory: Dict[str, List[NodeDescriptor]] = {
            host_name: self.node_repository.get_nodes_by_id(list_nodes)
            for host_name, list_nodes in _inventory.items()
        }

        if validate_nodes_in_role:
            self._check_nodes_role(role_name, inventory)

        if not role.hosts:
            inventory = {role_name: inventory['']}

        # Check if every required role's action variable is informed via extra_args
        for var in action.vars:
            if not var.optional:
                if var.name not in extra_args:
                    raise MissingActionVariableError(
                        role_name, action_name, var.name
                    )

        # Expand playbook path
        playbook_file = path_extend(self.roles_dir, action.playbook)
        # Create ansible-like inventory
        inventory = AnsiblePlaybookExecutor.create_inventory(
            inventory, self.private_dir, host_vars, node_vars)

        # Crate playbook executor and run
        playbook = AnsiblePlaybookExecutor(
            playbook_file, self.private_dir, inventory, extra_args, quiet=quiet)
        logger.info(f'Executing playbook {playbook_file} with inventory: '
                    f'{inventory}')
        result = playbook.run()
        return result

    def remove_role(self, role_name: str,
                    hosts_node_map: Union[List[str], Dict[str, List[str]]]) -> \
            List[str]:
        role = self.roles[role_name]

        if not role.hosts:
            if type(hosts_node_map) is list:
                _inventory = {'': hosts_node_map}
            elif type(hosts_node_map) is dict:
                if '' not in hosts_node_map:
                    raise ValueError("hosts_node_map variable must contain "
                                     "'None' key.")
                _inventory = {'': hosts_node_map['']}
            else:
                raise TypeError(f"hosts_node_map variable expects a list or a dict, "
                                f"not a {type(hosts_node_map)}")
        else:
            _inventory = hosts_node_map

        # Expand node_ids to NodeDescriptors
        inventory: Dict[str, List[NodeDescriptor]] = {
            host_name: self.node_repository.get_nodes_by_id(list_nodes)
            for host_name, list_nodes in _inventory.items()
        }

        self._check_nodes_role(role_name, inventory)
        node_set = set()

        for h, node_list in hosts_node_map.items():
            if h == '':
                h = role_name
            else:
                h = f"{role_name}/{h}"

            for node in self.node_repository.get_nodes_by_id(node_list):
                node.roles.remove(h)
                self.node_repository.upsert_node(node)
                node_set.add(node.node_id)

        return list(node_set)
