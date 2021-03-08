
import os
import time
from clap.common.repository import (AbstractEntry, AbstractRepository, RepositoryFactory, 
                                    check_and_create_table, get_repository_connection, generic_read_entry,
                                    generic_write_entry)
from clap.common.utils import log, path_extend
from clap.common.config import Defaults
from clap.common.factory import PlatformFactory

import enum
from typing import List
from .conf import Info


class Mcluster_states(enum.Enum):
   MCLUSTER_RUNNING = 1
   MCLUSTER_PAUSED = 2
   MCLUSTER_TERMINATED= 3

Mcluster_states_dict = {
    1: 'RUNNING',
    2: 'PAUSED',
    3: 'TERMINATED'

}



def translate_state(mcluster_state):
    _str = 'UNK STATE'
    _state = Mcluster_states_dict.get(mcluster_state, None)
    if _state is None:
        return _str
    else:
        return  _state

class ParamountIndexingData(AbstractEntry):

    def __init__(self,**kwargs):
        self.current_index = 0
        super(ParamountIndexingData, self).__init__(**kwargs)


class ParamountClusterData(AbstractEntry):
    def __init__(self, paramount_id, cluster_id, slaves, coordinator, status=1, isSetup= False,  mount_ip= None, \
                 no_instance_key = None, skip_mpi = None, descr=None, mount_point_partition=None, **kwargs):
        self.paramount_id = paramount_id # Id internal to cluster table
        self.cluster_id = cluster_id #Id referencing the actual cluster instance (used to perform actions)
        self.descr = descr #optional, verbal description of a cluster
        self.slaves = slaves
        self.coordinator = coordinator
        self.mount_point_partition = mount_point_partition
        self.jobs = []
        self.mount_ip = mount_ip
        self.skip_mpi = skip_mpi
        self.no_instance_key = no_instance_key
        self.isSetup = isSetup
        self.status = status
        super(ParamountClusterData, self).__init__(**kwargs)

    def __repr__(self):
        node_module = PlatformFactory.get_module_interface().get_module('node')

        if self.status == Mcluster_states.MCLUSTER_TERMINATED:
            return ''
        else:
            _coord_node_obj = node_module.list_nodes([self.coordinator])
            _coord_type = _coord_node_obj[0].instance_type
            _string = "MPI cluster (mcluster) of id: \'" +self.paramount_id + '\'.' " Cluster id: \'"+ self.cluster_id+ '\'. '+\
                      "Status: "+ translate_state(self.status) +  '. ' \
                      "Coordinator is: " +self.coordinator \
                      +  ' (type: {})'.format(_coord_type)
            if self.slaves and self.slaves.__len__() > 0:
                _string = _string + " slaves are: {"

                for _slave in self.slaves:
                    _node_obj = node_module.list_nodes([_slave])
                    _slave_type = _node_obj[0].instance_type
                    _string = _string + "{} (type: {}), ".format(_slave, _slave_type)


                _string = _string + "}"


            _string =  _string + '. Jobs configured are: ' + ', '.join(self.jobs)

            return _string

    def change_state(self, new_state_enum):
        '''Methods use the enum (due to ease and flexibility), however the ParamountClusterData cannot have status as enum
            because a enum is not JSON serializable, so this method converts a enum to the number


        '''

        #_state_number = Mcluster_states_dict.get(new_state_enum.value)
        self.status = new_state_enum.value


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

    def new_paramount_cluster(self, cluster_id,slaves, coordinator, descr=None, status=1) -> ParamountClusterData:

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
                                descr=descr,
                                status=status)
            generic_write_entry(_cluster, conn, 'paramount', create=True)

        return _cluster

    def list_paramount_clusters(self) -> List[ParamountClusterData] : 
        with get_repository_connection(self.repository) as conn:
            return conn.retrieve_elements('paramount', ParamountClusterData)

    def get_paramount_data(self, paramount_id):
        with get_repository_connection(self.repository) as conn:
            return conn.retrieve_elements('paramount', ParamountClusterData, **{'paramount_id': paramount_id})


    def get_newest_paramount_id(self, ):
        with get_repository_connection(self.repository) as conn:
            _control = next(iter(generic_read_entry(ParamountIndexingData, conn, 'control')))
            return _control.current_index



    def update_paramount(self, paramount_cluster_data: ParamountClusterData) -> str:
        with get_repository_connection(self.repository) as repository:
            generic_write_entry(paramount_cluster_data, repository, 'paramount', create=False,
                paramount_id=paramount_cluster_data.paramount_id)