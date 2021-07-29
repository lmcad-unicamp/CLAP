import logging
import os
import time
import click
import json
from collections import defaultdict
from collections import deque
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Deque

from clap.executor import SSHCommandExecutor
from clap.utils import yaml_load, path_extend, get_logger
from app.cli.cliapp import clap_command
from app.cli.modules.node import get_node_manager, get_config_db
from app.cli.modules.role import get_role_manager
from app.cli.modules.cluster import get_cluster_config_db, get_cluster_manager

logger = get_logger(__name__)

# Get configuration templates of instances (instances.yaml) and
# clusters (~/.clap/configs/clusters)
instances_configuration = get_config_db()
clusters_configuration = get_cluster_config_db()

# Get node, role and cluster managers
node_manager = get_node_manager()
role_manager = get_role_manager()
cluster_manager = get_cluster_manager()

is_running: bool = False


# Class Reporter
# You must implement these 3 methods as specified in the document
class Reporter:
    @dataclass
    class ManagerMetrics:
        node_id: str
        instance_config_id: str
        cnode_type: str
        manager_type: str
        pid_file: str
        retrieve_time: float
        metrics: dict = field(default_factory=dict)

    def __init__(self, cluster_id: str, jobid: str, metric_output_dir: str,
                 deque_size: int = 1000):
        self.cluster_id = cluster_id
        self.jobid = jobid
        self.metric_dir = metric_output_dir
        self.metrics: Deque[List[Reporter.ManagerMetrics]] = deque(maxlen=deque_size)
        self.jm_terminated = False
        self.jm_job_command = ''
        self.execution_timeout = 30
        self.last_execution = 0.0

    '''
    Example of retuned status dict:
{
    "TM-napoli-System-Product-Name-779756.pid": {       --> Optional
        "metrics": {...}
        "ok": true
    },

    "jm.pid": {                                         --> Optional
        "metrics": {...}
        "ok": true
    },

    "status": {
        "code": 0.0,
        "finished": false,
        "job": "bin/spitz_de --aph 1000 --apm 150 --thread-count 64 ...",
        "status": "Maybe Running"
    }
}

Will be appended as (one for each metric PID/worker): 
[
[
    {
        node: nodeid,
        instance_config_id: id of the node's instance config
        cnode_type: type of node of cluster
        manager_type: taskmanager of jobmanager
        metrics: {...}
        retrieve_time: timestamp of when metric is got
        pid_name: pid file name
    }, 
    {
    }, ...
], 
[{}, {}, {}, ...
], ...
]
    '''

    def get_metrics(self):
        cmd = f'~/spits-2.0/runtime/pypits/spits-job-status.py {self.jobid}'
        cnode_ids = cluster_manager.get_all_cluster_nodes(self.cluster_id)
        cnodes = node_manager.get_nodes_by_id(cnode_ids)
        cnode_types = cluster_manager.get_cluster_nodes_types(self.cluster_id)
        ssh_command = SSHCommandExecutor(
            cmd, cnodes, node_manager.private_path,
            execution_timeout=self.execution_timeout)
        results = ssh_command.run()
        run_date = time.time()
        metrics = []

        def _cluster_node_type(nid):
            nonlocal cnode_types
            for ntype, nlist in cnode_types.items():
                if nid in nlist:
                    return ntype

        def _node_instance_id(nid):
            nonlocal cnodes
            node = [n for n in cnodes if nid == n.node_id][0]
            return node.configuration.instance.instance_config_id

        for node_id, result in results.items():
            cnode_t = _cluster_node_type(node_id)
            instance_config_id = _node_instance_id(node_id)

            if not result.ok:
                logger.error(f"Node `{node_id}` does not executed successfully")
                continue
            if result.ret_code != 0:
                # TODO may print stderr and stdout?
                logger.error(f"Error executing command `{cmd} in node `{node_id}` "
                             f"(ret code: {result.ret_code}).")
                continue

            # Join lines and transform to dict
            results_json = '\n'.join(result.stdout_lines)
            metrics_dict = json.loads(results_json)

            # Loop though each Manager
            for pidfile, manager_values in metrics_dict.items():
                if pidfile == 'status':
                    if cnode_t != 'jobmanager':
                        continue
                    # Read status from jobmanager node type
                    self.jm_terminated = manager_values['finished']
                    self.jm_job_command = manager_values['job']
                    continue

                if not manager_values['ok']:
                    logger.error(f'{pidfile} at {node_id} does not executed '
                                 f'successfully...')
                    logger.error(f'Error: {manager_values["error"]}')
                    logger.error(f'Trace: {manager_values["trace"]}')
                    continue

                m = Reporter.ManagerMetrics(
                    node_id, instance_config_id, cnode_t,
                    manager_values['metrics']['type'], pidfile, run_date,
                    manager_values['metrics']
                )
                metrics.append(m)

        metric_file = path_extend(self.metric_dir, str(run_date) + '.metrics.json')
        with open(metric_file, 'w') as f:
            metrics_dict = [asdict(m) for m in metrics]
            json.dump(metrics_dict, f, indent=4, sort_keys=True)
            logger.info(f"Metrics are saved to file: {metric_file}")

        self.metrics.append(metrics)

    def get_interpolation_by(self, records: int = None, by: str = 'node') -> \
            Dict[str, List[float]]:
        bys = ('node', 'cluster_node', 'instance_config')
        if by not in bys:
            raise ValueError(f"Get interpolation by must be one of: {bys}")
        if not records:
            records = len(self.metrics)
        else:
            records = max(len(self.metrics), records)

        interpolations_by: Dict[str, List[float]] = defaultdict(list)

        for i in range(1, records + 1):
            for pid_metric in self.metrics[-i]:
                if 'interpolations_per_sec' not in pid_metric.metrics:
                    continue
                interpolations = [
                    m['value']
                    for m in pid_metric.metrics['interpolations_per_sec']['values']
                ]
                if len(interpolations) > 0:
                    if by == 'node':
                        interpolations_by[pid_metric.node_id] += \
                            interpolations
                    elif by == 'cluster_node':
                        interpolations_by[pid_metric.cnode_type] += \
                            interpolations
                    else:
                        interpolations_by[pid_metric.instance_config_id] += \
                            interpolations

        return interpolations_by

    def get_aggregated_interpolation_by_node_id(self, records: int = None) -> \
            Dict[str, float]:
        interpolations = self.get_interpolation_by(records, by='node')
        return {
            node_id: sum(mlist) / len(mlist)
            for node_id, mlist in interpolations.items() if len(mlist) > 0
        }

    def get_aggregated_interpolation_by_cluster_node(self, records: int = None) -> \
            Dict[str, float]:
        interpolations = self.get_interpolation_by(records, by='cluster_node')
        return {
            node_id: sum(mlist) / len(mlist)
            for node_id, mlist in interpolations.items() if len(mlist) > 0
        }

    def get_aggregated_interpolation_by_instance_config(self, records: int = None) -> \
            Dict[str, float]:
        interpolations = self.get_interpolation_by(records, by='instance_config')
        return {
            node_id: sum(mlist) / len(mlist)
            for node_id, mlist in interpolations.items() if len(mlist) > 0
        }

    def terminated(self) -> bool:
        return self.jm_terminated

    def fetch_results(self, output_dir: str):
        node_ids = cluster_manager.get_all_cluster_nodes(self.cluster_id)
        spits_nodes = role_manager.get_all_role_nodes_hosts('spits')
        nodes_to_execute = {}
        for host_name, host_nodes in spits_nodes.items():
            _nodes = [node for node in host_nodes if node in node_ids]
            if len(_nodes) > 0:
                nodes_to_execute[host_name] = _nodes

        if not nodes_to_execute:
            print("No nodes to execute...")
            return {}

        extra = {
            'jobid': self.jobid,
            'output_dir': output_dir
        }
        result = role_manager.perform_action(
            'spits', action_name='fetch', hosts_node_map=nodes_to_execute,
            extra_args=extra)
        return result.ok


