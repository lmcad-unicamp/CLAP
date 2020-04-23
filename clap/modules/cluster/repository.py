from clap.common.config import Defaults
from clap.common.repository import AbstractEntry, AbstractRepository, RepositoryFactory, check_and_create_table, get_repository_connection

class ClusterData(AbstractEntry):
    def __init__(self, **kwargs):
        cluster_index = 0

        super(ClusterData, self).__init__(**kwargs)

class RepositoryOperations:
    def __init__(self, cluster_repository_path: str, repository_type: str = Defaults.REPOSITORY_TYPE):
        self.repository_path = cluster_repository_path
        self.repository_type = repository_type
        self.repository = RepositoryFactory.get_repository(self.repository_path, self.repository_type)

    def exists_platform_db(self) -> bool:
        return RepositoryFactory.exists_repository(self.repository_path)

    def create_repository(self, exists: str = 'pass') -> AbstractRepository:
        if check_and_create_table(self.repository, 'cluster', exists):
            self.repository.create_element('control', ClusterData())
        return self.repository

    def get_new_cluster_index(self):
        pass