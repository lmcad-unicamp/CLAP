from typing import List, Dict
from paramiko import SSHClient

from clap.common.factory import PlatformFactory
from clap.common.cluster_repository import NodeInfo
from clap.common.utils import log

def start_zabbix_nodes(instance_ids: Dict[str, int]) -> List[NodeInfo]:
    node_module = PlatformFactory.get_module_interface().get_module('node')
    group_module = PlatformFactory.get_module_interface().get_module('group')

    # Return a ist with sucessfully started nodes information [NodeInfo]
    started_nodes = node_module.start_nodes(instance_ids)
    started_node_ids = [node.node_id for node in started_nodes]
    try:
        group_module.add_group_to_node(node_ids=started_node_ids, group='zabbix')
    except Exception as e:
        # Fail adding nodes to group zabbix --> destroy all nodes
        log.error(e)
        node_module.stop_nodes(started_node_ids)
        return []
        
    return started_node_ids