# For Batch Replacement algorithm set cut_num and replace_num to 0
class CutBatchReplacementPolicy:
    def __init__(self, cluster_id: str, jobid: str, desired_num: int,
                 cut_num: int, replace_num: int):
        self.cluster_id = cluster_id
        self.jobid = jobid
        self.desired_num = desired_num
        self.cut_num = cut_num
        self.replace_num = replace_num
        self.execution_times = 0

    def run(self, metrics: Dict[str, float], log_obj) -> bool:
        log_obj.debug("[OPTIMIZER] Cut Batch Replacement started!")
        log_obj.debug(f"[OPTIMIZER] Received metrics: {metrics}")
        node_types = []

        if self.execution_times == 0:
            nodes_to_stop = []
            for node in node_manager.get_nodes_by_id(cluster_manager.get_all_cluster_nodes(self.cluster_id)):
                if 'g4dn.xlarge' not in node.configuration.instance.flavor and 't2' not in node.configuration.instance.flavor:
                    nodes_to_stop.append(node.node_id)
            print(f"N TO STO: {nodes_to_stop}")
            start = time.time()
            node_ids = cluster_manager.grow(self.cluster_id, 'taskmanager-g4dn.xlarge', 2, 2)
            end = time.time()
            for nid in node_ids:
                log_obj.debug(f"[START] ID: {nid}. Type: taskmanager-g4dn.xlarge. Time: {end - start}")
            start = time.time()
            cluster_manager.setup_cluster(
                self.cluster_id, nodes_being_added={'taskmanager-g4dn.xlarge': node_ids})
            end = time.time()
            for nid in node_ids:
                log_obj.debug(f"[SETUP] ID: {nid}. Type: taskmanager-g4dn.xlarge. Time: {end - start}")

            stopped_nodes = node_manager.stop_nodes(nodes_to_stop)
            for nid in stopped_nodes:
                log_obj.debug(f"[STOP] Node {nid} stopped")

            # Just to remove unused nodes...
            cluster_manager.setup_cluster(self.cluster_id, start_at_stage='after')
            self.execution_times += 1
            return True
        else:
            log_obj.debug(f"[Optimizer] Cluster is homogeneous")
            return False

        for cnode_t, nlist in cluster_manager.get_cluster_nodes_types(self.cluster_id).items():
            if 'jobmanager' in cnode_t:
                continue
            for nid in nlist:
                if nid not in metrics:
                    log_obj.debug(f"[OPTIMIZER] No metrics for {nid} yet...")
                    return False
                node_types.append((cnode_t, nid, metrics[nid]))

        # Sort by performance
        node_types = sorted(node_types, key=lambda x: x[2], reverse=False)

        # Must cut?
        if len(node_types) > self.desired_num:
            max_removed = len(node_types) - self.desired_num
            to_remove = min(max_removed, self.cut_num)
            node_to_stop = [n[1] for n in node_types[:to_remove]]
            stopped_nodes = node_manager.stop_nodes(node_to_stop)
            for nid in stopped_nodes:
                log_obj.debug(f"[STOP] Node {nid} stopped")
            # Just to remove unused nodes
            cluster_manager.setup_cluster(self.cluster_id, start_at_stage='after')
            return True

        # Is homogeneous?
        if node_types[0][0] == node_types[-1][0]:
            log_obj.debug(f"[Optimizer] Cluster is homogeneous")
            return False

        # Best one...
        best_type, best_node, best_performance = node_types[-1]
        nodes_to_stop = []
        num_to_start = 0
        for i in range(self.replace_num):
            if node_types[i][0] == best_type:
                break
            nodes_to_stop.append(node_types[i][1])
            num_to_start += 1

        if num_to_start > 0:
            log_obj.debug(f"Starting {num_to_start} nodes of type {best_type}")
            start = time.time()
            started_nodes = cluster_manager.grow(
                self.cluster_id, best_type, num_to_start, min_count=num_to_start)
            end = time.time()

            if not started_nodes:
                log_obj.error(f"Error starting {num_to_start} nodes of type {best_type}")
                return False

            for nid in started_nodes:
                log_obj.debug(f"[START] ID: {nid}. Type: {best_type}. Time: {end - start}")

            start = time.time()
            cluster_manager.setup_cluster(
                self.cluster_id, nodes_being_added={best_type: started_nodes})
            end = time.time()

            for nid in started_nodes:
                log_obj.debug(f"[SETUP] ID: {nid}. Type: {best_type}. Time: {end - start}")

            stopped_nodes = node_manager.stop_nodes(nodes_to_stop)
            for nid in stopped_nodes:
                log_obj.debug(f"[STOP] Node {nid} stopped")

            # Just to remove unused nodes...
            cluster_manager.setup_cluster(self.cluster_id, start_at_stage='after')
            return True
        else:
            log_obj.debug("No nodes to start")
            return False


