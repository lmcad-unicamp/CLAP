# -*- coding: utf-8 -*-
import setuptools
from multiprocessing import Process, Queue

from flask import Flask, render_template, request, json, jsonify
from flask_bootstrap import Bootstrap

from . import common
from .interface import ServerInterfaces

# Default Entry point
app = Flask(__name__, template_folder='templates')
Bootstrap(app)

for common_route in common.__routes__:
    route_name = common_route[0]
    route_path = "/{}".format(route_name)
    route_func = common_route[1]
    try:
        route_methods = common_route[2]
    except Exception:
        route_methods = []
    
    app.add_url_rule(route_path, route_name, route_func, methods=route_methods)

server_ifaces = ServerInterfaces()

for interface in server_ifaces.get_interfaces():
    for route in interface['routes']:
        route_name = route[0]
        route_path = "/{}/{}".format(interface['module'], route_name)
        route_func = route[1]
        try:
            route_methods = route[2]
        except Exception:
            route_methods = []
        
        app.add_url_rule(route_path, route_path, route_func, methods=route_methods)