import time

from dataclasses import dataclass, field, asdict

from typing import List, Any, Dict, Callable, Optional

import dacite

from common.repository import Repository
from common.configs import InstanceInfo
from common.utils import get_logger

logger = get_logger(__name__)


class NodeStatus:
    UNKNOWN = 'unknown'
    STARTED = 'started'
    UNREACHABLE = 'unreachable'
    REACHABLE = 'reachable'
    PAUSED = 'paused'
    STOPPED = 'stopped'


class NodeType:
    TYPE_CLOUD = 'cloud'
    TYPE_LOCAL = 'local'


class NodeLifecycle:
    NORMAL = 'normal'
    PREEMPTIBLE = 'preemptible'


@dataclass
class NodeDescriptor:
    node_id: str
    configuration: InstanceInfo
    nickname: Optional[str] = ''
    ip: Optional[str] = ''
    type: Optional[str] = NodeType.TYPE_CLOUD
    cloud_instance_id: Optional[str] = ''
    cloud_lifecycle: Optional[str] = NodeLifecycle.NORMAL
    status: Optional[str] = NodeStatus.UNKNOWN
    creation_time: Optional[float] = 0.0
    update_time: Optional[float] = 0.0
    roles: List[str] = field(default_factory=list)
    tags: Dict[str, str] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)


class NodeRepositoryController:
    def __init__(self, repository: Repository):
        self.repository = repository

    def upsert_node(self, node: NodeDescriptor):
        node.update_time = time.time()
        with self.repository.connect('node') as db:
            node_dict = asdict(node)
            db.upsert(node.node_id, node_dict)

    def remove_node(self, node_id: str):
        with self.repository.connect('node') as db:
            db.remove(node_id)

    def remove_nodes(self, node_ids: List[str]):
        with self.repository.connect('node') as db:
            db.remove_multiple(node_ids)

    def get_nodes_by_id(self, node_ids: List[str]) -> List[NodeDescriptor]:
        with self.repository.connect('node') as db:
            nodes = [
                dacite.from_dict(data_class=NodeDescriptor, data=node)
                for nid, node in db.get_multiple(node_ids).items()
            ]
            return nodes

    def get_all_nodes(self) -> List[NodeDescriptor]:
        with self.repository.connect('node') as db:
            return [
                dacite.from_dict(data_class=NodeDescriptor, data=node)
                for nid, node in db.get_all().items()
            ]

    def get_nodes_filter(self, filter_func: Callable[[NodeDescriptor], bool]) -> \
            List[NodeDescriptor]:
        return [node for node in self.get_all_nodes() if filter_func(node)]
