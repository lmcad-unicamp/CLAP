import os
import jinja2
import csv
import time

from typing import List, Dict, Tuple, Any
from jinja2 import Template, StrictUndefined

from clap.common.factory import PlatformFactory
from clap.common.cluster_repository import NodeInfo
from clap.common.driver import Codes
from clap.common.utils import log, yaml_load, tmpdir, path_extend
from .repository import ParamountClusterData, ParamountClusterRepositoryOperations
from .conf import ParamountClusterDefaults, ParamountState

def create_paramount_cluster(
        app_name: str, 
        node_type: str, 
        node_counts: List[int],
        setup: bool = False, 
        app_dir: str = None,
        execution_dir: str = None,
        setup_efs: bool = False,
        mount_ip: str = None,
        mount_dir: str = None,
        install_script: str = None,
        compile_script: str = None) -> Tuple[ParamountClusterData, bool]:
    cluster_module = PlatformFactory.get_module_interface().get_module('cluster')
    repository = ParamountClusterRepositoryOperations()
    max_count = max(node_counts)
    # check min of 2 nodes
    jinjaenv = jinja2.Environment(loader=jinja2.FileSystemLoader(os.path.dirname(os.path.abspath(__file__))), 
                trim_blocks=True, lstrip_blocks=True)
    template = jinjaenv.get_template('paramount-cluster.j2')
    rendered_template = template.render({'node_type': node_type, 'node_count': max_count})
    
    with tmpdir() as dir:
        filename = path_extend(dir, 'paramount-cluster.yml')
        with open(filename, 'w') as f:
            f.write(rendered_template)
        cluster, nodes, is_setup = cluster_module.cluster_create([filename], cluster_name='paramount-cluster')

    paramount = repository.new_paramount(app_name, cluster.cluster_id, node_type, node_counts)
    is_setup = False
    try:
        if setup:
            paramount = setup_paramout_cluster(paramount.paramount_id, app_dir=app_dir, execution_dir=execution_dir,
                install_script=install_script, compile_script=compile_script)
            is_setup = True
        elif setup_efs:
            paramount = setup_paramount_cluster_efs(paramount.paramount_id, 
                execution_dir=execution_dir, mount_ip=mount_ip, mount_dir=mount_dir, app_dir=app_dir)
            is_setup = True

    except Exception as e:
        log.error("Error at paramount cluster `{}` setup: {}".format(paramount.paramount_id, e))
        log.error("Please setup paramount cluster `{}` manually using setup command".format(paramount.paramount_id))
    
    return paramount, is_setup

def list_paramount() -> List[ParamountClusterData]:
    repository = ParamountClusterRepositoryOperations()
    return repository.get_all_paramount()

def setup_paramount_cluster_efs(paramount_id: str, 
                            execution_dir: str = None,
                            mount_ip: str = None,
                            mount_dir: str = None, 
                            app_dir: str = None) -> ParamountClusterData:
    pass

# We wil copy a paramount mpi application if app_dir is defined
def setup_paramout_cluster( paramount_id: str, 
                            app_dir: str = None,
                            execution_dir: str = None,
                            install_script: str = None,
                            compile_script: str = None) -> ParamountClusterData:
    cluster_module = PlatformFactory.get_module_interface().get_module('cluster')
    repository = ParamountClusterRepositoryOperations()
    paramount = repository.get_paramount(paramount_id)

    # Suppose that app files is not at remote hosts, and we will copy to the location
    # If app is already at remote host, we just skip the copy section
    extra = {'paramount_id': paramount_id}
    if app_dir:
        extra['app_dir'] = app_dir
    if execution_dir:
        extra['execution_dir'] = execution_dir

    log.info("Setting up paramount cluster `{}`".format(paramount_id))
    cluster_module.perform_group_action(paramount.cluster_id, group_name='paramount', action_name='setup-paramount-job', 
            extra_args=extra)

    # If executeion dir is not defined, it is controlled by ansible...
    paramount.execution_dir = execution_dir
    paramount.is_setup = True
    paramount.use_shared_fs = False
    repository.update_paramount(paramount)

    if install_script or compile_script:
        log.info("Executing installation and compilation actions...")
        __execute_install_compile(paramount_id, install_script=install_script, compile_script=compile_script)

    return paramount

