import os
import time
import json
import jinja2
import uuid

from typing import List, Any, Dict, Tuple, Union
from dataclasses import dataclass, asdict, field

#from common.clap import AbstractModule, Runner
from clap.executor import SSHCommandExecutor, AnsiblePlaybookExecutor
from clap.repository import Repository, InvalidEntryError
from clap.utils import get_logger, get_random_name, path_extend, Singleton, tmpdir

from clap.node_manager import NodeManager
from clap.cluster_manager import ClusterManager, ClusterConfigDatabase
from clap.role_manager import RoleManager, NodeRoleError


logger = get_logger(__name__)

class Info:
    COORDINATOR = 'mpi-coordinator'
    SLAVES = 'mpi-slave'
    MOUNT_POINT_ROOT= '/efs/'
    LAST_PARAMOUNT='last-mcluster'
    LAST_JOB='last-job'

class MPIDefaults(metaclass=Singleton):
    def __init__(self):
        pass


class Mcluster_states:
    MCLUSTER_RUNNING = 'running'
    MCLUSTER_PAUSED = 'paused'
    MCLUSTER_TERMINATED = 'terminated'
    MCLUSTER_UNKNOWN = 'unknown'


@dataclass
class ParamountClusterData:
    paramount_id: str
    cluster_id: str
    description: str = None
    creation_time: float = None
    update_time: float = None
    coordinator: str = None
    slaves: List[str] = field(default_factory=list)
    mount_point_partition: str = None
    jobs: List[str] = field(default_factory=list)
    mount_ip: str = None
    skip_mpi: bool = False
    no_instance_key: bool = False
    is_setup: bool = False
    status: str = Mcluster_states.MCLUSTER_UNKNOWN

    def to_dict(self):
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> 'ParamountClusterData':
        cluster = ParamountClusterData(**d)
        return cluster

@dataclass
class JobData:
    job_id: str
    paramount_id: str
    name: str = None
    absolute_path: str = None
    creation_time: float = None
    update_time: float = None

    def to_dict(self):
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> 'JobData':
        job = JobData(**d)
        return job

class ParamountClusterRepositoryOperator:
    def __init__(self, repository: Repository, cluster_prefix: str = 'mcluster'):
        self.repository = repository
        self.cluster_prefix = cluster_prefix

    def get_unique_paramount_cluster_id(self) -> str:
        index = str(uuid.uuid4())[:8]
        return f'{self.cluster_prefix}-{index}'

    def new_paramount_cluster(self, cluster_id: str, slaves: List[str], coordinator: str, description: str = None, status: str = Mcluster_states.MCLUSTER_RUNNING) -> str:
        description = description or get_random_name([c.description for c in self.get_all_paramount_clusters()])
        paramount_id = self.get_unique_paramount_cluster_id()
        now = time.time()
        cluster = ParamountClusterData(
            paramount_id=paramount_id, cluster_id=cluster_id, description=description, 
            creation_time=now, update_time=now, coordinator=coordinator, slaves=slaves,
            status=status)
        self.upsert_paramount_cluster(cluster)
        return cluster.paramount_id

    def get_paramount_cluster(self, paramount_id: str) -> ParamountClusterData:
        with self.repository.connect('paramount') as db:
            return ParamountClusterData.from_dict(db.get(paramount_id))

    def get_all_paramount_clusters(self) -> List[ParamountClusterData]:
        with self.repository.connect('paramount') as db:
            return [ParamountClusterData.from_dict(c) for c in db.get_all().values()]

    def upsert_paramount_cluster(self, cluster: ParamountClusterData):
        with self.repository.connect('paramount') as db:
            cluster.update_time = time.time()
            db.upsert(cluster.paramount_id, cluster.to_dict())
      

