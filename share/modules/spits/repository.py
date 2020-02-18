import time
from typing import List

from cloudpits.common.repository import AbstractEntry, check_and_create_table, RepositoryFactory


class SpitsControlInfo(AbstractEntry):
    def __init__(self, *args, **kwargs):
        self.control = 0
        self.job_idx = 0
        self.process_idx = 0
        self.installeds = list()
        super(SpitsControlInfo, self).__init__(**kwargs)


class SpitsJobInfo(AbstractEntry):
    def __init__(self, *args, **kwargs):
        self.job_id = None
        self.job_name = None
        self.spits_binary_path = None
        self.spits_binary_args = None
        self.jm_args = None
        self.tm_args = None
        self.description = None
        self.nodes = list()
        super(SpitsJobInfo, self).__init__(**kwargs)

    def __repr__(self):
        return 'Job(id=`{}`, name=`{}`, nodes=`{}`, spits_binary_path=`{}`, description=`{}`)'.format(
            self.job_id, self.job_name, self.nodes, self.spits_binary_path, self.description)


class SpitsProcessInfo(AbstractEntry):
    SPITS_JM = 'jobmanager'
    SPITS_TM = 'taskmanager'

    def __init__(self, *args, **kwargs):
        self.process_id = None
        self.job_id = None
        self.node_id = None
        self.creation_time = time.time()
        self.update_time = self.creation_time
        self.host_addr = None
        self.port = 0
        self.pid = 0
        self.status = None
        self.manager_type = None
        super(SpitsProcessInfo, self).__init__(**kwargs)

    def __repr__(self):
        return 'Process(id=`{}` ({}), job_id=`{}`, node_id=`{}`, host=`{}:{}`, creation_time=`{}`)'.format(
            self.process_id, self.manager_type, self.job_id, self.node_id,
            self.host_addr, self.port, self.creation_time)


class SpitsRepositoryOperations:
    def __init__(self, repository_name: str):
        self.repository = RepositoryFactory.get_repository(repository_name)
        self.create_repository()

    def create_repository(self):
        if check_and_create_table(self.repository, 'control', 'pass'):
            self.repository.create_element('control', SpitsControlInfo())
        check_and_create_table(self.repository, 'processes', 'pass')
        check_and_create_table(self.repository, 'jobs', 'pass')

    def update_control_info(self, control_info: SpitsControlInfo):
        self.repository.update_element('control', control_info)

    def get_control_info(self) -> SpitsControlInfo:
        return self.repository.retrieve_elements('control', SpitsControlInfo)[0]

    def register_installed(self, node_ids: List[str]):
        control = self.get_control_info()
        control.installeds = list(set(control.installeds + node_ids))
        self.update_control_info(control)
        return control.installeds

    def check_installed(self, node_ids: List[str]):
        control = self.get_control_info()
        return all([True if node_id in control.installeds else False for node_id in node_ids])

    def deregister_installation(self, node_ids: List[str]):
        control = self.get_control_info()
        control.installeds = list(set(control.installeds).difference(node_ids))
        self.update_control_info(control)
        return control.installeds

    def save_or_update_job(self, spits_job: SpitsJobInfo):
        job = self.repository.retrieve_elements('jobs', SpitsJobInfo, job_id=spits_job.job_id)
        if len(job) == 0:
            self.repository.create_element('jobs', spits_job)
        else:
            self.repository.update_element('jobs', spits_job, job_id=spits_job.job_id)

    def get_jobs(self, job_ids: List[str] = None) -> List[SpitsJobInfo]:
        if not job_ids:
            return self.repository.retrieve_elements('jobs', SpitsJobInfo)

        return [item for sublist in [self.repository.retrieve_elements(
            'jobs', SpitsJobInfo, job_id=jobid) for jobid in job_ids]
                for item in sublist]

    def get_job(self, job_id: str) -> SpitsJobInfo:
        return self.repository.retrieve_elements('jobs', SpitsJobInfo, job_id=job_id)[0]

    def remove_job(self, job_id: str):
        return self.repository.drop_elements('jobs', job_id=job_id)

    def save_or_update_process(self, process_info: SpitsProcessInfo):
        process = self.repository.retrieve_elements(
            'processes', SpitsProcessInfo, process_id=process_info.process_id)
        if len(process) == 0:
            self.repository.create_element('processes', process_info)
        else:
            self.repository.update_element(
                'processes', process_info, process_id=process_info.process_id)

    def get_processes(self, process_ids: List[str] = None) -> List[SpitsProcessInfo]:
        if not process_ids:
            return self.repository.retrieve_elements('processes', SpitsProcessInfo)

        return [item for sublist in [self.repository.retrieve_elements(
            'processes', SpitsProcessInfo, process_id=process_id)
            for process_id in process_ids] for item in sublist]

    def get_processes_by_job(self, job_ids: List[str]) -> List[SpitsProcessInfo]:
        return [item for sublist in [self.repository.retrieve_elements(
            'processes', SpitsProcessInfo, job_id=job_id)
            for job_id in job_ids] for item in sublist]

    def get_process(self, process_id: str) -> SpitsProcessInfo:
        return self.repository.retrieve_elements('processes', SpitsProcessInfo, process_id=process_id)[0]

    def remove_process(self, process_id: str):
        return self.repository.drop_elements('processes', process_id=process_id)
