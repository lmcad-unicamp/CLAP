import yaml
from typing import Dict, List, Any, Tuple

from clap.common.cluster_repository import NodeInfo
from clap.common.config import Defaults
from clap.common.factory import PlatformFactory
from clap.common.utils import log


def __get_instance_api(**kwargs):
    platform_db = kwargs.get('plaform_db', Defaults.PLATFORM_REPOSITORY)
    repo_type = kwargs.get('repo_type', Defaults.REPOSITORY_TYPE)
    driver = kwargs.get('driver', Defaults.DRIVER_ID)

    return PlatformFactory.get_instance_api(
        platform_db=platform_db, repository_type=repo_type, default_driver=driver)


def node_start(nodes: Dict[str, int], tag: Dict[str, str] = None,
               group: str = None, group_extra: Dict = None, **kwargs) -> List[NodeInfo]:
    multi_instance = __get_instance_api(**kwargs)
    nodes_info = multi_instance.start_nodes(nodes)
    node_ids = [n.node_id for n in nodes_info]

    if tag:
        log.info("Adding tag `{}` to nodes `{}`".format(tag, ', '.join(node_ids)))
        nodes_info = multi_instance.add_tags_to_nodes([n.node_id for n in nodes_info], tag)

    if group:
        log.info("Adding nodes `{}` to group `{}`".format(', '.join(node_ids), group))
        added_nodes = multi_instance.add_nodes_to_group(node_ids, group, group_args=group_extra if group_extra else {})
        if len(added_nodes) != len(node_ids):
            log.error("{} nodes were not added to group `{}`".format(len(node_ids) - len(added_nodes), group))

    return nodes_info


def node_alive(node_ids: List[str] = None, tag: Dict[str, str] = None, **kwargs):
    multi_instance = __get_instance_api(**kwargs)

    if not node_ids:
        node_ids = [n.node_id for n in multi_instance.get_nodes()]
    elif tag:
        node_ids = set(node_ids)
        node_ids.update(set([node.node_id for node in multi_instance.get_nodes_with_tags(tag)]))
        node_ids = list(node_ids)

    return multi_instance.check_nodes_alive(node_ids) if node_ids else {}


def node_get(node_ids: List[str] = None, tags: Dict[str, str] = None, **kwargs) -> List[NodeInfo]:
    multi_instance = __get_instance_api(**kwargs)

    if not node_ids:
        return multi_instance.get_nodes(node_ids) if not tags else multi_instance.get_nodes_with_tags(tags)

    nodes = multi_instance.get_nodes(node_ids)

    if tags:
        nodes += multi_instance.get_nodes_with_tags(tags)

    return nodes


def node_add_tag(tags: Dict[str, str], node_ids: List[str] = None, **kwargs):
    multi_instance = __get_instance_api(**kwargs)

    if node_ids:
        node_ids = [node.node_id for node in multi_instance.get_nodes()]

    for key, val in tags.items():
        nodes = multi_instance.add_tags_to_nodes(node_ids, {key: val})
        log.info("Added tag `{}` for {} nodes".format({key: val}, len(nodes)))


def node_remove_tag(tags: List[str], node_ids: List[str] = None, **kwargs):
    multi_instance = __get_instance_api(**kwargs)

    if not node_ids:
        node_ids = [node.node_id for node in multi_instance.get_nodes()]

    for tag in tags:
        nodes = multi_instance.remove_tags_from_nodes(node_ids, [tag])
        if len(nodes) != len(node_ids):
            log.error("Tag not `{}` removed from {} nodes".format(tag, len(node_ids)-len(nodes)))


def node_stop(node_ids: List[str] = None, tags: Dict[str, str] = None, **kwargs):
    multi_instance = __get_instance_api(**kwargs)
    nodes = node_get(node_ids, tags, **kwargs)
    multi_instance.stop_nodes([n.node_id for n in nodes])
    log.info("Stopped {} nodes".format(len(nodes)))


def group_add(group: str, group_extra: Dict = None, node_ids: List[str] = None,
              tags: Dict[str, str] = None, **kwargs) -> List[NodeInfo]:
    multi_instance = __get_instance_api(**kwargs)
    node_ids = [n.node_id for n in node_get(node_ids, tags, **kwargs)]

    added_nodes = multi_instance.add_nodes_to_group(
        node_ids, group, group_args=group_extra if group_extra else {})

    if len(added_nodes) != len(node_ids):
        log.error("{} nodes were not added to group `{}`".format(len(node_ids)-len(added_nodes), group))

    return added_nodes


def group_remove():
    raise NotImplementedError("Not fully implemented yet...")


def group_action(group: str, action: str, group_extra: Dict = None, node_ids: List[str] = None,
                 tags: Dict[str, str] = None, **kwargs) -> List[NodeInfo]:
    multi_instance = __get_instance_api(**kwargs)
    node_ids = None if not node_ids and not tags else [n.node_id for n in node_get(node_ids, tags, **kwargs)]

    actioned_nodes = multi_instance.execute_group_action(
        group, action, node_ids=node_ids, group_args=group_extra if group_extra else {})

    if len(actioned_nodes) != len(node_ids):
        log.error("{} nodes have not successfully performed action `{}` from group `{}`".format(
            len(node_ids)-len(actioned_nodes), action, group))

    return actioned_nodes


def group_get(**kwargs) -> Dict[str, Tuple[List[str], List[str], str]]:
    multi_instance = __get_instance_api(**kwargs)
    groups = multi_instance.get_groups()
    group_values = dict()

    for group_name, group_actions, group_hosts, group_playbook in groups:
        group_values[group_name] = (group_actions, group_hosts, group_playbook)

    return group_values

def __save_yaml(yaml_string: str, filename: str) -> bool:
    try:
        yaml.safe_load(yaml_string)

        with open(filename, 'w') as f:
            f.write(yaml_string)

        return True

    except Exception as e:
        log.error(e)
        return False

def get_templates(**kwargs) -> Dict[str, Any]:
    return __get_instance_api(**kwargs).get_instance_templates()

def read_provider_file(**kwargs) -> str:
    with open(Defaults.cloud_conf, 'r') as f:
        return f.read()

def read_login_file(**kwargs) -> str:
    with open(Defaults.login_conf, 'r') as f:
        return f.read()

def read_template_file(**kwargs) -> str:
    with open(Defaults.instances_conf, 'r') as f:
        return f.read()

def save_provider_file(yaml_string: str) -> bool:
    return __save_yaml(yaml_string, Defaults.cloud_conf)

def save_login_file(yaml_string: str) -> bool:
    return __save_yaml(yaml_string, Defaults.login_conf)

def save_template_file(yaml_string: str) -> bool:
    return __save_yaml(yaml_string, Defaults.instances_conf)