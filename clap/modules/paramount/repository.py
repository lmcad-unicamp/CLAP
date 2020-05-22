import os
import time

from typing import List

from clap.common.config import Defaults
from clap.common.repository import (AbstractEntry, AbstractRepository, RepositoryFactory, 
                                    check_and_create_table, get_repository_connection, generic_read_entry,
                                    generic_write_entry)
from clap.common.utils import log, path_extend
from .conf import ParamountClusterDefaults, ParamountState

class ParamountClusterControlData(AbstractEntry):
    def __init__(self, **kwargs):
        self.control = 0
        self.cluster_index = 0
        super(ParamountClusterControlData, self).__init__(**kwargs)

class ParamountClusterData(AbstractEntry):
    def __init__(self, **kwargs):
        self.paramount_id = None
        self.application_name = None
        self.cluster_id = None
        self.node_type = None
        self.node_counts = None
        self.node_executeds = None
        self.node_scripts_executeds = None
        self.execution_dir = None
        self.is_setup = False
        self.is_installed = False
        self.is_compiled = False
        self.use_shared_fs = False
        super(ParamountClusterData, self).__init__(**kwargs)

class ParamountClusterRepositoryOperations:
    def __init__(self, repository_name: str = 'paramount_cluster.json', repository_type: str = Defaults.REPOSITORY_TYPE, paramount_prefix = 'paramount'):
        repository_dir = ParamountClusterDefaults.PARAMOUNT_CLUSTER_REPOSITORY_DIR

        if os.path.exists(repository_dir):
            if os.path.isfile(repository_dir):
                raise NotADirectoryError("File `{}` is not a directory".format(repository_dir))
        else:
            os.makedirs(repository_dir)

        self.repository_path = path_extend(repository_dir, repository_name)
        self.repository_type = repository_type
        self.repository = RepositoryFactory.get_repository(self.repository_path, self.repository_type)
        self.create_repository()
        self.paramount_prefix = paramount_prefix

    def exists_platform_db(self) -> bool:
        return RepositoryFactory.exists_repository(self.repository_path)

    def create_repository(self, exists: str = 'pass'):
        with get_repository_connection(self.repository) as repository:
            if check_and_create_table(repository, 'control', exists):
                repository.create_element('control', ParamountClusterControlData())
            check_and_create_table(repository, 'paramount', exists)

    def new_paramount(self, application_name: str, cluster_id: str, node_type: str, node_counts: List[int]):
        with get_repository_connection(self.repository) as repository:
            control = next(iter(generic_read_entry(ParamountClusterControlData, repository, 'control')))
            index = control.cluster_index
            control.cluster_index += 1
            generic_write_entry(control, repository, 'control', False, control=0)

            node_counts = list(reversed(sorted(node_counts)))
            node_executeds = {count: ParamountState.NOT_RUN for count in node_counts}

            paramount_cluster = ParamountClusterData(
                paramount_id="{}-{}".format(self.paramount_prefix, index), 
                application_name=application_name,
                cluster_id=cluster_id,
                node_type=node_type,
                node_counts=node_counts,
                node_executeds=node_executeds
            )
            generic_write_entry(paramount_cluster, repository, 'paramount', create=True)
            return paramount_cluster

    def get_paramount(self, paramount_id: str) -> ParamountClusterData:
        with get_repository_connection(self.repository) as repository:
            paramount = next(iter(generic_read_entry(ParamountClusterData, repository, 'paramount', paramount_id=paramount_id)), None)
            if not paramount:
                raise Exception("Invalid paramount: `{}`".format(paramount_id))
            return paramount

    def get_all_paramount(self) -> List[ParamountClusterData]:
        with get_repository_connection(self.repository) as repository:
            return generic_read_entry(ParamountClusterData, repository, 'paramount')

    def update_paramount(self, paramount_cluster_data: ParamountClusterData) -> str:
        with get_repository_connection(self.repository) as repository:
            generic_write_entry(paramount_cluster_data, repository, 'paramount', create=False, 
                paramount_id=paramount_cluster_data.paramount_id)

    def remove_paramount(self, paramount_id: str) -> str:
        with get_repository_connection(self.repository) as repository:
            repository.drop_elements('paramount', paramount_id=paramount_id)
        return paramount_id