def __execute_install_compile(paramount_id: str, install_script: str = None, compile_script: str = None):
    cluster_module = PlatformFactory.get_module_interface().get_module('cluster')
    repository = ParamountClusterRepositoryOperations()
    paramount = repository.get_paramount(paramount_id)

    if not paramount.is_installed and install_script:
        extra = {
            'paramount_id': paramount_id, 
            'script_install': install_script
        }
        if paramount.execution_dir:
            extra['execution_dir'] = paramount.execution_dir

        log.info("Performing installation using `{}`".format(install_script))
        cluster_module.perform_group_action(paramount.cluster_id, group_name='paramount', action_name='install', extra_args=extra)

    # Check the app is successfully installed
    paramount.is_installed = True
    repository.update_paramount(paramount)

    # Check if app is compiled
    if not paramount.is_compiled and compile_script:
        extra = {
            'paramount_id': paramount_id, 
            'script_compile': compile_script, 
        }
        if paramount.execution_dir:
            extra['execution_dir'] = paramount.execution_dir
        
        log.info("Performing compilation using `{}`".format(compile_script))
        cluster_module.perform_group_action(paramount.cluster_id, group_name='paramount', action_name='compile', extra_args=extra)

    # Check the app is successfully compiled
    paramount.is_compiled = True
    repository.update_paramount(paramount)
    

def run_paramount(  paramount_id: str, 
                    output_result_dir: str,
                    execute_scripts: List[str],
                    execution_dir: str = None,
                    forced_continue: bool = False,
                    at: int = None):
    cluster_module = PlatformFactory.get_module_interface().get_module('cluster')
    repository = ParamountClusterRepositoryOperations()
    paramount = repository.get_paramount(paramount_id)

    for script in execute_scripts:
        if not os.path.exists(script) or not os.path.isfile(script):
            raise Exception("Invalid script at `{}`".format(script))
    
    if at and at not in paramount.node_counts:
        raise Exception("Invalid starting point at `{}`".format(at))

    node_count = paramount.node_counts if not at else paramount.node_counts[paramount.node_counts.at(at):]
    
    # Lets execute the application
    for count in paramount.node_counts:
        log.info("Executing paramount with {} nodes...".format(count))
        if paramount.node_executeds[str(count)]== ParamountState.TERMINATED:
            log.info("Paramount already terminated with {} nodes.. Skipping".format(count))
            continue

        # Resize the cluster...
        cluster_nodes = cluster_module.get_nodes_from_cluster(paramount.cluster_id)
        if len(cluster_nodes) != count:
            log.info("Resizing cluster to have {} nodes...".format(count))
            cluster_module.stop_nodes_from_cluster_by_type(paramount.cluster_id, 
                {'paramount-node-slave': len(cluster_nodes)-count})
            cluster_nodes = cluster_module.get_nodes_from_cluster(paramount.cluster_id)

        # Execute the paramount app
        # Check app with this quantity of nodes is running
        paramount.node_executeds[str(count)]= ParamountState.RUNNING
        repository.update_paramount(paramount)
        extra = {
            'execution_id': '{}-{}-{}-{}'.format(
                paramount.application_name, paramount.node_type, count, time.time()),
            'paramount_id': paramount_id, 
            'output_dir': output_result_dir
        }
        if execution_dir:
            extra['execution_dir'] = execution_dir
        elif paramount.execution_dir:
            extra['execution_dir'] = paramount.execution_dir
        
        faileds =[]
        cluster_module.perform_group_action(paramount.cluster_id, group_name='paramount', action_name='generate-hosts', extra_args=extra)
        for script in execute_scripts:
            extra['execution_id'] = '{}-{}-{}x-{}'.format(int(time.time()), paramount.application_name, count, paramount.node_type)
            extra['script_to_execute'] = script
            log.info("Executing script `{}`".format(script))
            try:
                cluster_module.perform_group_action(paramount.cluster_id, group_name='paramount', action_name='execute', extra_args=extra)
            except BaseException as e:
                log.error("Execution of {} fail... Executing next script".format(script))
                faileds.append(script)

        if faileds:
            log.error("Error executing paramount `{}` with {} nodes".format(paramount_id, count))
            log.error("The following scripts have failed to execute: `{}`".format(faileds))
            if not forced_continue:
                paramount.node_executeds[str(count)]= ParamountState.ERROR
                repository.update_paramount(paramount)
                raise Exception("Failed to execute some scripts with {} nodes".format(count))
            
            log.info("Continuing even so..")
            paramount.node_executeds[str(count)]= ParamountState.SOME_ERROR
            repository.update_paramount(paramount)
        else:
            paramount.node_executeds[str(count)]= ParamountState.TERMINATED
            repository.update_paramount(paramount)



def stop_paramount_cluster(paramount_id: str) -> ParamountClusterData:
    cluster_module = PlatformFactory.get_module_interface().get_module('cluster')
    repository = ParamountClusterRepositoryOperations()
    paramount = repository.get_paramount(paramount_id)
    cluster_module.cluster_stop(paramount.cluster_id)
    repository.remove_paramount(paramount_id)
    return paramount