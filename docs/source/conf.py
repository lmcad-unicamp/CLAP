# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
import sys
sys.path.insert(0, os.path.abspath('../../'))

import sphinx_rtd_theme


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    'sphinx.ext.autodoc',
    'autoapi.extension',
    'sphinx_rtd_theme',
    'sphinx.ext.viewcode',
    'sphinx.ext.autodoc.typehints'
]


autoapi_type = 'python'
autoapi_dirs = ['../../clap/']
autoapi_member_order = 'alphabetical'
autoapi_python_use_implicit_namespaces = True
autoapi_python_class_content = 'both'
autoapi_file_patterns = ['*.py']
autoapi_generate_api_docs = True
autoapi_add_toctree_entry = False

autodoc_typehints = 'description'


# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# -- Project information -----------------------------------------------------

project = 'CLoud Application Platform'
copyright = u'2020, Otávio Napoli'
author = u'Otávio Napoli'

# The full version, including alpha/beta/rc tags
version = open('../../version.txt').read()
release = open('../../version.txt').read()

source_suffix = ['.rst']
master_doc = 'index'


# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = [
    '**.ipynb_checkpoints'
]


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = 'sphinx_rtd_theme'

htmlhelp_basename = 'clapdoc'

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
# html_static_path = ['_static']

source_encoding = 'utf-8'

htmlhelp_basename = 'clapdoc'
