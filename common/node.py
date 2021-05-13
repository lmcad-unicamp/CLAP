import time

from dataclasses import dataclass, field, asdict

from typing import List, Any, Dict, Union

from common.repository import Repository, RepositoryController
from common.schemas import InstanceInfo, ProviderConfigLocal, LoginConfig, InstanceConfigAWS
from common.utils import get_random_name, get_logger, Serializable

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
class NodeDescriptor(Serializable):
    node_id: str
    configuration: InstanceInfo
    nickname: str = ''
    ip: str = None
    type: str = NodeType.TYPE_CLOUD
    cloud_instance_id: str = None
    cloud_lifecycle: str = NodeLifecycle.NORMAL
    status: str = NodeStatus.UNKNOWN
    creation_time: float = 0.0
    update_time: float = 0.0
    roles: List[str] = field(default_factory=list)
    tags: Dict[str, List[str]] = field(default_factory=dict)
    facts: Dict[str, str] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)
    groups: Dict[str, List[str]] = field(default_factory=dict)

    def __str__(self):
        return f"id=`{self.node_id}` nickname=`{self.nickname}`, ip=`{self.ip}` status=`{self.status}` " \
               f"instance_type=`{self.configuration.instance.instance_config_id}`, " \
               f"tags=`{','.join(sorted([f'{tag}={sorted(values)}' for tag, values in self.tags.items()]))}`, " \
               f"roles=`{','.join(sorted(self.groups.keys()))}`"

    def to_dict(self):
        d = asdict(self)
        d['configuration'] = self.configuration.to_dict()
        return d

    @staticmethod
    def from_dict(d: dict) -> 'NodeDescriptor':
        node = NodeDescriptor(**d)
        node.configuration = InstanceInfo.from_dict(d['configuration'])
        return node


def get_local_node(node_id: str = 'node-local') -> NodeDescriptor:
    provider = ProviderConfigLocal(provider_config_id='provider-local')
    login = LoginConfig(login_config_id='login-local', user='')
    instance = InstanceConfigAWS(instance_config_id='instance-local', provider='provider-local', login='login-local',
                                 flavor='', image_id='')
    descriptor = InstanceInfo(provider=provider, login=login, instance=instance)
    return NodeDescriptor(node_id=node_id, configuration=descriptor, nickname=get_random_name(), ip='0.0.0.0')


class NodeRepositoryController(RepositoryController):
    def __init__(self, repository: Repository, node_prefix: str = 'node'):
        super().__init__(repository)
        self.node_prefix = node_prefix

    def create_node(self, instance_descriptor: InstanceInfo, node_id: str = None, cloud_instance_id: str = None,
                    ip: str = None, status: str = NodeStatus.UNKNOWN, cloud_lifecycle: str = NodeLifecycle.NORMAL,
                    node_type: str = NodeType.TYPE_CLOUD, extra: dict = None) -> NodeDescriptor:
        name = get_random_name(in_use_names=[n.nickname for n in self.get_all_nodes()])
        extra = extra or dict()
        node_id = node_id or self.get_unique_node_id()
        creation_time = time.time()
        new_node = NodeDescriptor(
            node_id=node_id, configuration=instance_descriptor, nickname=name,
            ip=ip, type=node_type, cloud_instance_id=cloud_instance_id, cloud_lifecycle=cloud_lifecycle,
            status=status, creation_time=creation_time, update_time=creation_time, extra=extra)
        self.upsert_node(new_node)
        return new_node

    @staticmethod
    def __update__(nodes: Union[NodeDescriptor, List[NodeDescriptor]]) -> List[NodeDescriptor]:
        nodes = nodes if type(nodes) is list else [nodes]
        return nodes

    def get_unique_node_id(self) -> str:
        node_idx = self.increment_key('node_index')
        return f"{self.node_prefix}-{node_idx}"

    def upsert_node(self, node: NodeDescriptor):
        node.update_time = time.time()
        with self.repository.connect('node') as db:
            db.upsert(node.node_id, node.to_dict())

    def remove_node(self, node_id: str):
        with self.repository.connect('node') as db:
            db.remove(node_id)

    def remove_nodes(self, node_ids: List[str]):
        with self.repository.connect('node') as db:
            db.remove_multiple(node_ids)

    def get_nodes_by_id(self, node_ids: List[str]) -> List[NodeDescriptor]:
        with self.repository.connect('node') as db:
            return self.__update__([NodeDescriptor.from_dict(node) for node in db.get_multiple(node_ids).values()])

    def get_all_nodes(self) -> List[NodeDescriptor]:
        with self.repository.connect('node') as db:
            return self.__update__([NodeDescriptor.from_dict(node) for node in db.get_all().values()])
