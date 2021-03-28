import pandas as pd
import numpy as np

from itertools import groupby
from abc import abstractmethod, ABC
from typing import Dict, Any, List, Tuple
from collections import defaultdict
from dataclasses import dataclass, field, asdict

from common.config import Config
from common.clap import AbstractModule, NodeInfo, NodeStatus
from common.schemas import YAMLConfigurationReader, InstanceDescriptor, ProviderConfig, LoginConfig, InstanceConfig, \
    ConfigurationReader
from common.utils import path_extend, tmpdir, default_dict_to_dict, Singleton
from modules.node.module import NodeModule
from modules.cluster.cluster import ClusterModule


@dataclass
class Value:
    value: Any
    provider_id: str
    instance_id: str
    node_id: str = None
    cluster_id: str = None
    cluster_name: str = None
    cluster_node_type: str = None
    time: float = None
    execution_id: int = None


class Query(ABC):
    @abstractmethod
    def query(self, metrics: List[str] = None, filters: Dict[str, List[str]] = None) -> Dict[str, List[Value]]:
        raise NotImplementedError('Must be implemented in derived classes')


class InstanceCostFunction(ABC):
    @abstractmethod
    def cost(self, instances: List[InstanceDescriptor]) -> List[Tuple[InstanceDescriptor, float]]:
        raise NotImplementedError('Must be implemented in derived classes')


class MetricCostFunction(ABC):
    @abstractmethod
    def cost(self, metrics: Dict[str, List[Value]]) -> Dict[str, float]:
        raise NotImplementedError('Must be implemented in derived classes')


class InstanceManager(ABC):
    @abstractmethod
    def start(self, instances_count: List[Tuple[InstanceDescriptor, int]]) -> List[NodeInfo]:
        raise NotImplementedError("Must be implemented in derived classes")

    @abstractmethod
    def setup(self, node_ids: List[str]) -> List[str]:
        raise NotImplementedError("Must be implemented in derived classes")

    @abstractmethod
    def stop(self, node_ids: List[str]):
        raise NotImplementedError("Must be implemented in derived classes")


class Heuristic:
    daemon: bool = False

    def run(self, *args, **kwargs):
        raise NotImplementedError("Must be implemented in derived classes")


class CSVQuery(Query):
    def __init__(self, filepath, *args, **kwargs):
        self.csv_file = filepath

    def query(self, metrics: List[str] = None, filters: Dict[str, List[str]] = None) -> Dict[str, List[Value]]:
        csv_values = pd.read_csv(self.csv_file)
        filters = filters or {}
        filters.pop('metric_name', None)
        for column_name, list_values in filters.items():
            csv_values = csv_values[csv_values[column_name].isin(list_values)]

        csv_values.replace({np.nan: None}, inplace=True)
        values = defaultdict(list)
        for index, row in csv_values.iterrows():
            if metrics and row['metric_name'] not in metrics:
                continue

            value = Value(row['metric_value'], row['provider_id'], row['instance_id'],
                          row['node_id'], row['cluster_id'], row['cluster_name'],
                          row['cluster_node_type'], row['time'], row['execution_id'])
            values[row['metric_name']].append(value)

        return default_dict_to_dict(values)


class AWSInstancePriceAZ(InstanceCostFunction):
    def __init__(self, provider_id: str, az_costs: Dict[str, float]):
        self.provider_id = provider_id
        self.az_costs = az_costs
        self.node_module = NodeModule.get_module()

    def cost(self, instances: List[InstanceDescriptor]) -> List[Tuple[InstanceDescriptor, float]]:
        return [(instance, self.az_costs[instance.provider.region]) for instance in instances]


class MeanInterpolationPerAWSAZCost(MetricCostFunction):
    def __init__(self, provider_id: str, instance_cost_func: InstanceCostFunction, config_reader: ConfigurationReader):
        self.provider_id = provider_id
        self.instance_cost_func = instance_cost_func
        self.config_reader = config_reader

    def cost(self, metrics: Dict[str, List[Value]], *args, **kwargs) -> Dict[str, float]:
        mean_cost = dict()
        for (provider_id, instance_id), values in groupby(metrics['interpolations_per_second'],
                                                          key=lambda x: (x.provider_id, x.instance_id)):
            # if provider_id != self.provider_id:
            #    continue
            ips_values = [value.value for value in values]
            instance_descriptor = self.config_reader.get_instance_descriptor(instance_id)
            instance_descriptor, instance_cost = self.instance_cost_func.cost([instance_descriptor])[0]
            cost_mean = np.mean(ips_values) / instance_cost
            mean_cost[instance_id] = cost_mean
        return mean_cost


