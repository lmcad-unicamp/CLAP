# -*- coding: utf-8 -*-
from multiprocessing import Process, Queue

from flask import Flask, render_template, request, json, jsonify
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, BooleanField, PasswordField, IntegerField, TextField, FormField, \
    SelectField, FieldList, TextAreaField
from wtforms.validators import DataRequired, Length
from flask_bootstrap import Bootstrap
from flask_sqlalchemy import SQLAlchemy

from app.server import commands
from app.server.exceptions import exceptions

app = Flask(__name__)
bootstrap = Bootstrap(app)
db = SQLAlchemy(app)

@app.route('/nodes/start', methods=['GET', 'POST'])
def start_nodes(result=None):
    instances = dict()
    i_name = ""
    qtde = 0

    for key, val in request.form.items():
        if key == 'instance-type':
            i_name = val
        elif key == 'instance-num':
            instances[i_name] = int(val)
            qtde += int(val)

    queue = Queue()
    p = Process(target=commands.node_start, args=(queue, instances))
    p.start()
    p.join()
    ret_code, ret_val = queue.get()

    if ret_code != 0:
        return jsonify(message="Error starting nodes.".format()), 601
    
    nodes = ret_val
    
    if len(nodes) != qtde:
        return jsonify(message="Only {} of {} nodes were sucessfully started...".format(len(nodes), qtde)), 601
    else:
        return jsonify(success=True)

@app.route('/nodes/alive', methods=['GET', 'POST'])
def alive_nodes(result=None):
    commands.node_alive()
    return jsonify(success=True)


@app.route('/templates/get', methods=['GET', 'POST'])
def get_instances(result=None):
    templates = json.dumps(list(commands.get_templates().keys()))
    return templates

@app.route('/templates/files/providers', methods=['GET', 'POST'])
def get_providers(result=None):
    return commands.read_provider_file()

@app.route('/templates/files/logins', methods=['GET', 'POST'])
def get_logins(result=None):
    return commands.read_login_file()

@app.route('/templates/files/templates', methods=['GET', 'POST'])
def get_instance_templates(result=None):
    return commands.read_template_file()

@app.route('/templates/files/save-providers', methods=['GET', 'POST'])
def save_providers(result=None):
    if commands.save_provider_file(request.json):
        return jsonify(success=True)
    else:
        return jsonify(message="Error saving to providers file. Identation may be incorrect or the file is invalid."), 600

@app.route('/templates/files/save-logins', methods=['GET', 'POST'])
def save_logins(result=None):
    if commands.save_login_file(request.json):
        return jsonify(success=True)
    else:
        return jsonify(message="Error saving to logins file. Identation may be incorrect or the file is invalid."), 600

@app.route('/templates/files/save-templates', methods=['GET', 'POST'])
def save_instance_templates(result=None):
    if commands.save_template_file(request.json):
        return jsonify(success=True)
    else:
        return jsonify(message="Error saving to templates file. Identation may be incorrect or the file is invalid."), 600

@app.route('/nodes/get', methods=['GET', 'POST'])
def get_nodes(result=None):
    nodes = json.dumps([node.__dict__ for node in commands.node_get()])
    return nodes

@app.route('/', methods=['GET', 'POST'])
def index(result=None):
    return render_template('index.html')