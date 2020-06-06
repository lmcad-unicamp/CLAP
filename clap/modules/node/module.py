from typing import List, Dict
from paramiko import SSHClient

from .interactive import interactive_shell
from clap.common.factory import PlatformFactory
from clap.common.cluster_repository import NodeInfo

def start_nodes(instance_ids: Dict[str, int]) -> List[NodeInfo]:
    """ Start instances based on the instance configuration values

    :param instance_ids: Dictionary containing the instance name as key and number of instances as value. The instance name must match the instance name at instances configuration file
    :type instance_ids: Dict[str, int]
    :return: A list of created nodes 
    :rtype: List[NodeInfo]
    """
    multi_instance = PlatformFactory.get_instance_api()
    return multi_instance.start_nodes(instance_ids)

def list_nodes(node_ids: List[str] = None, tags: Dict[str, str] = None) -> List[NodeInfo]:
    """ Get the information of nodes from the node repository

    :param node_ids: List of node ids to get the node information. If no node_ids and no tags are informed, all nodes are retrieved
    :type node_ids: List[str]
    :param tags: Key-valued dictionary informing the nodes to get, matching the tags informed. The nodes containing all tag values are retieved.
    :type tags: Dict[str, str]
    :return: A list with nodes information 
    :rtype: List[NodeInfo]
    """
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
    """ Check if nodes are alive, based on their node ids. The nodes are alive if a successfully SSH connection is performed

    :param node_ids: List of node ids to check for aliveness.
    :type node_ids: List[str]
    :param tags: Optionally check nodes that match the tags informed
    :type tags: Dict[str, str]
    :return: A dictionary telling which nodes are alive. The dictionary keys correspond to the node id and the value is a boolean that is true if node is alive or false otherwise. 
    :rtype: Dict[str, bool]
    """
    multi_instance = PlatformFactory.get_instance_api()
    node_ids = [node.node_id for node in list_nodes(node_ids=node_ids, tags=tags)]
    return  multi_instance.check_nodes_alive(list(set(node_ids)))

def stop_nodes(node_ids: List[str], tags: Dict[str, str] = None, force: bool = True) -> List[str]:
    """ Stop started nodes based on their node ids

    :param node_ids: List of node ids to stop
    :type node_ids: List[str]
    :param tags: Optionally stop nodes that match the tags informed
    :type tags: Dict[str, str]
    :return: A list of stopped nodes 
    :rtype: List[str]
    """      

    multi_instance = PlatformFactory.get_instance_api()
    if not node_ids and not tags:
        raise Exception("No nodes provided")
    node_ids = [node.node_id for node in list_nodes(node_ids=node_ids, tags=tags)]
    if not node_ids:
        raise Exception("No nodes provided")
    return multi_instance.stop_nodes(list(node_ids), force)

def resume_nodes(node_ids: List[str], tags: Dict[str, str] = None) -> List[str]:
    """ Resume stopped nodes based on their node ids

    :param node_ids: List of node ids to resume
    :type node_ids: List[str]
    :param tags: Optionally resume nodes that match the tags informed
    :type tags: Dict[str, str]
    :return: A list of resumed nodes 
    :rtype: List[str]
    """      
    multi_instance = PlatformFactory.get_instance_api()
    if not node_ids and not tags:
        raise Exception("No nodes provided")
    node_ids = [node.node_id for node in list_nodes(node_ids=node_ids, tags=tags)]
    if not node_ids:
        raise Exception("No nodes provided")
    return multi_instance.resume_nodes(list(node_ids))

def pause_nodes(node_ids: List[str], tags: Dict[str, str] = None) -> List[str]:
    """ Pause nodes based on their node ids

    :param node_ids: List of node ids to pause
    :type node_ids: List[str]
    :param tags: Optionally pause nodes that match the tags informed
    :type tags: Dict[str, str]
    :return: A list of paused nodes 
    :rtype: List[str]
    """    
    multi_instance = PlatformFactory.get_instance_api()
    if not node_ids and not tags:
        raise Exception("No nodes provided")
    node_ids = [node.node_id for node in list_nodes(node_ids=node_ids, tags=tags)]
    if not node_ids:
        raise Exception("No nodes provided")
    return multi_instance.pause_nodes(list(node_ids))

def execute_playbook(playbook_file: str, node_ids: List[str], tags: Dict[str, str] = None, extra_args: Dict[str, str] = None) -> Dict[str, bool]:
    """ Execute an Ansible Playbook at nodes based on their node ids.

    :param playbook_file: Path of the Ansible playbook to execute.
    :type playbook_file: str
    :param node_ids: List of node ids to execute the playbook
    :type node_ids: List[str]
    :param tags: Optionally execute playbook at nodes that match the tags informed
    :type tags: Dict[str, str]
    :param extra_args: Key-valued dictionary containing the extra variables to be passed to the playbook. Both key and value are strings
    :type extra_args: Dict[str, str]
    :return: A dictionary telling which nodes have sucessfully executed the playbook. The dictionary keys correspond to the node id and the value is a boolean that is true if node successfully executed the playbook or false otherwise. 
    :rtype: Dict[str, bool]
    """
    multi_instance = PlatformFactory.get_instance_api()
    if not node_ids and not tags:
        raise Exception("No nodes provided")
    node_ids = [node.node_id for node in list_nodes(node_ids=node_ids, tags=tags)]
    if not node_ids:
        raise Exception("No nodes provided")
    return  multi_instance.execute_playbook_in_nodes(playbook_file, node_ids, extra_args)

def get_ssh_connections(node_ids: List[str], tags: Dict[str, str] = None, *args, **kwargs) -> Dict[str, SSHClient]:
    """ Get a SSH client to nodes.

    :param node_ids: List of node ids to get the clients.
    :type node_ids: List[str]
    :param tags: Optionally get connections to nodes that match the tags informed
    :type tags: Dict[str, str]
    :return: A dictionary with the SSH clients. The key is the node id and each value is the SSH client (from Paramiko library)
    :rtype: Dict[str, Paramiko.SSHClient]
    """
    multi_instance = PlatformFactory.get_instance_api()
    if not node_ids and not tags:
        raise Exception("No nodes provided")
    node_ids = [node.node_id for node in list_nodes(node_ids=node_ids, tags=tags)]
    if not node_ids:
        raise Exception("No nodes provided")
    return multi_instance.get_connection_to_nodes(node_ids, *args, **kwargs)

def connect_to_node(node_id: str):
    """ Open a SSH shell to a node based on it node id
    """
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
