import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Union, List, Optional, Set

import dacite

from common.executor import AnsiblePlaybookExecutor
from common.node import NodeRepositoryController, NodeDescriptor
from common.utils import yaml_load, path_extend, get_logger

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
    def __init__(self, node_id: str, role_name: str):
        self.node_id = node_id
        self.role_name = role_name
        super().__init__(f"Node {node_id} does not belong to {role_name}")


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
    optional: Optional[bool]


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
                inventory: Dict[str, List[str]] = {role_name: hosts_node_map}
            else:
                if len(hosts_node_map) != 1 or role_name not in hosts_node_map:
                    raise ValueError(f"Invalid hosts {list(hosts_node_map.keys())} "
                                     f"for role {role_name}")
                inventory: Dict[str, List[str]] = hosts_node_map

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
            name = host if host == role_name else f'{role_name}/{host}'
            for node in self.node_repository.get_nodes_by_id(list_node_ids):
                added_nodes.add(node.node_id)
                if name not in node.roles:
                    node.roles.append(name)
                    self.node_repository.upsert_node(node)

        return list(added_nodes)

    def perform_action(self, role_name: str, action_name: str,
                       hosts_node_map: Union[List[str], Dict[str, List[str]]],
                       host_vars: Dict[str, Dict[str, str]] = None,
                       node_vars: Dict[str, Dict[str, str]] = None,
                       extra_args: Dict[str, str] = None,
                       quiet: bool = False,
                       validate_nodes_in_role: bool = True) -> \
            AnsiblePlaybookExecutor.PlaybookResult:
        host_vars = host_vars or dict()
        node_vars = node_vars or dict()
        extra_args = extra_args or dict()

        if role_name not in self.roles:
            raise InvalidRoleError(role_name)
        role: Role = self.roles[role_name]

        if action_name not in role.actions:
            raise InvalidActionError(role_name, action_name)
        action = role.actions[action_name]

        # The role has hosts? If True, hosts_node_map must provide a dict like:
        # hosts_node_map = {
        #   'host-a': ['node-1', 'node-2', ...],
        #   'host-b': ['node-x', 'node-y']
        # }
        if role.hosts:
            if type(hosts_node_map) is not dict:
                raise TypeError(f"The role '{role_name}' defines "
                                f"{len(role.hosts)} hosts. It must be informed "
                                f"which nodes belong to each role's host, as a dict")
            # Check if provided host_names are valid
            for host_name in hosts_node_map.keys():
                if host_name not in role.hosts:
                    raise InvalidHostError(role_name, host_name)
            inventory: Dict[str, List[str]] = hosts_node_map
        # The role has hosts? If false, hosts_node_map must provide a list like:
        # ['node-1', 'node-2']
        # or a dict like (dict must have only one entry):
        # { role_name: ['node-1', 'node-2'] }
        # It will be expanded (result) to:
        # { role_name: ['node-1', 'node-2'] }
        else:
            if type(hosts_node_map) is dict:
                # Check format: {role_name: ['node-1', 'node-2']}
                if len(hosts_node_map) != 1 or role_name not in hosts_node_map:
                    raise ValueError(f"Invalid hosts {list(hosts_node_map.keys())} "
                                     f"for role {role_name}")
                inventory: Dict[str, List[str]] = hosts_node_map
            elif type(hosts_node_map) is list:
                # If it's a list, simple expand to { role_name: ['node-1, ...] }
                inventory: Dict[str, List[str]] = {role_name: hosts_node_map}
            else:
                raise TypeError(f"The role '{role_name}' does not define any "
                                f"host. It must be informed the nodes as a list "
                                f"or a valid dict.")

        # Expand node_ids to NodeDescriptors
        inventory: Dict[str, List[NodeDescriptor]] = {
            host_name: self.node_repository.get_nodes_by_id(list_nodes)
            for host_name, list_nodes in inventory.items()
        }

        # Validate if a node belongs to a role.
        if validate_nodes_in_role:
            # { role_name: ['node-1', 'node-2'] }
            if role_name in inventory:
                for n in inventory[role_name]:
                    if role_name not in n.roles:
                        raise NodeRoleError(n.node_id, role_name)
            # {
            #   'host-a': ['node-1', 'node-2', ...],
            #   'host-b': ['node-x', 'node-y']
            # }
            else:
                for host_name, list_nodes in inventory.items():
                    for node in list_nodes:
                        if f"{role_name}/{host_name}" not in node.roles:
                            raise NodeRoleError(
                                node.node_id, f"{role_name}/{host_name}")

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
        pass


if __name__ == '__main__':
    from dataclasses import asdict
    from common.repository import RepositoryFactory
    from common.utils import setup_log

    setup_log(verbosity_level=3)
    node_repository_path = '/home/lopani/.clap/storage/nodes.db'
    private_path = '/home/lopani/.clap/private'
    repository = RepositoryFactory().get_repository('sqlite', node_repository_path)
    repository_controller = NodeRepositoryController(repository)

    role_manager = RoleManager(
        repository_controller,
        '/home/lopani/.clap/groups',
        '/home/lopani/.clap/groups/actions.d',
        '/home/lopani/.clap/private'
    )

    for rid, r in role_manager.roles.items():
        print(f"------ {rid} -------")
        print(r)

    all_nodes = repository_controller.get_all_nodes()
    print("**** Nodes ****")
    for node in all_nodes:
        print(asdict(node))

    # added_nodes = role_manager.add_role(
    #     'commands-common', [n.node_id for n in all_nodes])
    # print(f"Added nodes: {added_nodes}")
    # #
    # all_nodes = repository_controller.get_all_nodes()
    # print("**** Nodes ****")
    # for node in all_nodes:
    #     print(asdict(node))

    nodes = role_manager.get_role_nodes('commands-common')

    result = role_manager.perform_action(
        'commands-common', 'install-packages', nodes,
        extra_args={'packages': 'gcc'}
    )
    print(f"RESULT: {result}")
