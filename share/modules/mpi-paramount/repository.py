
import os
import time
from clap.common.repository import (AbstractEntry, AbstractRepository, RepositoryFactory, 
                                    check_and_create_table, get_repository_connection, generic_read_entry,
                                    generic_write_entry)
from clap.common.utils import log, path_extend
from clap.common.config import Defaults

class ParamountIndexingData(AbstractEntry):

    def __init__(self,**kwargs):
        self.current_index = 0
        super(ParamountIndexingData. self).__init__(**kwargs)


class ParamountClusterData(AbstractEntry):
    def __init__(self, paramount_id, descr=None, **kwargs):
        self.paramount_id = paramount_id
        self.descr = descr

        super(ParamountClusterData, self).__init__(**kwargs)



class ParamountClusterRepositoryOperations:
    def __init__(self, repository_name: str = 'paramount_clusters.json', repository_type: str = Defaults.REPOSITORY_TYPE, paramount_prefix = 'paramount'):
        repository_dir =     path_extend(Defaults.modules_data, 'paramount-clusters')


        if os.path.exists(repository_dir):
            if os.path.isfile(repository_dir):
                raise NotADirectoryError("File `{}` is not a directory".format(repository_dir))
        else:
            os.makedirs(repository_dir)

        self.repository_path = path_extend(repository_dir, repository_name)
        self.repository_type = repository_type

        #TinyDBRepository é retornado aqui
        self.repository = RepositoryFactory.get_repository(self.repository_path, self.repository_type)
        self.create_repository()
        self.paramount_prefix = paramount_prefix


    #Creates the table "control" and "paramount"
    def create_repository():
        with get_repository_connection(self.repository) as conn:
            if check_and_create_table(rep, 'control', exists):
                conn.create_element('control', ParamountIndexingData())

            check_and_create_table(repository, 'paramount', exists)

    def new_paramount_cluster(descr=None):

        _cluster = ParamountClusterData(descr)

