import os
import glob
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Union, List, Optional

from marshmallow_dataclass import class_schema

from common.utils import yaml_load, path_extend, get_logger

logger = get_logger(__name__)


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
    def __init__(self, role_dir: str, actions_dir: str, private_dir: str,
                 load: bool = True):
        self.roles_dir: str = role_dir
        self.actions_dir: str = actions_dir
        self.private_dir: str = private_dir
        self.roles: Dict[str, Role] = dict()
        if load:
            self.load_roles()

    def load_roles(self):
        role_schema = class_schema(Role)()

        for role_file in os.listdir(self.actions_dir):
            role_name: str = Path(role_file).stem
            try:
                role_values: dict = yaml_load(path_extend(self.actions_dir, role_file))
                role: Role = role_schema.load(role_values)
                self.roles[role_name] = role
            except Exception as e:
                logger.error(
                    f"Discarding role '{role_name}'. {type(e).__name__}: {e}")
                continue

    @property
    def roles(self):
        return self.roles

    def get_role(self, role: str) -> Role:
        pass

    def add_role(self, role: str,
                 hosts_node_map: Union[List[str], Dict[str, List[str]]],
                 host_vars: Dict[str, Dict[str, str]] = None,
                 role_vars: Dict[str, Dict[str, str]] = None,
                 extra_args: Dict[str, str] = None,
                 quiet: bool = False) -> List[str]:
        pass

    def perform_action(self, role: str, action: str,
                       hosts_node_map: Union[List[str], Dict[str, List[str]]] = None,
                       host_vars: Dict[str, Dict[str, str]] = None,
                       role_vars: Dict[str, Dict[str, str]] = None,
                       extra_args: Dict[str, str] = None,
                       quiet: bool = False):
        pass

    def remove_role(self, role: str,
                    hosts_node_map: Union[List[str], Dict[str, List[str]]]) -> \
            List[str]:
        pass