class JobRepositoryOperator:
    def __init__(self, repository: Repository, job_prefix: str = 'job'):
        self.repository = repository
        self.job_prefix = job_prefix
    
    def get_unique_job_id(self) -> str:
        index = str(uuid.uuid4())[:8]
        return f'{self.job_prefix}-{index}'

    def new_job(self, paramount_id: str, absolute_path_mount: str, job_name: str= None) -> str:
        job_id = self.get_unique_job_id()
        job_name = job_name or get_random_name([j.name for j in self.get_all_jobs()])
        now = time.time()
        absolute_path_mount = os.path.join(absolute_path_mount, job_id)
        job = JobData(
            job_id=job_id,
            paramount_id=paramount_id,
            name=job_name,
            absolute_path=absolute_path_mount,
            creation_time=now,
            update_time=now
        )
        self.upsert_job(job)
        return job.job_id

    def get_job(self, job_id: str) -> JobData:
        with self.repository.connect('jobs') as db:
            return JobData.from_dict(db.get(job_id))

    def get_all_jobs(self) -> List[JobData]:
        with self.repository.connect('jobs') as db:
            return [JobData.from_dict(j) for j in db.get_all().values()]

    def upsert_job(self, job: JobData):
        with self.repository.connect('jobs') as db:
            job.update_time = time.time()
            db.upsert(job.job_id, job.to_dict())
            
##################################################
##################################################
##################################################

