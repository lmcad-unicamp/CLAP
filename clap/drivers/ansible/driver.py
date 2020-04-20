import json
import logging
import os.path
import platform
import shlex
import tempfile
from collections import defaultdict
from datetime import datetime
from subprocess import call
from time import time
from typing import Optional, List, Dict, Set, Tuple, Union, Any

import paramiko
import yaml
from ansible.parsing.dataloader import DataLoader
from ansible.vars.manager import VariableManager
from ansible.inventory.manager import Inventory
from ansible.executor.playbook_executor import PlaybookExecutor
from pkg_resources import resource_filename

from clap.common.cluster_repository import RepositoryOperations, ClusterInfo, NodeInfo
from clap.common.config import Defaults, ConfigReader
from clap.common.driver import AbstractInstanceInterface, Codes
from clap.common.utils import path_extend, log


class AnsibleInterface(AbstractInstanceInterface):
        __interface_id__ = 'ansible'

    def __init__(self, repository_operator: RepositoryOperations):
        super(AnsibleInterface, self).__init__(repository_operator)
        self.cluster_prefix = 'clap'
        self.node_prefix = 'node'

    def start_nodes(self, instances_num: Dict[str, int]) -> List[NodeInfo]:
        reader = ConfigReader(Defaults.cloud_conf, Defaults.login_conf, Defaults.instances_conf)        
        # Get instance configurations from configuration files
        instances = {i_name: i_conf for i_name, i_conf in reader.get_instances().items() if i_name in list(instances_num.keys())}
        
        # Group instances with same provider and login --> create a cluster
        cluster_instance_map = dict()
        for iname, iconf in instances.items()
            # Get cluster name
            name = "{}-{}-{}".format(self.cluster_prefix, iconf.provider_id, iconf.login_id)
            # Append the instance to the cluster name
            if name in cluster_names:
                cluster_instance_map[name].add(iname)
            else:
                cluster_instance_map[name] = set(iname)
            
        # Let's create a new cluster or pass if already exists...
        for cluster_name, inames in cluster_instance_map.items():
            



    def stop_nodes(self, node_ids: List[str]):
        pass

    def pause_nodes(self, node_ids: List[str]):
        pass

    def resume_nodes(self, node_ids: List[str]):
        raise NotImplementedError("Not implemented")

    def check_nodes_alive(self, node_ids: List[str]) -> Dict[str, bool]:
        pass

    def get_connection_to_nodes(self, node_ids: List[str], *args, **kwargs) -> Dict[str, SSHClient]:
        pass

    def execute_playbook_in_nodes(self, playbook_path: str,
                                  group_hosts_map: Dict[str, List[str]],
                                  extra_args: Dict[str, str] = None,
                                  group_vars: Dict[str, Dict[str, str]] = None) -> Dict[str, bool]:
        pass
