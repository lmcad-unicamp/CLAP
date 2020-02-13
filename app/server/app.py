# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, flash, Markup
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, BooleanField, PasswordField, IntegerField, TextField, FormField, \
    SelectField, FieldList, TextAreaField
from wtforms.validators import DataRequired, Length
from flask_bootstrap import Bootstrap
from flask_sqlalchemy import SQLAlchemy

from clap.common.factory import PlatformFactory


app = Flask(__name__)
app.secret_key = 'dev'

bootstrap = Bootstrap(app)
db = SQLAlchemy(app)

class ClusterCreateForm(FlaskForm):
    cluster_name = TextAreaField()
    edit = SubmitField()


class ClusterCreateForm(FlaskForm):
    message = TextAreaField()
    close = SubmitField()


@app.route('/', methods=['GET', 'POST'])
def index(result=None):
    multi_instance = PlatformFactory.get_instance_api()

    nodes = multi_instance.get_nodes()

    if 'question' in request.form:
        result = process_request(request.args.get('question'))
    print("REQUEST ARGS: {}".format(request.args))
    print("REQUEST: {}".format(request.form))

    return render_template('index.html', nodes=nodes)


def process_request(text):
    return "REQUEST OK {}".format(text)