class MPIModule:
    module_name = 'mpi'
    module_version = '0.1.0'
    module_description = 'Execute and manage mpi clusters'
    module_tags = ['clusters', 'instances', 'mpi']

    def __init__(self,  job_repository_operator: JobRepositoryOperator, \
                        paramount_repository_operator: ParamountClusterRepositoryOperator, \
                        node_module: NodeManager, \
                        role_module: RoleManager, \
                        cluster_module: ClusterManager):
        self.job_repository_operator = job_repository_operator
        self.paramount_repository_operator = paramount_repository_operator
        self.templates_path = path_extend(os.path.dirname(os.path.abspath(__file__)), 'templates')

    def get_all_clusters(self) -> List[ParamountClusterData]:
        return self.paramount_repository_operator.get_all_paramount_clusters()

    def get_all_jobs(self) -> List[JobData]:
        return self.job_repository_operator.get_all_jobs()

    def get_cluster(self, mpi_cluster_id: str) -> ParamountClusterData:
        #if mpc_id == Info.LAST_PARAMOUNT:
            # must implement
        return self.paramount_repository_operator.get_paramount_cluster(mpi_cluster_id)

    def get_job(self, job_id: str) -> JobData:
        # if job_id == Info.LAST_JOB:
            # must implement
        return self.job_repository_operator.get_job(job_id)

    def setup_mpi_cluster(self, paramount_id: str, mount_ip: str, skip_mpi: bool = False, no_instance_key: bool = False):
        cluster = self.get_cluster(paramount_id)

        mount_point_partition = os.path.join(Info.MOUNT_POINT_ROOT, cluster.paramount_id)
        extra = {
            'nodes_group_name': cluster.paramount_id,
            'mount_ip': mount_ip
        }

        if skip_mpi:
            extra['skip_mpi'] = 'True'
        if no_instance_key:
            extra['use_instance_key'] = 'False'

        group_hosts_map = {'coordinator': [cluster.coordinator]}
        if len(cluster.slaves) > 0:
            group_hosts_map['slave'] = cluster.slaves

        all_nodes = [cluster.coordinator] + cluster.slaves

        self.role_module.add_role('ec2-efs', all_nodes)
        self.role_module.add_role('mpi', group_hosts_map, extra_args=extra)

        if cluster.mount_point_partition is None:
            with tmpdir() as temp_dir:
                filename = path_extend(temp_dir, 'mpi-paramount-cluster.yml')
                extra = {'dest': filename}
                self.role_module.perform_action('mpi', 'get-infos', [cluster.coordinator], extra_args=extra)

                with open(filename, 'r') as f:
                    # TODO not reading home part
                    data = json.loads(f.read())
                    home= data['ansible_env.HOME']
                    mount_point_partition = mount_point_partition if not mount_point_partition.startswith('/') else mount_point_partition[1:] 
                    mount_point_partition = os.path.join(home, mount_point_partition)
                    
        cluster.mount_point_partition = mount_point_partition
        cluster.mount_ip = mount_ip
        cluster.skip_mpi = skip_mpi
        cluster.no_instance_key = no_instance_key
        cluster.is_setup = True

        self.paramount_repository_operator.upsert_paramount_cluster(cluster)

    def create_mpi_cluster(self, nodes: List[Tuple[str, int]], description: str = None, coordinator: str = None) -> str:
        if not nodes:
            raise ValueError('No nodes informed')

        node_type, num_slaves = nodes[0]
        jinjaenv = jinja2.Environment(loader=jinja2.FileSystemLoader(self.templates_path), trim_blocks=True, lstrip_blocks=True)
        template = jinjaenv.get_template("mpi-paramount-cluster.j2")

        if coordinator is None:
            node_type_coord = node_type
            num_slaves -= 1
        else:
            node_type_coord = coordinator
        
        rendered_template = template.render({'node_type_coord': node_type_coord, 'node_type': node_type, 'node_count': num_slaves})

        with tmpdir() as temp_dir:
            filename = path_extend(temp_dir, 'mpi-paramount-cluster.yml')
            with open(filename, 'w') as f:
                f.write(rendered_template)

            configs = ClusterConfigDatabase([filename])
            cluster_to_start = configs.clusters['mpi-paramount-cluster']
            cluster_id = self.cluster_module.start_cluster(cluster_to_startr)
            node_types = self.cluster_module.get_cluster_nodes_types(cluster_id)
            mpi_cluster = self.paramount_repository_operator.new_paramount_cluster(cluster_id=cluster_id, 
                        slaves=node_types[Info.SLAVES], coordinator=node_types[Info.COORDINATOR][0], description=description,
                        status=Mcluster_states.MCLUSTER_RUNNING)
            return mpi_cluster         

    def create_job(self, paramount_id: str, job_name: str = None) -> str:
        mpi_cluster = self.get_cluster(paramount_id)
        if not mpi_cluster.is_setup:
            raise Exception(f"MPI Cluster `{mpi_cluster.paramount_id}`  is not setup. Be sure to setup properly the cluster")
        
        job_id = self.job_repository_operator.new_job(mpi_cluster.paramount_id, mpi_cluster.mount_point_partition, job_name=job_name)
        job = self.get_job(job_id)
        mpi_cluster.jobs.append(job_id)
        self.paramount_repository_operator.upsert_paramount_cluster(mpi_cluster)

        extra = {
            'directory': job.absolute_path,
            'cluster_name': paramount_id
        }
        if mpi_cluster.description:
            extra['cluster_descr'] = mpi_cluster.description
        if job_name:
            extra['job_name'] = job_name
        self.role_module.perform_action('mpi', 'start-job', [mpi_cluster.coordinator], extra_args=extra)

        return job_id

    def push_files(self, job_id: str, src: str, from_coord: bool = False, subpath: str = None):
        job = self.get_job(job_id)
        mpi_cluster = self.get_cluster(job.paramount_id)
        destination = job.absolute_path
        if subpath:
            destination = os.path.join(destination, subpath)

        extra = {
            'execution_dir': destination,
            'src_dir': src
        }

        self.role_module.module.perform_action('mpi', 'sync' if not from_coord else 'sync-remote', [mpi_cluster.coordinator], extra_args=extra)

    def terminate_cluster(self, mpi_cluster_id: str, remove_data_from_sfs: bool = False, force: bool = False):
        mpi_cluster = self.get_cluster(mpi_cluster_id)
        extra = {
            'cluster_folder': mpi_cluster.mount_point_partition
        }
        if remove_data_from_sfs:
            extra['remove_data_from_sfs'] = 'True'
        try:
            self.role_module.perform_action('mpi', 'mpi-terminate', [mpi_cluster.coordinator], extra_args=extra)
        except Exception as e:
            if not force:
                raise e
        
        self.cluster_module.stop_cluster(mpi_cluster.cluster_id)
        mpi_cluster.status = Mcluster_states.MCLUSTER_TERMINATED
        self.paramount_repository_operator.upsert_paramount_cluster(mpi_cluster)

        # TODO jobs attached to cluster still alive...
        # Remove cluster?

    def pause_cluster(self, mpi_cluster_id: str, force: bool = False):
        mpi_cluster = self.get_cluster(mpi_cluster_id)
        self.cluster_module.pause_cluster(mpi_cluster.cluster_id, force_pause=force)
        mpi_cluster.status = Mcluster_states.MCLUSTER_PAUSED
        self.paramount_repository_operator.upsert_paramount_cluster(mpi_cluster)

    def resume_cluster(self, mpi_cluster_id: str):
        mpi_cluster = self.get_cluster(mpi_cluster_id)
        self.cluster_module.resume_cluster(mpi_cluster.cluster_id)
        mpi_cluster.status = Mcluster_states.MCLUSTER_RUNNING
        self.paramount_repository_operator.upsert_paramount_cluster(mpi_cluster)

    def compile_script(self, job_id: str, script: str, subpath: str = None):
        job = self.get_job(job_id)
        mpi_cluster = self.get_cluster(job.paramount_id)

        execution_dir = job.absolute_path
        if subpath:
            execution_dir = os.path.join(execution_dir, subpath)
        
        extra = {
            'compile_script': script,
            'execution_dir': execution_dir
        }

        self.role_module.perform_action('mpi', 'compile', [mpi_cluster.coordinator], extra_args=extra)

    def run_script(self, job_id: str, script: str, subpath: str = None, exec_descr: str = None, run_on_taskdir: bool = False):
        job = self.get_job(job_id)
        mpi_cluster = self.get_cluster(job.paramount_id)

        execution_dir = job.absolute_path + '/'
        if subpath:
            execution_dir = os.path.join(execution_dir, subpath)

        extra = {
            'run_script': script,
            'execution_dir': execution_dir,
            'job_full_path': job.absolute_path,
            'mcluster_dir': mpi_cluster.mount_point_partition,
            'exec_descr': exec_descr
        }

        if run_on_taskdir:
            extra['run_on_taskdir'] = 'True'

        self.role_module.perform_action('mpi', 'run-script', [mpi_cluster.coordinator], extra_args=extra)

    def generate_hosts(self, job_id: str, filename: str = None, subpath: str = None, mpich_style: bool = False):
        job = self.get_job(job_id)
        mpi_cluster = self.get_cluster(job.paramount_id)

        execution_dir = job.absolute_path + '/'
        if subpath:
            execution_dir = os.path.join(execution_dir, subpath)

        extra = {
            'execution_dir': execution_dir
        }

        if filename:
            extra['file_name'] = filename
        if mpich_style:
            extra['mpich_style'] = 'True'
            
        nodes_to_execute = self.cluster_module.get_all_cluster_nodes(mpi_cluster.cluster_id)
        self.role_module.perform_action('mpi', 'generate-hosts', nodes_to_execute, extra_args=extra)

    def fetch_job(self, job_id: str, destination: str):
        job = self.get_job(job_id)
        mpi_cluster = self.get_cluster(job.paramount_id)
        path = os.path.join(job.absolute_path, 'tasks', '*')
        extra = {
            'src': path,
            'dest': destination,
            'job_name': job.job_id
        }
        nodes_to_execute = self.cluster_module.get_all_cluster_nodes(mpi_cluster.cluster_id)
        self.role_module.perform_action('mpi', 'fetch-job-info', nodes_to_execute, extra_args=extra)

    def fetch_data_coord(self, mpi_cluster_id: str, src: str, destination: str):
        mpi_cluster = self.get_cluster(mpi_cluster_id)
        extra = {
            'src': src,
            'dest': destination
        }
        nodes_to_execute = self.cluster_module.get_all_cluster_nodes(mpi_cluster.cluster_id)
        self.role_module.perform_action('mpi', 'fetch-data-coord', nodes_to_execute, extra_args=extra)

    def install_script(self, mpi_cluster_id: str, script: str, only_coord: bool = False, additional_file: str = None, path: str = None):
        mpi_cluster = self.get_cluster(mpi_cluster_id)
        extra = {
            'install_script': script
        }
        if path:
            extra['execution_dir'] = path
        if additional_file is not None:
            extra['src_dir'] = additional_file

        node_ids = [mpi_cluster.coordinator] + mpi_cluster.slaves if not only_coord else [mpi_cluster.coordinator]
        self.role_module.perform_action(mpi_cluster_id, 'install', node_ids, extra_args=extra)
    
    def run_command(self, mpi_cluster_id: str, command: str, private_path: str) -> dict:
        mpi_cluster = self.get_cluster(mpi_cluster_id)
        nodes_to_execute = self.cluster_module.get_all_cluster_nodes(mpi_cluster.cluster_id)
        cmd = SSHCommandExecutor(command, nodes_to_execute, private_path)
        return cmd.run()
        
    def run_playbook(self, mpi_cluster_id: str, playbook_file: str, private_path: str, only_coord: bool = False, extra: dict = None):
        mpi_cluster = self.get_cluster(mpi_cluster_id)
        extra = extra or dict()
        node_ids = [mpi_cluster.coordinator] + mpi_cluster.slaves if not only_coord else [mpi_cluster.coordinator]
        nodes = self.node_module.get_nodes_by_id(node_ids)
        inventory = AnsiblePlaybookExecutor.create_inventory(nodes, private_path, {}, {})
        executor = AnsiblePlaybookExecutor(playbook_file, private_path, inventory, extra)
        return executor.run()

