# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, json
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, BooleanField, PasswordField, IntegerField, TextField, FormField, \
    SelectField, FieldList, TextAreaField
from wtforms.validators import DataRequired, Length
from flask_bootstrap import Bootstrap
from flask_sqlalchemy import SQLAlchemy

from app.server import commands

app = Flask(__name__)
app.secret_key = 'dev'

bootstrap = Bootstrap(app)
db = SQLAlchemy(app)


@app.route('/get-nodes', methods=['GET', 'POST'])
def get_nodes(result=None):
    nodes = json.dumps([node.__dict__ for node in commands.node_get()])
    return nodes
    #nodes = [node.__dict__ for node in commands.node_get()]
    #return render_template('nodes-div.html', nodes=nodes)

@app.route('/', methods=['GET', 'POST'])
def index(result=None):
    return render_template('index.html')


def process_request(text):
    return "REQUEST OK {}".format(text)
