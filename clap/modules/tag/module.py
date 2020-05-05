from typing import List, Dict, Union

from clap.common.factory import PlatformFactory
from clap.common.cluster_repository import NodeInfo

def node_add_tag(node_ids: List[str], tags: Dict[str, str]) -> List[str]:
    multi_instance = PlatformFactory.get_instance_api()
    nodes = multi_instance.add_tags_to_nodes(node_ids, tags)
    return nodes

def node_append_tag(node_ids: List[str], tags: Dict[str, str]) -> List[str]:
    multi_instance = PlatformFactory.get_instance_api()
    nodes = multi_instance.append_tags_to_nodes(node_ids, tags)
    return nodes

def node_remove_tag(node_ids: List[str], tags: Union[str, Dict[str, str]]) -> List[str]:
    multi_instance = PlatformFactory.get_instance_api()
    if type(tags) is str:
        return multi_instance.remove_tags_from_nodes_by_key(node_ids, [tags])
    elif type(tags) is dict:
        return multi_instance.remove_tags_from_nodes(node_ids, tags)
    else:
        raise TypeError("Invalid tags type")