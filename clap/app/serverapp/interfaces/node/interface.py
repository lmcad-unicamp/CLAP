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
        return "Resumed nodes {}".format(', '.join(resumed_nodes)), 200
    except Exception as e:
        print(e)
        return "Failed to resume nodes {}".format(', '.join(node_ids)), 400

def node_pause():
    node_ids = json.loads(request.form['node_ids'])
    node_module = __get_module__('node')
    try:
        paused_nodes = node_module.pause_nodes(node_ids)
        return "Paused nodes {}".format(', '.join(paused_nodes)), 200
    except Exception as e:
        print(e)
        return "Failed to pause nodes {}".format(', '.join(node_ids)), 400

def node_stop():
    node_ids = json.loads(request.form['node_ids'])
    node_module = __get_module__('node')
    try:
        stopped_nodes = node_module.stop_nodes(node_ids)
        return "Stopped nodes {}".format(', '.join(stopped_nodes)), 200
    except Exception as e:
        print(e)
        return "Failed to stop nodes {}".format(', '.join(node_ids)), 400

def get_group_list():
    group_module = __get_module__('group')
    values = [{'name': group['name'], 'actions': list(group['actions'].keys())} for group in group_module.list_groups()]
    values = sorted(values, key=lambda x: x['name'])
    return jsonify(values), 200

def get_group_add_modal():
    group_module = __get_module__('group')
    group_name = request.form['group']

    actions = next(iter([group['actions'] for group in group_module.list_groups() if group['name'] == group_name]))
    
    if 'setup' in actions:
        if actions['setup']['vars']:
            return render_template('node/node-group-add.html', group_name=group_name, action_vars=actions['setup']['vars']), 200
    # No vars or no setup action
    return render_template('node/node-group-add.html', group_name=group_name), 200

# Must Add hosts
def node_add_group():
    group_module = __get_module__('group')
    group_name = request.form['group_name']
    group_values = json.loads(request.form['group_values'])
    node_ids = json.loads(request.form['node_ids'])

    actions = next(iter([group['actions'] for group in group_module.list_groups() if group['name'] == group_name]))
    invalids = []

    if 'setup' in actions:
        if actions['setup']['vars']:
            for var_value in actions['setup']['vars']:
                if var_value['optional']:
                    continue
                got_value = next(iter([v for v in group_values if v['name'] == var_value['name']]))
                if not got_value['value']:
                    invalids.append(got_value['name'])

    if invalids:
        return "Variables: `{}` must be set!".format(", ".join(sorted(invalids))), 400

    group_args = {value['name']: value['value'] for value in group_values}
    try:
        group_module.add_group_to_node(node_ids, group_name, group_args)
        return "Nodes `{}` successfully added to group {}".format(', '.join(sorted(node_ids)), group_name), 200
    except Exception as e:
        print(e)
        return "Error adding nodes to group {}: {}".format(group_name, e), 200

def get_node_list():
    node_module = __get_module__('node')
    return jsonify([node.__dict__ for node in node_module.list_nodes()]), 200

def node_list_update_periodically():
    node_module = __get_module__('node')

    #while True:
    #    node_module.is_alive([])
    #    time.sleep(120)
