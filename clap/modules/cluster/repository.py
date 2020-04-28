import os
import time

from typing import List

from clap.common.config import Defaults
from clap.common.repository import (AbstractEntry, AbstractRepository, RepositoryFactory, 
                                    check_and_create_table, get_repository_connection, generic_read_entry,
                                    generic_write_entry)
from clap.common.utils import log, path_extend
from .conf import ClusterDefaults

class ClusterControlData(AbstractEntry):
    def __init__(self, **kwargs):
        self.control = 0
        self.cluster_index = 0
        super(ClusterControlData, self).__init__(**kwargs)

class ClusterData(AbstractEntry):
    def __init__(self, **kwargs):
        self.cluster_id = None
        self.cluster_name = None
        self.creation_time = time.time()
        self.update_time = self.creation_time
        self.cluster_config = None
        self.cluster_state = None
        super(ClusterData, self).__init__(**kwargs)

class ClusterRepositoryOperations:
    def __init__(self, repository_name: str = 'cluster.db', repository_type: str = Defaults.REPOSITORY_TYPE, cluster_prefix = 'cluster'):
        repository_dir = ClusterDefaults.CLUSTER_REPOSITORY_DIR

        if os.path.exists(repository_dir):
            if os.path.isfile(repository_dir):
                raise NotADirectoryError("File `{}` is not a directory".format(repository_dir))
        else:
            os.mkdir(repository_dir)

        self.repository_path = path_extend(repository_dir, repository_name)
        self.repository_type = repository_type
        self.repository = RepositoryFactory.get_repository(self.repository_path, self.repository_type)
        self.create_repository()
        self.cluster_prefix = cluster_prefix

    def exists_platform_db(self) -> bool:
        return RepositoryFactory.exists_repository(self.repository_path)

    def create_repository(self, exists: str = 'pass'):
        with get_repository_connection(self.repository) as repository:
            if check_and_create_table(self.repository, 'control', exists):
                repository.create_element('control', ClusterControlData())
            check_and_create_table(self.repository, 'clusters', exists)

    def new_cluster(self, cluster_name, cluster_config, state: str = 'running') -> ClusterData:
        with get_repository_connection(self.repository) as repository:
            control = next(iter(generic_read_entry(ClusterControlData, repository, 'control')))
            index = control.cluster_index
            control.cluster_index += 1
            generic_write_entry(control, repository, 'control', False, control=0)

            cluster_data = ClusterData(
                cluster_id="{}-{}".format(self.cluster_prefix, index),
                cluster_name=cluster_name,
                cluster_config=cluster_config,
                cluster_state=state
            )

            generic_write_entry(cluster_data, repository, 'clusters', create=True)

            return cluster_data

    def get_cluster(self, cluster_id: str) -> ClusterData:
        with get_repository_connection(self.repository) as repository:
            return next(iter(generic_read_entry(ClusterData, repository, 'clusters', cluster_id=cluster_id)), None)

    def get_all_clusters(self) -> List[ClusterData]:
        with get_repository_connection(self.repository) as repository:
            return generic_read_entry(ClusterData, repository, 'clusters')

    def update_cluster(self, cluster_data: ClusterData) -> str:
        with get_repository_connection(self.repository) as repository:
            generic_write_entry(cluster_data, repository, 'clusters', create=False, cluster_id=cluster_data.cluster_id)

    def remove_cluster(self, cluster_id) -> str:
        with get_repository_connection(self.repository) as repository:
            repository.drop_elements('clusters', cluster_id=cluster_id)
        return cluster_id