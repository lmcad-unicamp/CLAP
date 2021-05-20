import time
import numpy
import datetime
import yaml

from itertools import groupby
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, asdict, field
from typing import Dict, Any, List, Tuple, Type

from common.abstract_provider import AbstractModule
from common.configs import InstanceInfo
from common.utils import defaultdict_to_dict, get_logger
from modules.cluster import ClusterModule
from modules.node import NodeModule
from modules.spits import SpitsModule

class Heuristic:
    name: str = 'heuristic'
    version = '0.1.0'
    daemon: bool = False

    @abstractmethod
    def run(self, values, *args, **kwargs):
        pass


class InstanceManager(ABC):
    @abstractmethod
    def start(self, instances_count: List[Tuple[InstanceInfo, int]]) -> List[str]:
        pass

    @abstractmethod
    def setup(self, node_ids: List[str]) -> List[str]:
        pass

    @abstractmethod
    def stop(self, node_ids: List[str]):
        pass

    @abstractmethod
    def get_nodes(self) -> List[str]:
        pass

class ClusterInstanceManager(InstanceManager):
    def __init__(self, cluster_id: str, instance_node_types: Dict[str, str], save_location: str, save_destination: str, jobid: str, setup_at: str = 'before_all'):
        self.cluster_id = cluster_id
        self.node_module = NodeModule.get_module()
        self.cluster_module = ClusterModule.get_module()
        self.instance_node_types = instance_node_types
        self.setup_at = setup_at
        self.save_location = save_location
        self.save_destination = save_destination
        self.jobid = jobid

    def start(self, instances_count: List[Tuple[InstanceInfo, int]]) -> List[str]:
        return self.node_module.start_nodes_by_instance_descriptor(instances_count)

    def setup(self, node_ids: List[str]) -> List[str]:
        node_types = defaultdict(list)
        for node in self.node_module.get_nodes_by_id(node_ids):
            node_types[self.instance_node_types[node.configuration.instance.instance_config_id]].append(node.node_id)
        node_types = dict(node_types)
        self.cluster_module.add_existing_node_to_cluster(self.cluster_id, node_types)
        self.cluster_module.cluster_setup(self.cluster_id, node_types, at=self.setup_at)
        return node_ids

    def stop(self, node_ids: List[str]):
        self.cluster_module.group_action(self.cluster_id, group_name='commands-common', action='fetch', extra_args={'src': self.save_location, 'dest': self.save_destination})
        self.node_module.stop_nodes(node_ids=node_ids)
        self.cluster_module.group_action(self.cluster_id, group_name='spits', action='add-nodes', extra_args={'jobid': self.jobid})

    def get_nodes(self) -> List[str]:
        return self.cluster_module.get_nodes_from_cluster(self.cluster_id)

class DummyInstanceManager(InstanceManager):
    def __init__(self, cluster_id: str, instance_node_types: Dict[str, str], setup_at: str = 'before_all'):
        self.cluster_id = cluster_id
        self.node_module = NodeModule.get_module()
        self.cluster_module = ClusterModule.get_module()
        self.instance_node_types = instance_node_types
        self.setup_at = setup_at

    def start(self, instances_count: List[Tuple[InstanceInfo, int]]) -> List[str]:
        print(f"Started nodes: {instances_count}")
        no_nodes = sum([i[1] for i in instances_count])
        return [f"znode-{i}" for i in range(0, no_nodes)]

    def setup(self, node_ids: List[str]) -> List[str]:
        print(f"Setup: {node_ids}")
        return node_ids

    def stop(self, node_ids: List[str]):
        print(f"Stop: {node_ids}")

    def get_nodes(self) -> List[str]:
        return self.cluster_module.get_nodes_from_cluster(self.cluster_id)


