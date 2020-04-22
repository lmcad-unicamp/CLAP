from typing import List, Dict, Tuple

from clap.common.factory import PlatformFactory
from clap.common.cluster_repository import NodeInfo
from clap.common.utils import log


def add_group_to_node(node_ids: List[NodeInfo], group: str, group_args: Dict[str, str] = None, tags: Dict[str, str] = None) -> List[str]:
    multi_instance = PlatformFactory.get_instance_api()
    node_ids = set(node_ids)

    if tags:
        try:
            for k, v in tags.items():
                node_ids.update(set([node.node_id for node in multi_instance.get_nodes_with_tags({k: v})]))
        except Exception as e:
            log.error(e)
            raise

    if not node_ids:
        return []

    node_ids = list(node_ids)
    added_nodes = multi_instance.add_nodes_to_group(node_ids, group, group_args=group_args)
    return added_nodes


def execute_group_action(node_ids: List[NodeInfo], group: str, action: str, group_args: Dict[str, str] = None, tags: Dict[str, str] = None) -> List[str]:
    multi_instance = PlatformFactory.get_instance_api()

    if tags:
        try:
            for k, v in tags.items():
                node_ids.update(set([node.node_id for node in multi_instance.get_nodes_with_tags({k: v})]))
        except Exception as e:
            log.error(e)
            raise

    actioned_nodes = multi_instance.execute_group_action(group, action, group_args=group_args, node_ids=node_ids)
    return actioned_nodes


def list_groups() -> List[Tuple[str, List[str], List[str], str]]:
    multi_instance = PlatformFactory.get_instance_api()
    groups = multi_instance.get_groups()
    return groups


def remove_group_from_node():
    raise NotImplementedError("Not fully implemented yet...")
    # multi_instance = __get_instance_api(namespace)
    # try:
    #     extra = {arg.split('=')[0]: arg.split('=')[1] for arg in namespace.extra} if namespace.extra else {}
    # except Exception:
    #     raise Exception("Error mounting extra parameters. Are you putting spaces after `=`? "
    #                     "Please check the extra parameters passed")
    #
    # removed_nodes = multi_instance.remove_node_from_group(namespace.node_ids, namespace.group, group_args=extra)
    # if removed_nodes:
    #     print("Nodes `{}` were successfully removed from group `{}`".format(', '.join(removed_nodes), namespace.group))

