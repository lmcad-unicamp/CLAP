# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, flash, Markup
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, BooleanField, PasswordField, IntegerField, TextField, FormField, \
    SelectField, FieldList, TextAreaField
from wtforms.validators import DataRequired, Length
from flask_bootstrap import Bootstrap
from flask_sqlalchemy import SQLAlchemy
import json

from clap.common.factory import PlatformFactory
from .commands import *


app = Flask(__name__)
app.secret_key = 'dev'

bootstrap = Bootstrap(app)
db = SQLAlchemy(app)


@app.route('/', methods=['GET', 'POST'])
def index(result=None):
    #nodes = json.dumps([node.__dict__ for node in node_get()])
    #print(nodes)
    return render_template('index.html', nodes=None)


def process_request(text):
    return "REQUEST OK {}".format(text)
