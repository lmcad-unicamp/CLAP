import yaml
import os
import click

from typing import List, Dict
from collections import defaultdict
from paramiko import SSHException

from common.utils import path_extend, float_time_to_string, get_logger
from modules.mpi import MPIModule, MPIDefaults
from app.module import clap_command

logger = get_logger(__name__)

mpi_defaults = MPIDefaults()

def get_mpi_module() -> MPIModule:
    return MPIModule.get_module()

@clap_command
@click.group(help='Control and manage MPI Clusters')
def mpi():
    pass

@mpi.command('create-mcluster')
@click.argument('node_types', nargs=-1, type=str)
@click.option('-c', '--coordinator', default=None, help='A string containing the type of the coordinator', show_default=False)
@click.option('-d', '--desc', default=None, help='Nickname for this cluster', show_default=False)
def create_mcluster(node_types, coordinator, desc):
    mpi_module = get_mpi_module()
    nodes_to_start = []
    for node_type in node_types:
        if ':' not in node_type:
            nodes_to_start.append((node_type, 1))
        else:
            n_type, n_num = node_type.split(':')[0], int(node_type.split(':')[1])
            nodes_to_start.append((n_type, n_num))
        
    cluster_id = mpi_module.create_mpi_cluster(nodes_to_start, description=desc, coordinator=coordinator)
    print(f'Cluster `{cluster_id}` successfully created!')
    return 0

@mpi.command('list-mclusters')
def list_mclusters():
    mpi_module = get_mpi_module()
    clusters = mpi_module.get_all_clusters()
    for c in clusters:
        print(f'* MPI cluster of id `{c.paramount_id}` associated with cluster `{c.cluster_id}`. Status: {c.status.upper()}. Coordinator id is: {c.coordinator}, slaves are: {c.slaves}. Jobs configurated are: {c.jobs}')

    print(f'Listed {len(clusters)} MPI clusters')
    return 0

@mpi.command('setup-mcluster')
@click.argument('mpi_cluster_id', nargs=1, type=str)
@click.option('-m', '--mount_ip', required=True, default=None, help='Mount ip address', show_default=False)
@click.option('-s', '--skip_mpi', is_flag=True, default=False, show_default=True, help='Flag to skip mpi related package installation')
@click.option('--no_instance_key', is_flag=True, default=False, show_default=True, help='Flag indicating to not use the instance key')
def setup_mcluster(mpi_cluster_id, mount_ip, skip_mpi, no_instance_key):
    mpi_module = get_mpi_module()
    mpi_module.setup_mpi_cluster(mpi_cluster_id, mount_ip=mount_ip, skip_mpi=skip_mpi, no_instance_key=no_instance_key)
    print(f'Cluster `{mpi_cluster_id}` successfully setup')

    mpi_cluster = mpi_module.get_cluster(mpi_cluster_id)
    print(f'New mount_point_partition (After updating) is: {mpi_cluster.mount_point_partition}')

    return 0


@mpi.command('create-job')
@click.argument('mpi_cluster_id', nargs=1, type=str)
@click.option('-j', '--job_name', default=None, show_default=False, help='Optional job description')
def create_job(mpi_cluster_id, job_name):
    mpi_module = get_mpi_module()
    job_id = mpi_module.create_job(mpi_cluster_id, job_name=job_name)
    job = mpi_module.get_job(job_id)
    print(f'Job `{job_id}` successfully created')
    print(f'Job: {job_id} at {job.paramount_id} (alias: {job.name}) in path: `{job.absolute_path}`')
    return 0


@mpi.command('list-jobs')
def list_jobs():
    mpi_module = get_mpi_module()
    jobs = mpi_module.get_all_jobs()
    for job in jobs:
        print(f'Job: {job.job_id} at {job.paramount_id} (alias: {job.name}) in path: `{job.absolute_path}`')
    print(f'Listed {len(jobs)} jobs')
    return 0

