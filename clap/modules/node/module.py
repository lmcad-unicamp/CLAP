from typing import List, Dict
from paramiko import SSHClient

from .interactive import interactive_shell
from clap.common.factory import PlatformFactory
from clap.common.cluster_repository import NodeInfo

def start_nodes(node_ids: Dict[str, int]) -> List[NodeInfo]:
    multi_instance = PlatformFactory.get_instance_api()
    return multi_instance.start_nodes(node_ids)

def list_nodes(node_ids: List[str] = None, tags: Dict[str, str] = None) -> List[NodeInfo]:
    multi_instance = PlatformFactory.get_instance_api()

    if tags:
        nodes = multi_instance.get_nodes_with_tags(tags)
        if node_ids:
            return nodes + multi_instance.get_nodes(node_ids)
        else:
            return nodes
    else:
        return multi_instance.get_nodes(node_ids) if node_ids else multi_instance.get_all_nodes()

def is_alive(node_ids: List[str], tags: Dict[str, str] = None) -> Dict[str, bool]:
    multi_instance = PlatformFactory.get_instance_api()
    node_ids = [node.node_id for node in list_nodes(node_ids=node_ids, tags=tags)]
    return  multi_instance.check_nodes_alive(list(set(node_ids)))

def stop_nodes(node_ids: List[str], tags: Dict[str, str] = None, force: bool = False) -> List[str]:
    multi_instance = PlatformFactory.get_instance_api()
    if not node_ids and not tags:
        raise Exception("No nodes provided")
    node_ids = [node.node_id for node in list_nodes(node_ids=node_ids, tags=tags)]
    if not node_ids:
        raise Exception("No nodes provided")
    return multi_instance.stop_nodes(list(node_ids), force)

def resume_nodes(node_ids: List[str], tags: Dict[str, str] = None) -> List[str]:
    multi_instance = PlatformFactory.get_instance_api()
    if not node_ids and not tags:
        raise Exception("No nodes provided")
    node_ids = [node.node_id for node in list_nodes(node_ids=node_ids, tags=tags)]
    if not node_ids:
        raise Exception("No nodes provided")
    return multi_instance.resume_nodes(list(node_ids))

def pause_nodes(node_ids: List[str], tags: Dict[str, str] = None) -> List[str]:
    multi_instance = PlatformFactory.get_instance_api()
    if not node_ids and not tags:
        raise Exception("No nodes provided")
    node_ids = [node.node_id for node in list_nodes(node_ids=node_ids, tags=tags)]
    if not node_ids:
        raise Exception("No nodes provided")
    return multi_instance.pause_nodes(list(node_ids))

def execute_playbook(playbook_file: str, node_ids: List[str], tags: Dict[str, str] = None, extra_args: Dict[str, str] = None) -> Dict[str, bool]:
    multi_instance = PlatformFactory.get_instance_api()
    if not node_ids and not tags:
        raise Exception("No nodes provided")
    node_ids = [node.node_id for node in list_nodes(node_ids=node_ids, tags=tags)]
    if not node_ids:
        raise Exception("No nodes provided")
    return  multi_instance.execute_playbook_in_nodes(playbook_file, node_ids, extra_args)

def get_ssh_connections(node_ids: List[str], tags: Dict[str, str] = None, *args, **kwargs) -> Dict[str, SSHClient]:
    multi_instance = PlatformFactory.get_instance_api()
    if not node_ids and not tags:
        raise Exception("No nodes provided")
    node_ids = [node.node_id for node in list_nodes(node_ids=node_ids, tags=tags)]
    if not node_ids:
        raise Exception("No nodes provided")
    return multi_instance.get_connection_to_nodes(node_ids, *args, **kwargs)

def connect_to_node(node_id: str):
    # Not the best way...
    if list_nodes([node_id])[0].driver_id == 'ansible':
        get_ssh_connections([node_id], open_shell=True)

    else:
        ssh_client = get_ssh_connections([node_id])[node_id]
        if not ssh_client:
            raise Exception("Connection to `{}` was unsuccessful. "
                            "Check you internet connection or if the node is up and alive".format(node_id))
        channel = ssh_client.get_transport().open_session()
        channel.get_pty()
        channel.invoke_shell()
        interactive_shell(channel)
        ssh_client.close()
