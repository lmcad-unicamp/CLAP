from dataclasses import dataclass, field

from typing import List, Any, Dict, Optional

from clap.configs import InstanceInfo
from clap.utils import get_logger

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