def get_optimizer_logger(filename: str):
    formatter = logging.Formatter('%(asctime)s: %(message)s')
    _logger = get_logger('optimizer')
    _logger.setLevel(logging.DEBUG)
    fh = logging.FileHandler(filename)
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)
    _logger.addHandler(fh)
    return _logger


# Function used to dynamic optimization
def optimize_it(jobid: str, vm_price_file: str, cluster_id: str,
                root_dir: str, report_time: int = 60, policy_time: int = 60) -> int:
    last_report = 0.0
    last_opt_run = time.time()

    # -------- Create experiments directory --------
    experiment_dir = path_extend(root_dir, jobid, str(int(time.time())))
    app_results_dir = path_extend(experiment_dir, 'app_results')
    optimizer_logs_dir = path_extend(experiment_dir, 'optimizer_logs')
    metrics_dir = path_extend(experiment_dir, 'metrics_dir')
    os.makedirs(app_results_dir, exist_ok=True)
    os.makedirs(optimizer_logs_dir, exist_ok=True)
    os.makedirs(metrics_dir, exist_ok=True)

    # -------- Get reporter and optimizer objects --------
    reporter_obj = Reporter(cluster_id, jobid, metrics_dir)
    optimizer_obj = CutBatchReplacementPolicy(
        cluster_id, jobid, desired_num=7, cut_num=0, replace_num=0)

    # -------- Logger ---------
    opt_filename = path_extend(optimizer_logs_dir, f'{time.time()}.txt')
    optimizer_logger = get_optimizer_logger(opt_filename)
    optimizer_logger.debug("Hello!")
    print_str = f"Cluster ID: {cluster_id}, Job ID: {jobid}, VM Price File: {vm_price_file}, " \
                f"APP Result Dir: {app_results_dir}, Optimizer Logs Dir: {optimizer_logs_dir} " \
                f"Metrics Dir: {metrics_dir}"
    optimizer_logger.debug(print_str)
    print(print_str)
    cluster_nodes = cluster_manager.get_all_cluster_nodes(cluster_id)
    for node in node_manager.get_nodes_by_id(cluster_nodes):
        optimizer_logger.debug(
            f"[START] Node: {node.node_id}, created at: {node.creation_time}, "
            f"instance config: {node.configuration.instance.instance_config_id}")

    def _cluster_node_type(cnode_types, nid):
        for ntype, nlist in cnode_types.items():
            if nid in nlist:
                return ntype
        return None

    # Continue until application terminates
    while not reporter_obj.terminated():
        if time.time() - last_report > report_time:
            optimizer_logger.debug("[METRICS START] Start running metrics")
            reporter_obj.get_metrics()
            optimizer_logger.debug("[METRICS END] Metrics get")
            last_report = time.time()

        if time.time() - last_opt_run > policy_time:
            # TODO this should not be specific
            metrics = reporter_obj.get_aggregated_interpolation_by_node_id()
            print(metrics)
            prices = yaml_load(vm_price_file)
            interpolations_per_dollar = {}
            cluster_node_ids = cluster_manager.get_all_cluster_nodes(cluster_id)
            for node_id, value in metrics.items():
                if node_id not in cluster_node_ids:
                    logger.debug(f"Skipping node `{node_id}`. It was not alive anymore!")
                    continue
                cnode_t = _cluster_node_type(
                    cluster_manager.get_cluster_nodes_types(cluster_id), node_id)
                interpolations_per_dollar[node_id] = value / prices[cnode_t]
            optimizer_logger.debug("[POLICY START] Starting policy run")
            optimizer_obj.run(interpolations_per_dollar, optimizer_logger)
            optimizer_logger.debug("[POLICY END] Policy end")
            last_opt_run = time.time()

        time.sleep(1)

    optimizer_logger.debug("Application finished!")
    ok = reporter_obj.fetch_results(app_results_dir)
    if ok:
        optimizer_logger.debug(f"Results saved to {app_results_dir}")
    else:
        optimizer_logger.debug(f"Error fetching results")
    optimizer_logger.debug("Bye!")
    print("Application Finished!")
    return 0


