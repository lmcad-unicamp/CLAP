"""""""""""""""""
CLAP
"""""""""""""""""

CLoud Application Platform (CLAP) provides a interface to manage, interact and deploy HPC applications hosted in different cloud providers.
CLAP is based on the `elasticluster <https://github.com/elasticluster/elasticluster>`_. project, a tool that allows automated setup of compute clusters
(MPI, Spark/Hadoop, etc) and their management. CLAP extend the project by allowing a simplified interface to interact with the compute nodes.
Some of the features are:

- `YAML-Style <https://yaml.org/>`_. configuration files to define nodes, logins and cloud configurations
- User-friendly interface to create, setup, manage, interact and stop multiple computing nodes on different cloud providers at the same time
- Group system to easily perform actions in different heterogeneous nodes via `Ansible <https://ansible.com/>`_. playbooks
- Easy-to-use python API.

# CLAP Provides.........

..  toctree::
    :glob:
    :maxdepth: 2
    :titlesonly:
    :caption: Table of Contents
    :name: mastertoc

    installation
    configuration
    usage
    groups
    shared_groups
    pythonapi
    tutorials
    troubleshooting
    autoapi/index


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
