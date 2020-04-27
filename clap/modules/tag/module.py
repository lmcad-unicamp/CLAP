from typing import List, Dict

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

def node_remove_tag(node_ids: List[str], tags: str) -> List[str]:
    multi_instance = PlatformFactory.get_instance_api()
    if not node_ids:
        node_ids = [node.node_id for node in multi_instance.get_nodes()]
    nodes = multi_instance.remove_tags_from_nodes(node_ids, [tags])
    return nodes