# Missing change_coordinator
# Missing add_from_instances
# Must test before implement more...

# def test_repository_operator():
#     with tmpdir() as d:
#         print(f'Temporary directory: {d}')
#         paramount_repo_path = path_extend(d, 'paramount')
#         jobs_repo_path = path_extend(d, 'jobs')
#         paramount_repository = SQLiteRepository(paramount_repo_path)
#         jobs_repository = SQLiteRepository(jobs_repo_path)
#         paramount_operator = ParamountClusterRepositoryOperator(paramount_repository)
#         jobs_operator = JobRepositoryOperator(jobs_repository)
        
#         paramount_cluster = paramount_operator.new_paramount_cluster('cluster-0', [], None)
#         job = jobs_operator.new_job(paramount_cluster.paramount_id, 'abspath')

#         print(paramount_operator.get_all_paramount_clusters())
#         print(jobs_operator.get_all_jobs())


if __name__ == '__main__':
    from clap.utils import tmpdir, path_extend
    from clap.repository import SQLiteRepository
    
    paramount_repo_path = '/home/napoli/mpi-paramount-repo.db'
    jobs_repo_path = '/home/napoli/mpi-jobs.db'
    
    paramount_repo = SQLiteRepository(paramount_repo_path)
    jobs_repo = SQLiteRepository(jobs_repo_path)
    
    paramount_operator = ParamountClusterRepositoryOperator(paramount_repo)
    jobs_operator = JobRepositoryOperator(jobs_repo)
    
    cluster_id = paramount_operator.new_paramount_cluster('cluster-1', slaves=['node-1', 'node-2'], coordinator='node-0')
    cluster = paramount_operator.get_paramount_cluster(cluster_id)
    
    job_id = jobs_operator.new_job(paramount_id='ola', absolute_path_mount='/efs')
    job = jobs_operator.get_job(job_id)
    print(cluster, job)

