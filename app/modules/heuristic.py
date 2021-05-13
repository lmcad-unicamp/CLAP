import time
import datetime
import threading
from typing import List, Dict

import click

from common.utils import get_logger, path_extend
from modules.heuristic import HeuristicModule, SpitsQuery, CutHeuristic, BatchReplacementHeuristic, ClusterInstanceManager, Query, Value, DummyInstanceManager
from modules.node import NodeDefaults
from app.module import clap_command
from common.repository import RepositoryController, SQLiteRepository, Repository
from modules.cluster import ClusterModule

logger = get_logger(__name__)

node_defaults = NodeDefaults()

@clap_command
@click.group(help='Perform timed queries')
@click.option('-p', '--platform-db', default=node_defaults.node_repository_path,
              help='Platform database to be used, where nodes will be written', show_default=True)
def heuristic(platform_db):
    node_defaults.node_repository_path = platform_db

@heuristic.command('run')
@click.argument('cluster_id', nargs=1, required=True)
@click.option('-j', '--job', required=True, default=None, type=str, help="Id of the job to query")
@click.option('-m', '--metric', required=True, default=None, type=str, help='Metric to optimize')
@click.option('-n', '--node-type-file', required=True, default=None, type=str, help="Type of instance node to perform cluster setup (Key=val filepath)")
@click.option('-pc', '--percentage', required=True, default=0.5, type=float, show_default=True,  help="Percentage of instances to replace")
@click.option('-i', '--instance_cost_file', required=True, default=None, type=str,  help="Key=val filepath with costs")
@click.option('-p', '--pypits-path', required=False, default=None, type=str, help="Optional pypits directory path")
@click.option('-s', '--spits-job-path', required=False, default=None, type=str, help="Optional spits-job directory path")
def heuristic_run(cluster_id, job, metric, node_type_file, percentage, instance_cost_file, pypits_path, spits_job_path):
    spits_query = SpitsQuery(cluster_id=cluster_id, jobid=job, pypits_path=pypits_path,
                             spits_jobs_path=spits_job_path)
    costs = dict()
    node_types = dict()
    with open(path_extend(instance_cost_file), 'r') as f:
        for line in f.readlines():
            if not line:
                continue
            line = line.strip()
            i_name, i_cost = line.split('=')
            costs[i_name] = float(i_cost)

    with open(path_extend(node_type_file), 'r') as f:
        for line in f.readlines():
            if not line:
                continue
            line = line.strip()
            i_name, i_cost = line.split('=')
            node_types[i_name] = i_cost

    instance_manager = ClusterInstanceManager(cluster_id=cluster_id, instance_node_types=node_types)
    batch_replacement = BatchReplacementHeuristic(cluster_id=cluster_id, instance_manager=instance_manager,
                                                  query_mod=spits_query, instances_cost=costs,
                                                  metric_to_query=metric, percentage=percentage)
    heuristic_module = HeuristicModule.get_module(heuristic=batch_replacement)
    heuristic_module.run()
    return 0


class QueryRepositoryController(RepositoryController):
    def __init__(self, repository: Repository):
        super().__init__(repository)

    @staticmethod
    def metrics_to_dict(metric_values: Dict[str, List[Value]]) -> Dict[str, List[dict]]:
        d = { metric_name: [m.to_dict() for m in metric_values_list]
            for metric_name, metric_values_list in metric_values.items()
        }
        return d

    @staticmethod
    def dict_to_value(metrics_dict: Dict[str, List[dict]]):
        d = { metric_name: [Value.from_dict(m) for m in metric_value_list]
            for metric_name, metric_value_list in metrics_dict.items()
        }
        return d

    def upsert_query(self, query_id: str, metric_values: dict):
        insert_time = time.time()      
        with self.repository.connect('queries') as db:
            serialized_metric_values  = self.metrics_to_dict(metric_values)
            db.upsert(query_id, {'insert_time': insert_time, 'metrics': serialized_metric_values})
            print(f'Inserted query at db with time: {insert_time}')

    def get_query(self, query_id: str):
        with self.repository.connect('queries') as db:
            metrics = db.get(query_id)['metrics']
            return self.dict_to_value(metrics)
    

    def get_all_queries(self, query_id: str) -> Dict[str, Dict[str, List[Value]]]:
        with self.repository.connect('queries') as db:
            d = { query_id: self.dict_to_value(query_values['metrics'])
                for query_id, query_values in db.get_all().items()
            }
            return d

    def get_last(self):
        initial_time = 0.0
        higher = None
        with self.repository.connect('queries') as db:
            for query_id, query_values in db.get_all().items():
                if query_values['insert_time'] > initial_time:
                    higher = query_values['metrics']
                    initial_time = query_values['insert_time']
                
        return self.dict_to_value(higher) if higher else None