class CutHeuristic(Heuristic):
    import json
    name: str = 'cut_heuristic'
    version = '0.1.0'
    daemon = False

    @dataclass
    class NodeCost:
        instance_config_id: str
        node_mean: float
        node_std: float
        node_id: str = None

        def __eq__(self, other):
            return other.node_id == self.node_id and other.instance_config_id == self.instance_config_id

    def __init__(self, cluster_id: str, instance_manager: InstanceManager, 
                 instances_cost: Dict[str, float], metric_to_query: str, target: float, output_file: str):
        self.cluster_id = cluster_id
        self.instance_manager = instance_manager
        self.instances_cost = instances_cost
        self.metric_to_query = metric_to_query
        self.target = target
        self.node_module = NodeModule.get_module()
        self.cluster_module = ClusterModule.get_module()
        self.output_file = output_file

    def run(self, values: Dict[str, List[Value]]):
        metrics = values[self.metric_to_query]
        nodes_cost = dict()
        cluster_nodes = self.cluster_module.get_nodes_from_cluster(self.cluster_id)

        file_output = open(self.output_file, 'a')
        file_output.write(f"CUT started at: {datetime.datetime.now()}\n")
        file_output.write(f"No. instances: {len(cluster_nodes)-1}; target: {self.target}\n")

        for instance_id, metric_list in groupby(metrics, key=lambda x: x.instance_config_id):
            metric_list = list(metric_list)
            instance = self.node_module.get_instance_descriptor(instance_id)
            i_conf = instance.instance.instance_config_id
            cost = self.instances_cost[i_conf]
            
            for node in self.node_module.get_nodes_by_id(cluster_nodes):
                if node.configuration.instance.instance_config_id != instance_id:
                    continue
                node_values = [metric.value for metric in metric_list if metric.node_id == node.node_id]
                if node_values:
                    print(f"[CUT] Node {node.node_id} has values={node_values} and cost={cost}")
                    nodes_cost[node.node_id] = numpy.mean(node_values)/cost
                    file_output.write(f"[{datetime.datetime.now()}] Node {node.node_id}, instance_type: {node.configuration.instance.instance_config_id}, metric_values: {node_values}, cost: {cost}, metric/cost: {numpy.mean(node_values)/cost}\n")
        

        interp = sorted([(k, v) for k, v in nodes_cost.items()], key=lambda x: x[1])
        print(f"[CUT] Values: {self.json.dumps(nodes_cost, indent=4, sort_keys=True)}")
        print(f"[CUT] Sorted: {interp}")
        no_nodes_to_cut = len(cluster_nodes)-self.target-1

        if (len(interp) != len(cluster_nodes)-1):
            file_output.write("Skipping... Number of TMs and number of metrics values mismatch....\n")
            file_output.write(f"Finished with error at {datetime.datetime.now()}")
            file_output.close()
            return False

        nodes_to_stop = [n[0] for n in interp[:no_nodes_to_cut]]
        print(f"[CUT] Stopping nodes: {nodes_to_stop}")
        file_output.write(f"Stopping {len(nodes_to_stop)} nodes: {nodes_to_stop}\n")
        start_time = time.time()
        if nodes_to_stop:
            self.instance_manager.stop(nodes_to_stop)
        end_time = time.time()
        file_output.write(f"Finished at {datetime.datetime.now()}. Stop instances time: {end_time-start_time}")

        file_output.close()
        return True


