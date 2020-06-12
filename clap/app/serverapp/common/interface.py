from flask import render_template, jsonify, make_response
from clap.app.serverapp.interface import ServerInterfaces

def __get_modules__():
    server_ifaces = ServerInterfaces()
    interfaces = [{
        'module': iface['module'],
        'name': iface['name'],
        'description': iface['description']
    } for iface in server_ifaces.get_interfaces()]
    return interfaces

def get_navigation_html():
    return render_template('navigation_template.html', interfaces=__get_modules__()), 200

def get_module_cards_html():
    return render_template('index_cards_template.html', interfaces=__get_modules__()), 200

def index(result=None):
    server_ifaces = ServerInterfaces()
    interfaces = [{
        'module': iface['module'],
        'name': iface['name'],
        'description': iface['description']
    } for iface in server_ifaces.get_interfaces()]

    return render_template('index.html')
