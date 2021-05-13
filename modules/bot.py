import dataclasses
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple
from abc import abstractmethod

from common.clap import AbstractModule
from common.utils import get_logger
from modules.group import GroupModule
from modules.cluster import ClusterModule

logger = get_logger(__name__)


class Reporter:
    @abstractmethod
    def query(self):
        raise NotImplementedError('Method must be implemented in derived classes')

    @abstractmethod
    def state(self) -> Dict[str, Dict[str, Any]]: # Returns {node: {metric: value, metric2: [values]} }
        raise NotImplementedError('Method must be implemented in derived classes')


class Decider:
    @abstractmethod
    def should_scale(self, cluster_id: str, state: Dict[str, Dict[str, Any]]) -> Tuple[List[Tuple[str, int]], List[str]]:
        # Returns ( [(node_to_add, qtde), (node_2, qtde)], [node_to_remove, node_to_remove] )
        raise NotImplementedError('Method must be implemented in derived classes')


class Scaler:
    def __init__(self, cluster_id: str):
        self.cluster_id = cluster_id
        self.cluster_module = ClusterModule.get_module()

    def scale(self, delta):
        pass


class AutoScaler:
    pass


class Bot:
    @abstractmethod
    def run(self, *args, **kwargs):
        raise NotImplementedError('Method must be implemented in derived classes')
    


class BotModule(AbstractModule):
    module_name = 'bot'
    module_version = '0.1.0'
    module_description = "CLAP's robot module"
    module_tags = []
    @staticmethod
    def get_module(**defaults_override) -> 'BotModule':
        cluster_module = ClusterModule.get_module()
        return BotModule(group_module, cluster_module)

    def __init__(self, group_module: GroupModule, cluster_module: ClusterModule):
        self.group_module = group_module
        self.cluster_module = cluster_module


    def run(bot: Bot, bot_args = (), bot_kwargs = None, times: int = None, timeout: float = 10.0):
        bot_args = bot_args if bot_args else tuple()
        bot_kwargs = bot_kwargs if bot_kwargs else dict()
        while True:
            bot.run(*bot_args, **bot_kwargs) 
            
            if times is not None:
                times -= 1
                if times <= 0:
                    break

            time.sleep(timeout)
