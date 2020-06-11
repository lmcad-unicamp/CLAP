# -*- coding: utf-8 -*-
import setuptools
import threading
import os
from multiprocessing import Process, Queue

from flask import Flask, render_template, request, json, jsonify
from flask_bootstrap import Bootstrap

from . import common
from .interface import ServerInterfaces

from clap.common.utils import setup_log, path_extend

# Default Entry point

class ServerApp(object):
    app = None

    def __init__(self, name):
        self.name = name
        self.root_path = path_extend(os.path.dirname(__file__))
        self.server_ifaces = ServerInterfaces()
        ServerApp.app = Flask(name, root_path=self.root_path)
        Bootstrap(ServerApp.app)

    def initialize(self):
        self.register_modules()
        self.register_module_interfaces()

    def run(self, *args, **kwargs):
        self.app.run(*args, **kwargs)

    def register_modules(self):
        # Common interfaces
        for common_route in common.__routes__:
            route_name = common_route[0]
            route_path = "/{}".format(route_name)
            route_func = common_route[1]
            try:
                route_methods = common_route[2]
            except Exception:
                route_methods = []
            
            self.app.add_url_rule(route_path, route_name, route_func, methods=route_methods)

        # Module interfaces
        for interface in self.server_ifaces.get_interfaces():
            for route in interface['routes']:
                route_name = route[0]
                route_path = "/{}/{}".format(interface['module'], route_name)
                route_func = route[1]
                try:
                    route_methods = route[2]
                except Exception:
                    route_methods = []
                
                self.app.add_url_rule(route_path, route_path, route_func, methods=route_methods)

    def register_module_interfaces(self):
        for iface in self.server_ifaces.get_interfaces():
            if iface['register']:
                thread = threading.Thread(target=iface['register'], )
                thread.start()