class StdInterpolationPerAWSAZCost(MetricCostFunction):
    def __init__(self, provider_id: str, instance_cost_func: InstanceCostFunction, config_reader: ConfigurationReader):
        self.provider_id = provider_id
        self.instance_cost_func = instance_cost_func
        self.config_reader = config_reader

    def cost(self, metrics: Dict[str, List[Value]], *args, **kwargs) -> Dict[str, float]:
        mean_cost = dict()
        for (provider_id, instance_id), values in groupby(metrics['interpolations_per_second'],
                                                          key=lambda x: (x.provider_id, x.instance_id)):
            # if provider_id != self.provider_id:
            #    continue
            ips_values = [value.value for value in values]
            instance_descriptor = self.config_reader.get_instance_descriptor(instance_id)
            instance_descriptor, instance_cost = self.instance_cost_func.cost([instance_descriptor])[0]
            cost_mean = np.std(ips_values) / instance_cost
            mean_cost[instance_id] = cost_mean
        return mean_cost


class ClusterInstanceManager(InstanceManager):
    def __init__(self, cluster_id: str, cluster_node_type: str, setup_at: str = 'before_all'):
        self.cluster_id = cluster_id
        self.cluster_node_type = cluster_node_type
        self.node_module = NodeModule.get_module()
        self.cluster_module = ClusterModule.get_module()
        self.setup_at = setup_at

    def start(self, instances_count: List[Tuple[InstanceDescriptor, int]]) -> List[NodeInfo]:
        return self.node_module.get_nodes(self.node_module.start_nodes_by_instance_descriptor(instances_count))

    def setup(self, node_ids: List[str]) -> List[str]:
        self.cluster_module.add_existing_node_to_cluster(self.cluster_id, {self.cluster_node_type: node_ids})
        self.cluster_module.cluster_setup(self.cluster_id, {self.cluster_node_type: node_ids}, at=self.setup_at)
        return node_ids

    def stop(self, node_ids: List[str]):
        self.node_module.stop_nodes(node_ids=node_ids)


class BatchReplacementHeuristic(Heuristic):
    daemon: bool = False

    @dataclass
    class NodeCost(object):
        node_id: str
        provider_id: str
        instance_type: str
        node_mean: float
        node_std: float

        def __eq__(self, other):
            return other.node_id == self.node_id and other.provider_id == self.provider_id

    def __init__(self,
                 node_ids: List[str],
                 node_query: Query,
                 instance_manager: InstanceManager,
                 mean_interpolation_cost_providers: Dict[str, MetricCostFunction],
                 std_interpolation_cost_providers: Dict[str, MetricCostFunction],
                 percentage: float):
        self.node_ids = node_ids
        self.instance_manager = instance_manager
        self.node_query = node_query
        self.interpolation_cost_providers = zip(
            mean_interpolation_cost_providers.keys(),
            mean_interpolation_cost_providers.values(),
            std_interpolation_cost_providers.values())
        self.percentage = percentage
        self.node_module = NodeModule.get_module()

    # def run(self, *args, **kwargs)
    def run(self, *args, **kwargs):
        L_all = []
        L_cur = []
        i = 0
        metrics = self.node_query.query()
        for provider_id, mean_cost_func, std_cost_func in self.interpolation_cost_providers:
            node_means = mean_cost_func.cost(metrics)
            node_stds = std_cost_func.cost(metrics)
            for node in self.node_module.get_nodes(self.node_ids):
                node_cost = self.NodeCost(node.node_id, provider_id, node.configuration.instance.instance_config_id,
                                          node_means[node.configuration.instance.instance_config_id],
                                          node_stds[node.configuration.instance.instance_config_id])
                L_all.append(node_cost)
                if node.configuration.provider.provider_config_id == provider_id:
                    L_cur.append(node_cost)

        L_all = list(reversed(sorted(L_all, key=lambda x: x.node_mean)))
        L_cur = sorted(L_cur, key=lambda x: x.node_mean)

        print('-----------ALL------------')
        for x in L_all:
            print(x)
            print()
        print('-----------CUR------------')
        for x in L_cur:
            print(x)
            print()
        print('-----------------------')

        i, j, lim = 0, 0, max(len(self.node_ids) * self.percentage, 1)
        while i < len(L_cur) * self.percentage:

            if L_cur[i] != L_all[j]:
                if L_cur[i].node_mean + L_cur[i].node_std < L_all[j].node_mean - L_all[j].node_std:
                    print(
                        f"Replacing instance {L_cur[i].instance_type}:{L_cur[i].provider_id} ({L_cur[i].node_id}) for "
                        f"{L_all[j].instance_type}:{L_all[j].provider_id}")
                    try:
                        instance_to_create = self.node_module.config_reader.get_instance_config(L_all[j].instance_type)
                        instance_to_create.provider = L_all[j].provider_id
                        instance_to_create.provider_config = self.node_module.config_reader.get_provider_config(
                            L_all[j].provider_id)
                        new_nodes = [node.node_id for node in
                                     self.instance_manager.start(instances_count=[(instance_to_create, 1)])]
                    except Exception as e:
                        print(e)
                        j += 1
                        # i -= 1
                        continue

                    try:
                        self.instance_manager.setup(new_nodes)
                        # L_all[j].node_id = new_nodes[0]
                    except Exception as e:
                        self.instance_manager.stop(node_ids=new_nodes)
                        print(e)
                        j += 1
                        # i -= 1
                        continue

                    j = 0

                    try:
                        self.instance_manager.stop(node_ids=[L_cur[i].node_id])
                    except Exception as e:
                        print(e)
                else:
                    print(
                        f"Skipping instance {L_cur[i].instance_type}:{L_cur[i].provider_id} (already in best location)")
                    j = 0

            i += 1


