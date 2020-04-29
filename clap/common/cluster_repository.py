import clap.common
import time
import datetime
from datetime import datetime
from typing import List

from clap.common.utils import float_time_to_string
from clap.common.repository import AbstractEntry, AbstractRepository, RepositoryFactory, get_repository_connection


class PlatformControlInfo(AbstractEntry):
    """ This class holds control information used to create nodes and cluster in the repository (database).
    It holds an incremental index to be used when creating such elements.
    """

    def __init__(self, *args, **kwargs):
        self.control_idx = 0
        self.node_idx = 0
        self.cluster_idx = 0
        super(PlatformControlInfo, self).__init__(*args, **kwargs)


class ClusterInfo(AbstractEntry):
    """ This class holds information about a cluster that is stored in the repository and used by several interfaces
    Each cluster is unique and is composed by the following elements:
        * cluster_id: The unique identification of the cluster, used to perform operations across modules and instance interfaces
        * cluster_name: The name of the cluster used by the driver object that controls this cluster
        * cloud: The cluster (or cloud) provider that this cluster is attached (e.g., aws, azure, ...)
        * keypair: The name of the keypair used to connect to the machines created in this cluster
        * region: The avaliability zone that this cluster was created
        * template: Name of the template that was used to create this cluster
        * driver_id: ID of the driver that controls this cluster
        * driver_version: Version of the driver used by this cluster
        * tags: Additional user tags for cluster identification

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
    """ This class holds information about a node that is stored in the repository and used by several interfaces
    Each node is unique and is composed by the following elements:
        * node_id: The unique identification of the node, used to perform operations across modules and instance interfaces
        * node_name: The name of the node used by the driver object that controls it
        * cluster_id: ID of the cluster that this node is attached to
        * flavor: Instance flavor (e.g., t2.micro in aws)
        * status: Last known status of the node (see PlatformCodes)
        * ip: IP address used to connect to this node (address used to perform SSH)
        * driver_id: ID of the driver that controls this node
        * driver_version: Version of the driver used by this node
        * keypair: The name of the keypair used to connect to the machines created in the node cluster
        * key: The private key file used to perform SSH and connect to machines
        * tags: Additional user tags for node identification

    """

    def __init__(self, **kwargs):
        self.node_id = None
        self.cluster_id = None
        self.eclust_node_name = None
        self.instance_type = None
        self.provider_id = None
        self.login_id = None
        self.instance_conf = None
        self.creation_time = time.time()
        self.update_time = self.creation_time
        self.ip = None
        self.status = None
        self.tags = dict()
        self.groups = dict()
        self.driver_id = None
        self.extra = None
        super(NodeInfo, self).__init__(**kwargs)

    def __repr__(self):
        return 'Node(id=`{}`, type=`{}`, status=`{}`, public_ip=`{}`, groups=`{}`, tags=`{}`, last_update=`{}`'.format(
            self.node_id, self.instance_type, self.status, self.ip,
            ', '.join(list(self.groups.keys())), '; '.join(["{}={}".format(k, ','.join(v)) for k, v in self.tags.items()]),
            float_time_to_string(self.update_time))


class RepositoryOperations:
    def __init__(self, platform_repository: str, repository_type: str):
        self.platform_db_name = platform_repository
        self.repository_type = repository_type
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

    def get_and_increment_node_index(self) -> int:
        with get_repository_connection(self._get_platform_repository()) as repository:
            control = next(iter(clap.common.repository.generic_read_entry(PlatformControlInfo, repository, 'control')))
            index = control.node_idx
            control.node_idx += 1
            clap.common.repository.generic_write_entry(control, repository, 'control', False)
            return index
    
    def get_and_increment_cluster_index(self) -> int:
        with get_repository_connection(self._get_platform_repository()) as repository:
            control = next(iter(clap.common.repository.generic_read_entry(PlatformControlInfo, repository, 'control')))
            index = control.cluster_idx
            control.cluster_idx += 1
            clap.common.repository.generic_write_entry(control, repository, 'control', False)
            return index

    def write_cluster_info(self, cluster: ClusterInfo, create: bool = False):
        """ Helper function to write Cluster information on the correct table in the repository

        :param cluster: Cluster information to be written
        :type cluster: ClusterInfo
        :param create: If true, create a new element, else update the one with same id
        :type create: str
        :return: None
        """
        with get_repository_connection(self._get_platform_repository()) as repository:
            clap.common.repository.generic_write_entry(cluster, repository, 'clusters', create,
                                                    cluster_id=cluster.cluster_id)

    def _read_clusters_info(self, **where) -> List[ClusterInfo]:
        """ Helper function to read Cluster information from the correct table in the repository

        :param where: Dictionary of criterion to be matched when retrieving elements (e.g., {'cluster.id' == 'xxx'})
        :return: List of cluster matching the criterion passed
        :rtype: List[ClusterInfo]
        """
        with get_repository_connection(self._get_platform_repository()) as repository:
            return clap.common.repository.generic_read_entry(ClusterInfo, repository, 'clusters',
                                                            **where)

    def write_node_info(self, node: NodeInfo, create: bool = False):
        """ Helper function to write Node information on the correct table in the repository

        :param node: node information to be written
        :type node: NodeInfo
        :param create: If true, create a new element, else update the one with same id
        :type create: str
        :return: None
        """
        with get_repository_connection(self._get_platform_repository()) as repository:
            clap.common.repository.generic_write_entry(node, repository, 'nodes', create,
                                                   node_id=node.node_id)

    def _read_nodes_info(self, **where) -> List[NodeInfo]:
        """ Helper function to read Nodes information from the correct table in the repository

        :param where: Dictionary of criterion to be matched when retrieving elements (e.g., {'node.id' == 'xxx'})
        :return: List of nodes matching the criterion passed
        :rtype: List[NodeInfo]
        """
        with get_repository_connection(self._get_platform_repository()) as repository:
            return clap.common.repository.generic_read_entry(NodeInfo, repository, 'nodes',
                                                            **where)

    def _delete_clusters_info(self, **where):
        with get_repository_connection(self._get_platform_repository()) as repository:
            repository.drop_elements('clusters', **where)

    def _delete_nodes_info(self, **where):
        with get_repository_connection(self._get_platform_repository()) as repository:
            repository.drop_elements('nodes', **where)

    def get_cluster(self, cluster_id: str) -> ClusterInfo:
        return next(iter(self.get_clusters([cluster_id])), None)

    def get_clusters(self, cluster_ids: List[str]) -> List[ClusterInfo]:
        """ Given a list with cluster ids, it returns all the Cluster Information that matches the Ids in the repository

        :param cluster_ids: List of cluster ids to be queried
        :type cluster_ids: List[str]
        :return: Matched cluster information
        :rtype: List[ClusterInfo]
        """

        clusters = [self._read_clusters_info(cluster_id=cluster_id) for cluster_id in cluster_ids]
        return [cluster for cluster_objs in clusters for cluster in cluster_objs]

    def get_all_clusters(self) -> List[ClusterInfo]:
        """ Get the information of all created cluster in the repository

        :return: List with the information of all created cluster
        :rtype: List[ClusterInfo]
        """
        return self._read_clusters_info()

    def remove_cluster(self, cluster_id: str):
        self._delete_clusters_info(cluster_id=cluster_id)

    def get_node(self, node_id):
        return next(iter(self.get_nodes([node_id])))

    def get_nodes(self, node_ids: List[str]) -> List[NodeInfo]:
        """ Given a list with node ids, it returns all the Node Information that matches the ids in the repository

        :param node_ids: List of node ids to be queried
        :type node_ids: List[str]
        :return: Matched nodes information
        :rtype: List[NodeInfo]
        """
        nodes = [self._read_nodes_info(node_id=node_id) for node_id in node_ids]
        return [node for node_obj in nodes for node in node_obj]

    def get_all_nodes(self) -> List[NodeInfo]:
        """ Get the information of all created nodes in the repository

        :return: List with the information of all created nodes
        :rtype: List[NodeInfo]
        """
        return self._read_nodes_info()

    def get_nodes_from_cluster(self, cluster_id: str) -> List[NodeInfo]:
        """ Given a list of cluster ids, return all nodes in cluster that matches the ids passed in the repository

        :param cluster_id: Id of the cluster
        :type cluster_id: str
        :return: All the nodes that matches the cluster ids passed
        :rtype: List[NodeInfo]
        """

        return self._read_nodes_info(cluster_id=cluster_id)

    def remove_node(self, node_id: str):
        self._delete_nodes_info(node_id=node_id)