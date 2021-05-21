from abc import abstractmethod, ABC
from typing import List, Dict

from clap.node import NodeDescriptor
from clap.configs import InstanceInfo
from clap.utils import get_logger

logger = get_logger(__name__)


class InstanceDeploymentError(Exception):
    pass


class AbstractInstanceProvider(ABC):
    @abstractmethod
    def start_instances(self, instance: InstanceInfo, count: int,
                        timeout: int = 600) -> List[NodeDescriptor]:
        pass

    @abstractmethod
    def stop_instances(self, nodes_to_stop: List[NodeDescriptor],
                       timeout: int = 600) -> List[NodeDescriptor]:
        pass

    @abstractmethod
    def pause_instances(self, nodes_to_pause: List[NodeDescriptor],
                        timeout: int = 600) -> List[NodeDescriptor]:
        pass

    @abstractmethod
    def resume_instances(self, nodes_to_resume: List[NodeDescriptor],
                         timeout: int = 600) -> List[NodeDescriptor]:
        pass

    @abstractmethod
    def update_instance_info(self, nodes_to_check: List[NodeDescriptor],
                             timeout: int = 600) -> List[NodeDescriptor]:
        pass
