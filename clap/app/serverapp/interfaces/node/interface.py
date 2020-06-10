import yaml

from flask import jsonify

from clap.common.factory import PlatformFactory
from clap.common.cluster_repository import NodeInfo
from clap.common.config import Defaults
from clap.common.factory import PlatformFactory

from flask import render_template

def __get_module__(name, **kwargs):
    platform_db = kwargs.get('plaform_db', Defaults.PLATFORM_REPOSITORY)
    repo_type = kwargs.get('repo_type', Defaults.REPOSITORY_TYPE)
    driver = kwargs.get('driver', Defaults.DRIVER_ID)
    return PlatformFactory.get_module_interface().get_module(name)

def node_index():
    return render_template('node/node.html')

def get_node_templates():
    template_module = __get_module__('template')
    return template_module.list_instance_types()

def get_node_list():
    node_module = __get_module__('node')
    return jsonify([node.__dict__ for node in node_module.list_nodes()]), 200