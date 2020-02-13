from abc import abstractmethod
from typing import List, Dict
from paramiko import SSHClient
from clap.common.cluster_repository import RepositoryOperations, NodeInfo


class AbstractInstanceInterface:
    """ Abstract class implementing the interface between the driver and the clap objects.
    The interface is responsible for create and manage clusters and nodes entries in the clap platform repository.
    Clap objects interact with the driver interface instead of the driver directly.

    """

    __interface_id__ = 'InterfaceID'
    __interface_version__ = '0.1.0'

    def __init__(self, repository_operator: RepositoryOperations):
        """
        :param repository_operator: Repository used to create and manage clusters and nodes information
        :type repository_operator: RepositoryOperations
        """
        self.repository_operator = repository_operator

    @abstractmethod
    def start_nodes(self, instances_num: Dict[str, int]) -> List[NodeInfo]:
        raise NotImplementedError("Must implement this method in derived classes!")

    @abstractmethod
    def stop_nodes(self, node_ids: List[str]):
        raise NotImplementedError("Must implement this method in derived classes!")

    @abstractmethod
    def pause_nodes(self, node_ids: List[str]):
        pass

    @abstractmethod
    def resume_nodes(self, node_ids: List[str]):
        pass

    @abstractmethod
    def check_nodes_alive(self, node_ids: List[str]) -> Dict[str, bool]:
        raise NotImplementedError("Must implement this method in derived classes!")

    @abstractmethod
    def get_connection_to_nodes(self, node_ids: List[str], *args, **kwargs) -> Dict[str, SSHClient]:
        raise NotImplementedError("Must implement this method in derived classes!")

    @abstractmethod
    def execute_playbook_in_nodes(self, node_ids: List[str], playbook_path: str, *args, **kwargs) -> Dict[str, bool]:
        raise NotImplementedError("Must implement this method in derived classes!")


class Codes:
    """ Status codes for nodes
    """
    NODE_STATUS_INIT = 'initialized'
    NODE_STATUS_UNREACHABLE = 'unreachable'
    NODE_STATUS_REACHABLE = 'reachable'
    NODE_STATUS_PAUSED = 'paused'
    NODE_STATUS_STOPPED = 'stopped'
