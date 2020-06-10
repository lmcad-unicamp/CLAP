import yaml 

from flask import render_template, jsonify, make_response, request
from clap.app.serverapp.interface import ServerInterfaces
from clap.common.config import Defaults
from clap.common.utils import log

def __get_modules__():
    server_ifaces = ServerInterfaces()
    interfaces = [{
        'module': iface['module'],
        'name': iface['name'],
        'description': iface['description']
    } for iface in server_ifaces.get_interfaces()]
    return interfaces

def __read_file__(filename) -> str:
    with open(filename, 'r') as f:
        return f.read()

def __save_yaml__(yaml_string: str, filename: str) -> bool:
    to_save = yaml.safe_load(yaml_string)
    with open(filename, 'w') as f:
        f.write(yaml_string)

def get_navigation_items():
    return jsonify(__get_modules__()), 200

def get_module_cards_html():
    return render_template('index_cards_template.html', interfaces=__get_modules__()), 200

def get_configuration_html():
    config_type = request.args.get('config', default=None, type=str)
    if not config_type:
        return "Error", 404
    return render_template('configuration.html', config_type=config_type), 200

def get_configuration_navigation_html():
    config_type = request.args.get('config', default=None, type=str)
    if not config_type:
        return "Error", 404
    return render_template('configuration.html', config_type=config_type), 200

def get_configuration():
    config_type = request.form['config_type']
    try:
        if config_type == 'provider':
            return __read_file__(Defaults.cloud_conf), 200
        elif config_type == 'login':
            return __read_file__(Defaults.login_conf), 200
        elif config_type == 'instance':
            return __read_file__(Defaults.instances_conf), 200 
        else:
            return "Invalid type: {}".format(config_type), 400
    except Exception as e:
        return "Error reading {} file".format(config_type), 400

def save_configuration():
    config_type = request.form['config_type']
    content = request.form['content']
    
    if config_type == 'provider':
        filename = Defaults.cloud_conf
    elif config_type == 'login':
        filename = Defaults.login_conf
    elif config_type == 'instance':
        filename = Defaults.instances_conf
    else:
        return "Invalid file type", 400
    try:
        __save_yaml__(content, filename)
        return filename, 200
    except Exception as e:
        return "Error saving at {}: {}".format(filename, e), 400

def index(result=None):
    server_ifaces = ServerInterfaces()
    interfaces = [{
        'module': iface['module'],
        'name': iface['name'],
        'description': iface['description']
    } for iface in server_ifaces.get_interfaces()]

    return render_template('index.html')