#    mpi_module = MPIModule.get_module()
#    cluster_id = mpi_module.create_mpi_cluster(nodes=[('type-a', 2)], description='fox sheep')
#    print(mpi_module.get_all_clusters())
    
#    efs_mount_point = '172.31.7.112'
#    mpi_module.setup_mpi_cluster(cluster_id, efs_mount_point, skip_mpi=False)
    
#    job_name = 'example-job'
#    job_id = mpi_module.create_job(cluster_id, job_name=job_name)
#    print(mpi_module.get_all_clusters())
#    print(mpi_module.get_all_jobs())

#    directory_to_push = path_extend('~/temp/NPB/NPB3.4.1')
#    mpi_module.push_files(job_id, src=directory_to_push)

#    compile_script_file = path_extend('~/temp/NPB/compile.sh')
#    mpi_module.compile_script(job_id, script=compile_script_file)

#    mpi_module.generate_hosts(job_id)

#    execute_script_file = path_extend('~/temp/NPB/execute.sh')
#    mpi_module.run_script(job_id, script=execute_script_file, exec_descr='example-description')

#    print('Sleep a little....')
#    time.sleep(15)

#    with tmpdir() as temp:
#        results_dir = os.path.join(temp, 'results')
#        mpi_module.fetch_job(job_id, results_dir)

#        print(f'check results at `{results_dir}`')
#        print('\n')

#    mpi_module.terminate_cluster(cluster_id, force=True)



        