class BatchReplacementHeuristic(Heuristic):
    name: str = 'batch_replacement'
    version = '0.1.0'
    daemon = False

    @dataclass
    class NodeCost:
        instance_config_id: str
        node_mean: float
        node_std: float
        node_interpolation: float
        node_cost: float
        node_id: str = None

        def __eq__(self, other):
            return other.node_id == self.node_id and other.instance_config_id == self.instance_config_id

    def __init__(self, cluster_id: str, instance_manager: InstanceManager,
                 instances_cost: Dict[str, float], metric_to_query: str, percentage: float, output_file: str):
        self.cluster_id = cluster_id
        self.instance_manager = instance_manager
        self.instances_cost = instances_cost
        self.metric_to_query = metric_to_query
        self.percentage = percentage
        self.node_module = NodeModule.get_module()
        self.cluster_module = ClusterModule.get_module()
        self.output_file = output_file

    def run(self, values: Dict[str, List[Value]]):
        L_all = []
        L_cur = []
        i = 0

        file_output = open(self.output_file, 'a')
        file_output.write(f"Batch Replacement started at {datetime.datetime.now()}\n")

        metrics = values[self.metric_to_query]
        instance_means = dict()
        instance_stddev = dict()
        replaces = 0
        cluster_nodes = self.cluster_module.get_nodes_from_cluster(self.cluster_id)

        for instance_id, metric_list in groupby(metrics, key=lambda x: x.instance_config_id):
            metric_list = list(metric_list)
            instance = self.node_module.get_instance_descriptor(instance_id)
            instances_with_same_flavor = [self.node_module.get_instance_descriptor(instance_id)
                                          for instance_id in self.instances_cost.keys()]
            instances_with_same_flavor = [i for i in instances_with_same_flavor
                                          if i.instance.flavor == instance.instance.flavor]
            values = [value.value for value in metric_list]
            for i in instances_with_same_flavor:
                i_conf = i.instance.instance_config_id
                instance_means[i_conf] = numpy.mean(values)/self.instances_cost[i_conf]
                instance_stddev[i_conf] = numpy.std(values)/self.instances_cost[i_conf]

                nodes_with_flavor = [metric.node_id for metric in metric_list
                                     if metric.instance_config_id == i_conf and metric.node_id]
                nodes_with_flavor = [nid for nid in self.instance_manager.get_nodes() if nid in nodes_with_flavor]

                if not nodes_with_flavor:
                    L_all.append(BatchReplacementHeuristic.NodeCost(
                        instance_config_id=i_conf, node_mean=instance_means[i_conf], node_std=instance_stddev[i_conf]))
                    continue

                for node_id in nodes_with_flavor:
                    c = BatchReplacementHeuristic.NodeCost(
                        instance_config_id=i_conf, node_id=node_id, node_mean=instance_means[i_conf], node_interpolation=numpy.mean(values), 
                        node_cost=self.instances_cost[i_conf], node_std=instance_stddev[i_conf])
                    L_all.append(c)
                    L_cur.append(c)

        L_all = list(reversed(sorted(L_all, key=lambda x: x.node_mean)))
        L_cur = sorted(L_cur, key=lambda x: x.node_mean)

        print(f'[BATCH_REPLACEMENT {datetime.datetime.now()}] -----------ALL------------')
        for x in L_all:
            print(x)
            print()
            file_output.write(f"[{datetime.datetime.now()}] Node: {x.node_id}, instance: {x.instance_config_id}, metric: {x.node_interpolation}, cost: {x.node_cost}, metric/cost: {x.node_mean}\n")

        print(f'[BATCH_REPLACEMENT {datetime.datetime.now()}] -----------CUR------------')
        for x in L_cur:
            print(x)
            print()
        print(f'[BATCH_REPLACEMENT {datetime.datetime.now()}] -----------------------')


        if (len(L_cur) != len(cluster_nodes)-1):
            file_output.write(f"Skipping... Number of TMs and metric values mismatch\n")
            file_output.close()
            return False

        i, j, lim = 0, 0, max((len(self.instance_manager.get_nodes())-1) * self.percentage, 1)
        
        while i < len(L_cur) * self.percentage:
            if L_cur[i] != L_all[j]:
                node_cost = L_cur[i].node_mean + L_cur[i].node_std
                best_cost = L_all[j].node_mean - L_all[j].node_std
                if node_cost < best_cost:
                    file_output.write(f"[{datetime.datetime.now()}] Replacing node `{L_cur[i].node_id}` of type {L_cur[i].instance_config_id} with instance: `{L_all[j].instance_config_id}. Actual cost: {node_cost}, Best cost: {best_cost}\n")
                    
                    print(f"[BATCH_REPLACEMENT {datetime.datetime.now()}] Replacing node `{L_cur[i].node_id}` with instance_conf=`{L_all[j].instance_config_id}` "
                                f"with `{L_all[j].instance_config_id}`")
                    print(f"[BATCH_REPLACEMENT {datetime.datetime.now()}] Node `{L_cur[i].node_id}` cost:`{node_cost}`; best_cost: `{best_cost}`")

                    # Creating a new node...
                    try:
                        instance_to_create = self.node_module.get_instance_descriptor(L_all[j].instance_config_id)
                        start_time = time.time()
                        node_ids = self.instance_manager.start([(instance_to_create, 1)])
                        end_time = time.time()
                        replaces += len(node_ids)
                        file_output.write(f"[{datetime.datetime.now()}] Successfully created nodes `{', '.join(sorted(node_ids))}` in {end_time-start_time} seconds\n")
                        print(f"[BATCH_REPLACEMENT {datetime.datetime.now()}] Successfully created nodes `{', '.join(sorted(node_ids))}` in {end_time-start_time} seconds")
                    except Exception as e:
                        logger.error(e)
                        print(f"[BATCH_REPLACEMENT {datetime.datetime.now()}] Error creating nodes...")
                        j += 1
                        # i -= 1
                        continue

                    # Setting up node
                    try:
                        print(f"[BATCH_REPLACEMENT {datetime.datetime.now()}] Setting up created nodes `{', '.join(sorted(node_ids))}`")
                        start_time = time.time()
                        self.instance_manager.setup(node_ids)
                        end_time = time.time()
                        print(f"[BATCH_REPLACEMENT {datetime.datetime.now()}] Nodes: `{', '.join(sorted(node_ids))}` sucessfully setup in {end_time-start_time} seconds")
                        file_output.write(f"[{datetime.datetime.now()}] Nodes: `{', '.join(sorted(node_ids))}` sucessfully setup in {end_time-start_time} seconds\n")
                    except Exception as e:
                        logger.error(e)
                        print(f"[BATCH_REPLACEMENT {datetime.datetime.now()}] Stopping unsuccessfully setup nodes `{', '.join(sorted(node_ids))}`. Stopping it!")
                        file_output.write(f"[{datetime.datetime.now()}] Stopping unsuccessfully setup nodes `{', '.join(sorted(node_ids))}`. Stopping it!\n")
                        self.instance_manager.stop(node_ids)
                        j += 1
                        # i -= 1
                        continue

                    j = 0

                    try:
                        self.instance_manager.stop([L_cur[i].node_id])
                    except Exception as e:
                        logger.error(e)
                        logger.error(f"Error stopping nodes `{', '.join(sorted(L_cur[i].node_id))}`. Skipping....")
                        continue

                else:
                    file_output.write(f"[{datetime.datetime.now()}] Skipping node `{L_cur[i].node_id}` (already is the best one)\n")
                    print(f"[BATCH_REPLACEMENT {datetime.datetime.now()}] Skipping node `{L_cur[i].node_id}` (already is the best one))")
                    j = 0

            i += 1

        print(f"[BATCH_REPLACEMENT {datetime.datetime.now()}] Number of nodes replaced: {replaces}")
        file_output.write(f"Batch replacement finished at {datetime.datetime.now()}. No. Nodes replaced: {replaces}\n\n")
        file_output.close()
        return True