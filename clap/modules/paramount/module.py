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

def create_paramount_cluster(app_name: str, node_type: str, node_counts: List[int]) -> ParamountClusterData:
    cluster_module = PlatformFactory.get_module_interface().get_module('cluster')
    repository = ParamountClusterRepositoryOperations()
    max_count = max(node_counts)

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
    cluster_module.perform_group_action(cluster_id=cluster.cluster_id, group_name='paramount', 
            action_name='setup-paramount-job', extra_args={'paramount_id': paramount.paramount_id})
    return paramount

def setup_paramount_cluster_efs(paramount_id: str, 
                            execution_dir: str = None,
                            mount_ip: str = None,
                            mount_dir: str = None):
    pass

def setup_paramout_cluster( paramount_id: str, 
                            execution_dir: str = None,
                            app_dir: str = None) -> ParamountClusterData:
    cluster_module = PlatformFactory.get_module_interface().get_module('cluster')
    repository = ParamountClusterRepositoryOperations()
    paramount = repository.get_paramount(paramount_id)
    cluster_module.perform_group_action(paramount.cluster_id, group_name='paramount', action_name='setup-paramount-job', 
            extra_args={'paramount_id': paramount_id, 'execution_dir': execution_dir, 'app_dir': app_dir})
    paramount.execution_dir = execution_dir
    paramount.is_setup = True
    paramount.use_shared_fs = False
    repository.update_paramount(paramount)
    return paramount
    

def run_paramount(  paramount_id: str, 
                    output_result_dir: str,
                    install_script: str, 
                    compile_script: str, 
                    execute_script: str, 
                    install_script_args: str = '', 
                    compile_script_args: str = '', 
                    execute_script_args: str= '', ):
    cluster_module = PlatformFactory.get_module_interface().get_module('cluster')
    repository = ParamountClusterRepositoryOperations()
    paramount = repository.get_paramount(paramount_id)

    if execute_script is None:
        raise Exception("No execution script provided!")

    for script in [install_script, compile_script, execute_script]:
        if not script:
            continue
        if not os.path.exists(script) or not os.path.isfile(script):
            raise Exception("Invalid script at `{}`".format(script))
    
    if not paramount.is_setup and install_script:
        extra = {
            'paramount_id': paramount_id, 
            'script_install': install_script, 
            'script_install_extra': install_script_args,
            'execution_dir': paramount.execution_dir
        }
        cluster_module.perform_group_action(paramount.cluster_id, group_name='paramount', action_name='install', extra_args=extra)
    paramount.is_setup = True
    repository.update_paramount(paramount)

    if not paramount.is_compiled and compile_script:
        extra = {
            'paramount_id': paramount_id, 
            'script_compile': compile_script, 
            'script_compile_extra': compile_script_args,
            'execution_dir': paramount.execution_dir
        }
        cluster_module.perform_group_action(paramount.cluster_id, group_name='paramount', action_name='compile', extra_args=extra)
    paramount.is_compiled = True
    repository.update_paramount(paramount)

    for count in paramount.node_counts:
        log.info("Executing paramount with {} nodes...".format(count))
        if paramount.node_executeds[count] == ParamountState.TERMINATED:
            log.info("Paramount already terminated with {} nodes.. Skipping".format(count))
            continue

        cluster_nodes = cluster_module.get_nodes_from_cluster(paramount.cluster_id)
        if len(cluster_nodes) != count:
            log.info("Resizing cluster to have {} nodes...".format(count))
            cluster_module.stop_nodes_from_cluster_by_type(paramount.cluster_id, 
                {'paramount-node': len(cluster_nodes)-count})
            cluster_nodes = cluster_module.get_nodes_from_cluster(paramount.cluster_id)

        try:
            paramount.node_executeds[count] = ParamountState.RUNNING
            repository.update_paramount(paramount)
            extra = {
                'execution_id': '{}-{}-{}-{}'.format(
                    paramount.application_name, paramount.node_type, count, time.time()),
                'paramount_id': paramount_id, 
                'script_execute': execute_script, 
                'script_execute_extra': execute_script_args,
                'execution_dir': paramount.execution_dir
            }
            cluster_module.perform_group_action(paramount.cluster_id, group_name='paramount', action_name='compile', extra_args=extra)
            paramount.node_executeds[count] = ParamountState.TERMINATED
            repository.update_paramount(paramount)

        except BaseException:
            log.error("Error executing paramount {} with {} nodes".format(paramount_id, count))
            paramount.node_executeds[count] = ParamountState.ERROR
            repository.update_paramount(paramount)
            raise

        try:
            extra = {
                'paramount_id': paramount_id, 
                'execution_dir': paramount.execution_dir,
                'output_dir': output_result_dir
            }
            cluster_module.perform_group_action(paramount.cluster_id, group_name='paramount', action_name='get-results', extra_args=extra)
        except BaseException:
            log.error("Error fetching resuts from nodes....")
            raise