class DummyInstanceManager(InstanceManager):
    def __init__(self):
        self.node_module = NodeModule.get_module()

    def start(self, instances_count: List[Tuple[InstanceDescriptor, int]]) -> List[NodeInfo]:
        nodes = []
        for instance, count in instances_count:
            for i in range(count):
                nodes.append(self.node_module.node_repository_operator.create_node(instance))
        return nodes

    def setup(self, node_ids: List[str]) -> List[str]:
        return node_ids

    def stop(self, node_ids: List[str]):
        self.node_module.node_repository_operator.remove_nodes(node_ids=node_ids)


if __name__ == '__main__':
    Config.NODE_REPOSITORY_PATH = '/home/napoli/temp/sqlite/test.db'

    try:
        os.unlink('/home/napoli/temp/sqlite/test.db')
    except:
        pass

    csv_query = CSVQuery('/home/napoli/example.csv')
    values = csv_query.query(filters=None)
    # print(values)

    conf_reader = YAMLConfigurationReader()
    node_module = NodeModule()
    instances = ['type-a', 'type-b']

    instance_cost_funcs = [
        ('aws-config-us-east-1', AWSInstancePriceAZ('aws-config-us-east-1', {'t2.micro': 0.05, 't2.medium': 0.06})),
        ('aws-config-us-east-2', AWSInstancePriceAZ('aws-config-us-east-2', {'t2.micro': 0.09, 't2.medium': 0.10}))]

    mean_costs_dict = dict()
    stds_costs_dict = dict()
    for az, instance_cost_func in instance_cost_funcs:
        mean_interpolation_cost = MeanInterpolationPerAWSAZCost(az, instance_cost_func)
        std_interpolation_cost = StdInterpolationPerAWSAZCost(az, instance_cost_func)
        mean_costs = mean_interpolation_cost.cost(values)
        std_costs = std_interpolation_cost.cost(values)
        print(az, mean_costs, std_costs)
        mean_costs_dict[az] = mean_interpolation_cost
        stds_costs_dict[az] = std_interpolation_cost

    instances_obj = [conf_reader.get_instance_config(i) for i in instances]
    instance_manager = DummyInstanceManager()
    nodes = instance_manager.start([(instances_obj[0], 3), (instances_obj[1], 3)])
    # print(node_module.list_nodes())
    # another_one = instances_obj[0]
    # another_one.provider = instances_obj[1].provider
    # another_one.provider_config = conf_reader.get_provider_info(instances_obj[1].provider)
    # nodes = instance_manager.start([(another_one, 1), (instances_obj[0], 2)])
    # print(node_module.list_nodes())
    # instance_manager.stop([node.node_id for node in nodes])
    # print(node_module.list_nodes())

    heuristic = BatchReplacementHeuristic([node.node_id for node in nodes], csv_query,
                                          instance_manager, mean_costs_dict, stds_costs_dict, 0.1)

    heuristic.run()
