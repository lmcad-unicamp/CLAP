import yaml
import threading
import time
import sched
import json

from flask import jsonify, render_template, request

from clap.common.factory import PlatformFactory
from clap.common.cluster_repository import NodeInfo
from clap.common.config import Defaults
from clap.common.factory import PlatformFactory

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

def node_resume():
    node_ids = json.loads(request.form['node_ids'])
    node_module = __get_module__('node')
    try:
        resumed_nodes = node_module.resume_nodes(node_ids)
        return "Resumed nodes {}".format(','.join(resumed_nodes)), 200
    except Exception as e:
        print(e)
        return "Failed to resume nodes {}".format(','.join(node_ids)), 400

def get_node_list():
    node_module = __get_module__('node')
    return jsonify([node.__dict__ for node in node_module.list_nodes()]), 200

def node_list_update_periodically():
    node_module = __get_module__('node')

    #while True:
    #    node_module.is_alive([])
    #    time.sleep(120)
