
import os
import time
from clap.common.repository import (AbstractEntry, AbstractRepository, RepositoryFactory, 
                                    check_and_create_table, get_repository_connection, generic_read_entry,
                                    generic_write_entry)
from clap.common.utils import log, path_extend
from clap.common.config import Defaults
from typing import List
from .conf import Info


class ParamountIndexingData(AbstractEntry):

    def __init__(self,**kwargs):
        self.current_index = 0
        super(ParamountIndexingData, self).__init__(**kwargs)


class ParamountClusterData(AbstractEntry):
    def __init__(self, paramount_id, cluster_id, slaves, coordinator, isSetup= False,  mount_point_id= None,  no_instance_key = None, skip_mpi = None, descr=None, mount_point_partition=None, **kwargs):
        self.paramount_id = paramount_id # Id internal to cluster table
        self.cluster_id = cluster_id #Id referencing the actual cluster instance (used to perform actions)
        self.descr = descr #optional, verbal description of a cluster
        self.slaves = slaves
        self.coordinator = coordinator
        self.mount_point_partition = mount_point_partition
        self.jobs = []
        self.mount_point_id = mount_point_id
        self.skip_mpi = skip_mpi
        self.no_instance_key = no_instance_key
        super(ParamountClusterData, self).__init__(**kwargs)

    def __repr__(self):
        _string = "Paramount cluster of id: " +self.paramount_id + " cluster id is: "+ self.cluster_id+ " coordinator is: " +self.coordinator
        if self.slaves and self.slaves.__len__() > 0:
            _string = _string + " slaves are: {"
            for _slave in self.slaves:
                _string = _string + "{}, ".format(_slave)

            _string = _string + "}"


        _string =  _string + ' Jobs configured are: ' + ', '.join(self.jobs)

        return _string

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


    #Creates the table "control" and "paramount"
    def create_repository(self):
        with get_repository_connection(self.repository) as conn:
            # debug

            _typeOfCreateControl = 'overwrite'
            _typeOfCreateClusterData = 'overwrite'

            try:
                # Há um bug no qual a table pode ter sido criada mas não há elementos

                _elemsControl = conn.retrieve_elements('control', ParamountIndexingData)
                _elemsClusterData = conn.retrieve_elements('paramount', ParamountClusterData)
                _typeOfCreateControl = 'overwrite' if _elemsControl.__len__() == 0 else 'pass'
                _typeOfCreateClusterData = 'overwrite' if _elemsClusterData.__len__() == 0 else 'pass'
            except ValueError:
                pass



            if check_and_create_table(conn, 'control', _typeOfCreateControl):

                conn.create_element('control', ParamountIndexingData())
            check_and_create_table(conn, 'paramount', _typeOfCreateClusterData)

    def new_paramount_cluster(self, cluster_id,slaves, coordinator, descr=None) -> ParamountClusterData:

        _cluster = None
        with get_repository_connection(self.repository) as conn:
            
            _control = next(iter(generic_read_entry(ParamountIndexingData, conn, 'control')))
            _control.current_index += 1
            #conn.update_element('control', _control)
            generic_write_entry(_control, conn, 'control', create=False)
            _cluster = ParamountClusterData(
                                slaves=slaves,
                                coordinator=coordinator,
                                cluster_id= cluster_id,
                                paramount_id= Info.CLUSTER_PREFIX + str( _control.current_index) ,
                                descr=descr)
            generic_write_entry(_cluster, conn, 'paramount', create=True)

        return _cluster

    def list_paramount_clusters(self) -> List[ParamountClusterData] : 
        with get_repository_connection(self.repository) as conn:
            return conn.retrieve_elements('paramount', ParamountClusterData)

    def get_paramount_data(self, paramount_id):
        with get_repository_connection(self.repository) as conn:
            return conn.retrieve_elements('paramount', ParamountClusterData, **{'paramount_id': paramount_id})


    def update_paramount(self, paramount_cluster_data: ParamountClusterData) -> str:
        with get_repository_connection(self.repository) as repository:
            generic_write_entry(paramount_cluster_data, repository, 'paramount', create=False,
                paramount_id=paramount_cluster_data.paramount_id)