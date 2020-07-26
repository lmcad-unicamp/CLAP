
import os
import time
from clap.common.repository import (AbstractEntry, AbstractRepository, RepositoryFactory,
                                    check_and_create_table, get_repository_connection, generic_read_entry,
                                    generic_write_entry)
from clap.common.utils import log, path_extend
from clap.common.config import Defaults
from typing import List
from .conf import Info
from clap.common.factory import PlatformFactory


class JobsIndexingData(AbstractEntry):

    def __init__(self,**kwargs):
        self.current_index = 0
        super(JobsIndexingData, self).__init__(**kwargs)


class JobData(AbstractEntry):
    def __init__(self, paramount_id, jobId, absolutePath,name=None, **kwargs):
        self.paramount_id = paramount_id # Id internal to cluster table
        self.name = name
        self.jobId =  jobId
        self.absolutePath = absolutePath

        super(JobData, self).__init__(**kwargs)

    def __repr__(self):
        if self.name:
            _string = "Job: {}@{} (alias:'{}')  in path: {}".format(self.jobId, self.paramount_id, self.name, self.absolutePath)
        else:
            _string = "Job: {}@{}, in path: {}".format(self.jobId, self.paramount_id,self.absolutePath)

        return _string

class JobDataRepositoryOperations:
    def __init__(self, repository_name: str = 'paramount_jobs.json', repository_type: str = Defaults.REPOSITORY_TYPE):
        repository_dir =     path_extend(Defaults.modules_data, 'paramount_jobs')


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

        # Creates the table "control" and "paramount"

    def create_repository(self):
        with get_repository_connection(self.repository) as conn:
            # debug

            _typeOfCreateControl = 'overwrite'
            _typeOfCreateClusterData = 'overwrite'

            try:
                # Há um bug no qual a table pode ter sido criada mas não há elementos

                _elemsControl = conn.retrieve_elements('job_control', JobsIndexingData)
                _elemsClusterData = conn.retrieve_elements('job', JobData)

                _typeOfCreateControl = 'overwrite' if _elemsControl.__len__() == 0 else 'pass'
                _typeOfCreateClusterData = 'overwrite' if _elemsClusterData.__len__() == 0 else 'pass'
            except ValueError:
                pass



            if check_and_create_table(conn, 'job_control', _typeOfCreateControl):
                conn.create_element('job_control', JobsIndexingData())
            check_and_create_table(conn, 'job', _typeOfCreateClusterData)


    def new_job(self,cluster_obj, absolute_path_mount,name=None):

        cluster_module = PlatformFactory.get_module_interface().get_module('cluster')

        with get_repository_connection(self.repository) as conn:
            _control = next(iter(generic_read_entry(JobsIndexingData, conn, 'job_control')))
            _control.current_index += 1
            # conn.update_element('control', _control)

            _id = Info.JOB_PREFIX +  str(_control.current_index )
            _job = JobData(
                paramount_id=cluster_obj.paramount_id,
                jobId=_id,
                absolutePath=absolute_path_mount+ '/'+ _id,
                name = name
                )

            #Run playbook first then add to the table...
            extra = {}
            extra.update({'directory': _job.absolutePath})

            cluster_module.perform_group_action(cluster_id= cluster_obj.cluster_id, group_name='mpi/coordinator',
                                                action_name='start-job',
                                                node_ids=[cluster_obj.coordinator],
                                                extra_args=extra)

            generic_write_entry(_control, conn, 'job_control', create=False)
            print("Successfully created job:")
            print(_job)
            generic_write_entry(_job, conn, 'job', create=True)

        return _job


    def get_job_data(self, job_id):
        with get_repository_connection(self.repository) as conn:
            return conn.retrieve_elements('job', JobData, **{'jobId': job_id})
    def list_jobs(self):
        with get_repository_connection(self.repository) as conn:
            return conn.retrieve_elements('job', JobData)