# Command-line interface
@clap_command
@click.group(help='Control and manage cluster of nodes using optimizer')
def bot():
    pass


@bot.command('optimizer-recipe')
@click.option('--policy', default='cut', show_default=True,
              type=str, required=False, help='In use policy (cut)')
@click.option('-j', '--jobid', default=None, show_default=False,
              type=str, required=True, help="Job ID")
@click.option('-v', '--vm-price', default=None, show_default=False,
              type=str, required=True,
              help='Path to the YAML file with the price of the VMs')
@click.option('-c', '--cluster-id', default=None, show_default=False,
              type=str, required=False,
              help="Id of the cluster running the application")
@click.option('-r', '--root-dir', default='.', show_default=False,
              type=str, required=False,
              help='Root directory where experiment directories will be created')
@click.option('-rt', '--report-time', default=30, show_default=True,
              type=int, required=False,
              help='Time to wait before calling reporter')
@click.option('-pt', '--policy-time', default=60, show_default=True,
              type=int, required=False,
              help='Time to wait before calling policy')
def bot_run(policy: str, jobid: str, vm_price: str, cluster_id: str,
            root_dir: str, report_time: int, policy_time: int):
    if policy == 'cut':
        return optimize_it(jobid, vm_price, cluster_id, root_dir, report_time, policy_time)
    else:
        raise ValueError(f"Invalid policy {policy}")
