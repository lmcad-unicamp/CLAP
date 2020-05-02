=====================================================
Welcome to CLoud Application Platform Documentation!
=====================================================

---------------
Introduction
---------------

CLoud Application Platform (CLAP) provides a interface to manage, interact and deploy HPC applications hosted in different cloud providers.
CLAP is firstly inspired on  `elasticluster <https://github.com/elasticluster/elasticluster>`_. project, a tool that allows automated setup of compute clusters (MPI, Spark/Hadoop, etc) and their management and `Ansible <https://www.ansible.com/integrations/cloud>`_, a framework used for automation.
CLAP provide user-friendly command line tool to create, manage and interact with individual nodes or a set of nodes hosted in public cloud providers (such as AWS, Google Cloud and Microsoft Azure), as well as easily create, manages, resize and interact with computer clusters hosted in public cloud providers.
The main features of CLAP includes:

- `YAML-Style <https://yaml.org/>`_. configuration files to define nodes, logins and cloud configurations
- User-friendly interface to create, setup, manage, interact and stop multiple computing nodes on different cloud providers at the same time
- Easy and fast creation and configuration of multiple compute clusters hosted in public cloud providers at same time
- Growing and shrinking a running cluster
- Group system to easily perform actions in different heterogeneous nodes via `Ansible <https://ansible.com/>`_. playbooks
- Easy-to-use python API to bring nodes up and configure them (via ansible or SSH commands)

---------------
Contents
---------------

..  toctree::
    :maxdepth: 2

    introduction
    configuration
    usage
    autoapi/index


-------------------
Indices and tables
-------------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