def queryier(query_obj: Query, repository: QueryRepositoryController, metrics: list = None, query_time: float = 40.0):
    next_call = time.time()
    cluster_module = ClusterModule.get_module()
    
    while True:
        try:
            query_time_start = time.time()
            metric_values = query_obj.query(metrics=metrics)
            query_time_end = time.time()
            print(f'Query time: {query_time_end-query_time_start}...')
            next_call += query_time
            repository.upsert_query(f"query-{time.time()}", metric_values)
            time.sleep(next_call - time.time())
        except Exception as e:
            logger.error(e)
            time.sleep(query_time)

def fetcher(cluster_id: str, save_location: str, save_destination: str, jobid: str, interval: float = 60.0):
    next_call = time.time()
    cluster_module = ClusterModule.get_module()
    
    while True:
        try:
            print(f"[{datetime.datetime.now()}] Fetching files...")
            cluster_module.group_action(cluster_id, group_name='commands-common', action='fetch', extra_args={'src': save_location, 'dest': save_destination})
            next_call += interval
            time.sleep(next_call - time.time())
        except Exception as e:
            logger.error(e)
            time.sleep(interval)
       

if __name__ == '__main__':
    import sys
    import json

    cluster_id = sys.argv[1]
    job_id = sys.argv[2]
    pypits = sys.argv[3]
    spits_jobs = sys.argv[4]

    repository = SQLiteRepository('/home/lopani/temp/queries.db') 
    repository_op = QueryRepositoryController(repository)

    spits_query = SpitsQuery(cluster_id=cluster_id, jobid=job_id, pypits_path=pypits,
                             spits_jobs_path=spits_jobs)

    timerThread = threading.Thread(target=queryier, args=(spits_query, repository_op))
    timerThread.daemon = True
    timerThread.start()

    fetcherThread = threading.Thread(target=fetcher, args=(cluster_id, f'{spits_jobs}/{job_id}/logs', '/home/lopani/temp/logs/{{ inventory_hostname }}', job_id))
    fetcherThread.daemon = True
    fetcherThread.start()
   
    instances_cost = {
        'spits-worker-instance-aws-g4dn.xlarge': 0.526, 
        'spits-worker-instance-aws-g4dn.2xlarge': 0.752,
        'spits-worker-instance-aws-g4dn.4xlarge': 1.204,
        'spits-worker-instance-aws-g3.4xlarge': 1.14,
        'spits-worker-instance-aws-g3s.xlarge': 0.75,
        'spits-worker-instance-aws-p3.2xlarge': 3.06,
        'spits-worker-instance-aws-p2.xlarge': 0.90
        
    }

    instance_cluster_types = {
        'spits-worker-instance-aws-g4dn.xlarge': 'spits-taskmanager-g4dn.xlarge',
        'spits-worker-instance-aws-g4dn.2xlarge': 'spits-taskmanager-g4dn.2xlarge',
        'spits-worker-instance-aws-g4dn.4xlarge': 'spits-taskmanager-g4dn.4xlarge',
        'spits-worker-instance-aws-g3.4xlarge': 'spits-taskmanager-g3.4xlarge',
        'spits-worker-instance-aws-g3s.xlarge': 'spits-taskmanager-g3s.xlarge',
        'spits-worker-instance-aws-p3.2xlarge': 'spits-taskmanager-p3.2xlarge',
        'spits-worker-instance-aws-p2.xlarge': 'spits-taskmanager-p2' 
    }

    dummy_instance_manager = DummyInstanceManager(cluster_id, None)
    instance_manager = ClusterInstanceManager(cluster_id, instance_cluster_types, f'{spits_jobs}/{job_id}/logs', '/home/lopani/temp/logs/{{ inventory_hostname }}', jobid=job_id)

    cut_heuristic = CutHeuristic(cluster_id, instance_manager, instances_cost, 'interpolations_per_sec', 4, '/home/lopani/temp/cut.txt')
    batch_heuristic = BatchReplacementHeuristic(cluster_id, instance_manager, instances_cost, 'interpolations_per_sec', 0.50, '/home/lopani/temp/batch.txt')

    initial_time = time.time()
    while True:
        if time.time() - initial_time > 60.0:
            last_value = repository_op.get_last()
            if last_value:
                print("Executing CUT....")
                if cut_heuristic.run(last_value):
                    break
                initial_time = time.time()
        time.sleep(1)


    initial_time = time.time()
    while True:
        if time.time() - initial_time > 60.0:
            last_value = repository_op.get_last()
            if last_value:
                print("Executing BATCH_REPLACEMENT")
                batch_heuristic.run(last_value)
                initial_time = time.time()

        time.sleep(1)