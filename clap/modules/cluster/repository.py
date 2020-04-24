import os

from clap.common.config import Defaults
from clap.common.repository import (AbstractEntry, AbstractRepository, RepositoryFactory, 
                                    check_and_create_table, get_repository_connection, generic_read_entry,
                                    generic_write_entry)
from clap.common.utils import log, path_extend

class ClusterData(AbstractEntry):
    def __init__(self, **kwargs):
        self.control = 0
        self.cluster_index = 0
        super(ClusterData, self).__init__(**kwargs)

class ClusterRepositoryOperations:
    def __init__(self, repository_name: str = 'cluster.db', repository_dir: str = 'cluster', repository_type: str = Defaults.REPOSITORY_TYPE):
        repository_dir = path_extend(Defaults.modules_data, repository_dir)

        if os.path.exists(repository_dir):
            if os.path.isfile(repository_dir):
                raise NotADirectoryError("File `{}` is not a directory".format(repository_dir))
        else:
            os.mkdir(repository_dir)

        self.repository_path = path_extend(repository_dir, repository_name)
        self.repository_type = repository_type
        self.repository = RepositoryFactory.get_repository(self.repository_path, self.repository_type)
        self.create_repository()

    def exists_platform_db(self) -> bool:
        return RepositoryFactory.exists_repository(self.repository_path)

    def create_repository(self, exists: str = 'pass'):
        with get_repository_connection(self.repository) as repository:
            if check_and_create_table(self.repository, 'control', exists):
                repository.create_element('control', ClusterData())

    def get_new_cluster_index(self):
        with get_repository_connection(self.repository) as repository:
            control = next(iter(generic_read_entry(ClusterData, repository, 'control')))
            index = control.cluster_index
            control.cluster_index += 1
            generic_write_entry(control, repository, 'control', False, control=0)
            return index