from typing import List, Dict, Union

from clap.common.factory import PlatformFactory
from clap.common.cluster_repository import NodeInfo

def node_add_tag(node_ids: List[str], tags: Dict[str, str]) -> List[str]:
    """ Add tags to nodes

    :param node_ids: List of node ids to add the tags.
    :type node_ids: List[str]
    :param tags: Key-valued dictionary with informing the tags key and value. Each tag may contain a set of value, so if a value a tag with the same key already exists in node, the value will be added to the tag set.
    :type tags: Dict[str, str]
    :return: A list of nodes which the tags were added 
    :rtype: List[str]
    """
    multi_instance = PlatformFactory.get_instance_api()
    nodes = multi_instance.add_tags_to_nodes(node_ids, tags)
    return nodes

# def node_append_tag(node_ids: List[str], tags: Dict[str, str]) -> List[str]:
#     multi_instance = PlatformFactory.get_instance_api()
#     nodes = multi_instance.append_tags_to_nodes(node_ids, tags)
#     return nodes

def node_remove_tag(node_ids: List[str], tags: Union[str, Dict[str, str]]) -> List[str]:
    """ Remove a tag value from a node tag set 

    :param node_ids: List of node ids to remove the tags.
    :type node_ids: List[str]
    :param tags: The tags can be a dictionay or a list. If:
      - Tag is a dictionary: Key-valued dictionary with informing the tags key and value. The value will be removed from each tag set. If the tag set contains no value, the node tag will be removed.
      - Tag is a list: List of tags to remove from nodes (all tag values will be removed from the tag set of the node)
    :type tags: Union[str, Dict[str, str]]
    :return: A list of nodes which the tags were removed 
    :rtype: List[str]
    """
    multi_instance = PlatformFactory.get_instance_api()
    if type(tags) is str:
        return multi_instance.remove_tags_from_nodes_by_key(node_ids, [tags])
    elif type(tags) is dict:
        return multi_instance.remove_tags_from_nodes(node_ids, tags)
    else:
        raise TypeError("Invalid tags type")