@mpi.command('push-job-files')
@click.argument('job_id', nargs=1, type=str)
@click.argument('source', nargs=1, type=str)
@click.option('-s', '--sub_path', default=None, show_default=False, help='Subdirectory inside job folder where the script should be executed, if left unspecified it will execute in the job root')
@click.option('-fc', '--from_coord', default=False, is_flag=True, show_default=True, help='Flag that indicates the the coordinator already has the files somewhere  in the system, and therefore these files should be pushed from the coordinator to the job folder in the file system')
def push_job_files(job_id, source, sub_path, from_coord):
    mpi_module = get_mpi_module()
    mpi_module.push_files(job_id, source, from_coord=from_coord, subpath=sub_path)
    return 0


@mpi.command('setup-job')
@click.argument('job_id', nargs=1, type=str)
@click.argument('script_path', nargs=1, type=str)
@click.option('-s', '--sub_path', default=None, show_default=False, help='Subdirectory inside job folder where the script should be executed, if left unspecified it will execute in the job root')
def setup_job(job_id, script_path, sub_path):
    mpi_module = get_mpi_module()
    mpi_module.compile_script(job_id, script=script_path, subpath=sub_path)
    return 0


@mpi.command('gen-job-hostfile')
@click.argument('job_id', nargs=1, type=str)
@click.option('-f', '--filename', default=None, show_default=False, help="What name should the file be, defaults to 'host'")
@click.option('-s', '--sub_path', default=None, show_default=False, help='Subdirectory inside job folder where the script should be executed, if left unspecified it will execute in the job root')
@click.option('-m', '--mpich_style', is_flag=True, default=False, show_default=True, help='If the hostfile should be written in a mpich style way')
def genenerate_hostfiles(job_id, filename, sub_path, mpich_style):
    mpi_module = get_mpi_module()
    mpi_module.generate_hosts(job_id, filename, subpath=sub_path, mpich_style=mpich_style)
    return 0

@mpi.command('run-job-task')
@click.argument('job_id', nargs=1, type=str)
@click.argument('script_path', nargs=1, type=str)
@click.option('-rp', '--run_on_path', default=None, show_default=False, help='Subdirectory inside job folder where the script should be executed, if left unspecified it will execute in the job root')
@click.option('-rt', '--run_on_taskdir', is_flag=True, default=False, show_default=True, help='Flag that specifies if the application should run on the respective task folder')
@click.option('-e', '--exec_desc', default=None, show_default=False, help='Description of this specific execution (problem size, algorithm used...)')
def run_job_task(job_id, script_path, run_on_path, run_on_taskdir, exec_desc):
    mpi_module = get_mpi_module()
    
    if run_on_taskdir and (run_on_path is not None):
        raise Exception("You cannot simultaneously specify run_on_taskdir and a run_on_path on the job folder")

    mpi_module.run_script(job_id, script=script_path, subpath=run_on_path, exec_descr=exec_desc, run_on_taskdir=run_on_taskdir)
    return 0

@mpi.command('fetch-tasks-results')
@click.argument('job_id', nargs=1, type=str)
@click.argument('destination', nargs=1, type=str)
def fetch_task_results(job_id, destination):
    mpi_module = get_mpi_module()
    mpi_module.fetch_job(job_id, destination=destination)
    print(f'Job {job_id} fetched to destination {destination}')
    return 0


@mpi.command('destroy-mcluster')
@click.argument('mpi_cluster_id', nargs=1, type=str)
@click.option('-r', '--remove_data_from_sfs', is_flag=True, default=False, show_default=True, help='If set the files from the cluster on the shared filesystem will be removed')
@click.option('-f', '--force', is_flag=True, default=False, show_default=True, help='Force cluster removal (and nodes stop) even if some things failed') 
def destroy_mcluster(mpi_cluster_id, remove_data_from_sfs, force):
    mpi_module = get_mpi_module()
    mpi_module.terminate_cluster(mpi_cluster_id, remove_data_from_sfs=remove_data_from_sfs, force=force)
    print(f'Cluster `{mpi_cluster_id}` destroyed')
    return 0

