import time

from typing import List, Any
from dataclasses import dataclass, field, asdict

from common.repository import RepositoryOperator
from common.utils import get_logger, Serializable
from modules.bot import Bot
from modules.node import NodeModule
from modules.cluster import ClusterModule
from modules.spits import SpitsModule

logger = get_logger(__name__)

@dataclass
class Value(Serializable):
    value: Any
    node_id: str
    instance_config_id: str
    time: float = None
    tags: dict = field(default_factory=dict)

    def to_dict(self):
        d = asdict(self)
        return d

    @staticmethod
    def from_dict(d: dict) -> 'Value':
        return Value(**d)


class SpitsMetricsRepositoryOperator(RepositoryOperator):
    def __init__(repository: Repository, metric_prefix: str = 'metric'):
        super().__init__(repository)
        self.metric_prefix = metric_prefix
        self.metrics_table = 'metrics'

    def get_metric_id(self):
        return f'{self.metric_prefix}-{time.time()}'

    def upsert_metric(self, d: dict):
        with self.repository.connect(self.metrics_table) as db:
            metric_id = self.get_metric_id
            db.upsert(metric_id, d)

    def get_metric(self, metric_id: str) -> dict:
        with self.repository.connect(self.metrics_table) as db:
            return db.get(metric_id) 

    def get_all_metrics(self) -> Dict[str, dict]:
        with self.repository.connect(self.metrics_table) as db:
            return db.get_all()


class SpitsQueryBot(Bot):
    def __init__(self, repository_operator: SpitsMetricsRepositoryOperator, cluster_id: str, jobid: str, pypits_path: str = None, spits_jobs_path: str = None):
        self.repository = repository_operator
        self.cluster_id = cluster_id
        self.jobid = jobid
        self.pypits_path = pypits_path
        self.spits_jobs_path = spits_jobs_path
        self.cluster_module = ClusterModule.get_module()
        self.spits_module = SpitsModule.get_module()
        self.node_module = NodeModule.get_module()

    def run(self, *args, **kwargs):
        try:
            metrics: List[str] = kwargs.pop('metrics')
        except KeyError as e:
            logger.error(f'Parameter `{e}` must be informed.')
            raise
    
        node_ids = self.cluster_module.get_nodes_from_cluster(self.cluster_id)
        # TODO only setup nodes....
        metric_values = self.spits_module.query_job_status(self.jobid, node_ids, pypits_path=self.pypits_path,
                                                           spits_job_path=self.spits_jobs_path, quiet=True)
        d = defaultdict(list)
        for node_id, values in metric_values.items():
            node = self.node_module.get_nodes_by_id([node_id])[0]
            job_status = values['job_status']
            job_metrics = values['metrics']
            for m in job_metrics:
                if metrics and m['name'] not in metrics:
                    continue

                if m['type'] == 'integer':
                    cast_to = int
                elif m['type'] == 'double' or m['type'] == 'float':
                    cast_to = float
                else:
                    cast_to = str

                d[m['name']].append(Value(
                    value=cast_to(m['value']), node_id=node.node_id,
                    instance_config_id=node.configuration.instance.instance_config_id,
                    time=m['time']))

        self.repository.upsert_metric(dict(d))
