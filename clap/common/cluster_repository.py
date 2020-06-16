import clap.common
import time
import datetime
from datetime import datetime
from typing import List, Union

from clap.common.utils import float_time_to_string
from clap.common.repository import AbstractEntry, AbstractRepository, RepositoryFactory, get_repository_connection


class PlatformControlInfo(AbstractEntry):
    """ This class holds control information used to create nodes and cluster in the repository (database).
    It holds an **incremental index** to be used to create such elements.
    """

    def __init__(self, *args, **kwargs):
        self.control_idx = 0
        self.node_idx = 0
        self.cluster_idx = 0
        super(PlatformControlInfo, self).__init__(*args, **kwargs)

class ClusterInfo(AbstractEntry):
    """ This class holds information about a cluster. A cluster is considered a set of nodes with the same provider and login configurations
    Each cluster is unique and is composed by the following elements:
        * cluster_id: The unique identification of the cluster, used to perform operations across modules and instance interfaces (auto-generated)
        * provider_id: Id of the provider configuration used
        * login_id: Id of the login configuration used 
        * driver_id: Id of the driver in-use
        * creation_time: Date of cluster's creation
        * extra: Optional extra information
    """
    def __init__(self, **kwargs):
        self.cluster_id = None
        self.eclust_cluster_name = None
        self.provider_id = None
        self.login_id = None
        self.provider_conf = None
        self.login_conf = None
        self.driver_id = None
        self.creation_time = time.time()
        self.extra = None
        super(ClusterInfo, self).__init__(**kwargs)

    def __repr__(self):
        return 'Cluster(id=`{}`, provider=`{}`, driver=`{}`, creation_time=`{}`)'.format(
            self.cluster_id, self.provider_id, self.login_id, float_time_to_string(self.creation_time))

class NodeInfo(AbstractEntry):
    """ This class holds information about a node that is stored in the CLAP's repository and used by several interfaces
    Each node is unique and is composed by the following elements:
        * node_id: The unique identification of the node, used to perform operations across modules and interfaces
        * cluster_id: ID of the cluster that this node is attached to. The cluster defines a unique login and provider configurations.
        * instance_type: Type of the instantiated node (equivalent to the instances configuration file)
        * creation_time: Date of node's creation
        * update_time: Date of the last node's update
        * ip: IP address used to connect to this node (address used to perform SSH)
        * status: Last known status of the node (see PlatformCodes)
        * tags: Dictionary of tags for node identification. The key is the tag name and the value is a set of tag values
        * groups: Dictionary with groups which the nodes belongs to. The key is the group name and the value is additional group's information.
        * driver_id: ID of the in-use driver that controls this node
        * instance_id: ID of the instance at the cloud provider (cloud's instance id)
        * lifecycle: Instance lifecycle. It can be 'spot' or 'on-demand'
        * extra: Additional instance information
    """

    def __init__(self, **kwargs):
        self.node_id = None
        self.cluster_id = None
        self.instance_type = None
        self.creation_time = time.time()
        self.update_time = self.creation_time
        self.ip = None
        self.status = None
        self.tags = dict()
        self.groups = dict()
        self.roles = list()
        self.driver_id = None
        self.instance_id = None
        self.extra = None
        self.lifecycle = None
        super(NodeInfo, self).__init__(**kwargs)

    def __repr__(self):
        return 'Node(id=`{}`, type=`{}`, status=`{}`, public_ip=`{}`, groups=`{}`, tags=`{}`, roles=`{}`, last_update=`{}`'.format(
            self.node_id, self.instance_type, self.status, self.ip,
            ', '.join(list(self.groups.keys())), '; '.join(["{}={}".format(k, ','.join(v)) for k, v in self.tags.items()]),
            ', '.join(sorted(self.roles)), float_time_to_string(self.update_time))

class RepositoryOperations:
    def __init__(self, platform_repository: str, repository_type: str, node_prefix = 'node'):
        self.platform_db_name = platform_repository
        self.repository_type = repository_type
        self.node_prefix = node_prefix
        self.repository = RepositoryFactory.get_repository(self.platform_db_name, self.repository_type)

    def _get_platform_repository(self) -> AbstractRepository:
        """ Get the platform repository connection

        :return: The platform database connection
        :rtype: AbstractRepository
        """
        return self.repository

    def exists_platform_db(self) -> bool:
        """ Check if the platform database exists

        :return: A boolean representing the existence of the platform database
        :rtype: bool
        """
        return RepositoryFactory.exists_repository(self.platform_db_name)

    def create_platform_db(self, exists: str = 'pass'):
        """ Creates the platform Database

        :param exists: This parameter can be:
        * 'pass' (default): will do nothing if the platform database tables already exists
        * 'fail': will raise `TableAlreadyExists` exception
        * 'overwrite': will drop and create a new table, if it already exists
        :return: A open repository connection
        :rtype: AbstractRepository
        """

        with get_repository_connection(self._get_platform_repository()) as repository:
            if clap.common.repository.check_and_create_table(repository, 'control', exists):
                repository.create_element('control', PlatformControlInfo())
            clap.common.repository.check_and_create_table(repository, 'clusters', exists)
            clap.common.repository.check_and_create_table(repository, 'nodes', exists)

    def new_cluster(self, cluster_id: str, provider_id: str, login_id: str, driver_id: str, extra: dict = None) -> ClusterInfo:
        """ Create a new cluster in the repository

        :param cluster_id: ID of the cluster to create (usually driver_id-provider_id-login_id)
        :type cluster_id: str
        :param provider_id: Name of the provider configuration (must match the provider ID in the provider's configuration file)
        :type provider_id: str
        :param login_id: Name of the login configuration (must match the login ID in the login's configuration file)
        :type login_id: str
        :param driver_id: ID of the in-use driver
        :type driver_id: str
        :param extra: Additional extra parameters to cluster
        :type extra: dict
        :return: A new created cluster in the repository
        :rtype: ClusterInfo
        """
        with get_repository_connection(self.repository) as repository:
            cluster_data = ClusterInfo(
                cluster_id=cluster_id,
                provider_id=provider_id,
                login_id=login_id,
                driver_id=driver_id,
                extra=extra if extra else {}
            )

            clap.common.repository.generic_write_entry(cluster_data, repository, 'clusters', create=True)

            return cluster_data
    
    def new_node(self, cluster_id: str, instance_type: str, status: str, driver_id: str, ip: str = None, 
                 instance_id: str = None, tags: dict = None, groups: dict = None, extra: dict = None, 
                 lifecycle: str = 'on-demand') -> NodeInfo:
        """ Create a new node in the repository

        :param cluster_id: Cluster which the node will be associated
        :type cluster_id: str
        :param instance_type: Type of the instance to be created (must match the instance ID from the instance configuration file)
        :type instance_type: str
        :param status: Status of the node (see PlatformCodes)
        :type status: str
        :param driver_id: ID of the in-use driver
        :type driver_id: str
        :param ip: IP of the node
        :type ip: str
        :param instance_id: ID of the instance from the provider
        :type instance_id: str
        :param tags: Additional tags from instance
        :type tags: dict
        :param groups: Groups which the nodes belong to. It is a dictionary, keys are group names and values are optional groups additional variables
        :type groups: dict
        :param extra: Additional extra parameters to the node
        :type extra: dict
        :param lifecycle: Cloud's instance lifecycle. On-demand or spot
        :type lifecycle: str
        :return: A new created node in the repository
        :rtype: NodeInfo
        """

        with get_repository_connection(self.repository) as repository:
            control = next(iter(clap.common.repository.generic_read_entry(PlatformControlInfo, repository, 'control')))
            index = control.node_idx
            control.node_idx += 1
            clap.common.repository.generic_write_entry(control, repository, 'control', create=False, control_idx=0)

            node_data = NodeInfo(
                node_id="{}-{}".format(self.node_prefix, index),
                cluster_id=cluster_id,
                instance_type=instance_type,
                status=status,
                driver_id=driver_id,
                ip=ip,
                instance_id=instance_id,
                tags=tags if tags else {},
                groups=groups if groups else {},
                extra=extra if extra else {},
                lifecycle=lifecycle
            )

            clap.common.repository.generic_write_entry(node_data, repository, 'nodes', create=True)

            return node_data

    def update_cluster(self, cluster: ClusterInfo):
        """ Update a cluster information in the repository

        :param cluster: The cluster infromation to be updated
        :type cluster: ClusterInfo
        """
        with get_repository_connection(self._get_platform_repository()) as repository:
            clap.common.repository.generic_write_entry(cluster, repository, 'clusters', create=False, cluster_id=cluster.cluster_id)

    def update_node(self, node: NodeInfo):
        """ Update a node information in the repository

        :param cluster: The node infromation to be updated
        :type cluster: NodeInfo
        """
        with get_repository_connection(self._get_platform_repository()) as repository:
            clap.common.repository.generic_write_entry(node, repository, 'nodes', create=False, node_id=node.node_id)

    def get_clusters(self, cluster_ids: Union[str, List[str]]) -> List[ClusterInfo]:
        """ Given a list with cluster ids, it returns all the Cluster Information that matches the Ids in the repository

        :param cluster_ids: List of cluster ids to be queried
        :type cluster_ids: List[str]
        :return: Matched cluster information
        :rtype: List[ClusterInfo]
        """
        if type(cluster_ids) is str:
            cluster_ids = [cluster_ids]

        with get_repository_connection(self._get_platform_repository()) as repository:
            clusters = []
            for cluster_id in cluster_ids:
                clusters += clap.common.repository.generic_read_entry(ClusterInfo, repository, 'clusters', cluster_id=cluster_id)
            return clusters

    def get_all_clusters(self) -> List[ClusterInfo]:
        """ Get the information of all created cluster in the repository

        :return: List with the information of all created cluster
        :rtype: List[ClusterInfo]
        """
        with get_repository_connection(self._get_platform_repository()) as repository:
            return clap.common.repository.generic_read_entry(ClusterInfo, repository, 'clusters')

    def get_nodes(self, node_ids: Union[str, List[str]]) -> List[NodeInfo]:
        """ Given a list with node ids, it returns all the Node Information that matches the ids in the repository

        :param node_ids: List of node ids to be queried
        :type node_ids: List[str]
        :return: Matched nodes information
        :rtype: List[NodeInfo]
        """
        if type(node_ids) is str:
            node_ids = [node_ids]

        with get_repository_connection(self._get_platform_repository()) as repository:
            nodes = []
            for node_id in node_ids:
                nodes += clap.common.repository.generic_read_entry(NodeInfo, repository, 'nodes', node_id=node_id)
            return nodes

    def get_all_nodes(self) -> List[NodeInfo]:
        """ Get the information of all created nodes in the repository

        :return: List with the information of all created nodes
        :rtype: List[NodeInfo]
        """
        with get_repository_connection(self._get_platform_repository()) as repository:
            return clap.common.repository.generic_read_entry(NodeInfo, repository, 'nodes')

    def get_nodes_from_cluster(self, cluster_id: str) -> List[NodeInfo]:
        """ Given a list of cluster ids, return all nodes in cluster that matches the ids passed in the repository

        :param cluster_id: Id of the cluster
        :type cluster_id: str
        :return: All the nodes that matches the cluster ids passed
        :rtype: List[NodeInfo]
        """
        with get_repository_connection(self._get_platform_repository()) as repository:
            return clap.common.repository.generic_read_entry(NodeInfo, repository, 'nodes', cluster_id=cluster_id)

    def remove_cluster(self, cluster_id: str):
        """ Remove a cluster from repository based on it's ID
        
        :param cluster_id: ID of the cluster to be removed
        :type cluster_id: str
        """
        with get_repository_connection(self._get_platform_repository()) as repository:
            repository.drop_elements('clusters', cluster_id=cluster_id)
    
    def remove_node(self, node_id: str):
        """ Remove a node from repository based on it's ID
        
        :param node_id: ID of the node to be removed
        :type node_id: str
        """
        with get_repository_connection(self._get_platform_repository()) as repository:
            repository.drop_elements('nodes', node_id=node_id)
