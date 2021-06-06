=====================================================
Welcome to CLoud Application Provider Documentation!
=====================================================


Introduction
---------------

CLoud Application Provider (CLAP) provides a user-friendly command line tool to
create, manage and interact with individual instances or a set of instances
hosted in public cloud providers (such as AWS, Google Cloud and Microsoft Azure),
as well as easily creates, manages, resizes and interacts with compute clusters
hosted in public cloud providers.
It was firstly inspired on `elasticluster <https://github.com/elasticluster/elasticluster>`_
project, a tool that allows automated setup of compute clusters (MPI, Spark/Hadoop, etc.)
and `Ansible <https://www.ansible.com/integrations/cloud>`_, a framework used for
automation.

Its main features includes:

- | `YAML-Style <https://yaml.org/>`_ configuration files to define nodes, logins and cloud configurations.
- User-friendly interface to create, setup, manage, interact and stop multiple instances hosted different cloud providers at the same time, transparently.
- Easy and fast creation and configuration of multiple compute clusters hosted in public cloud providers at same time.
- Growing and shrinking running clusters.
- Role system to easily perform actions in different heterogeneous nodes via `Ansible <https://ansible.com/>`_. playbooks.
- Easy-to-use python API to bring nodes up and configure them (via ansible or SSH commands).

Contents
---------------

..  toctree::
    :maxdepth: 2

    introduction
    configuration
    usage
    shared_roles
    api

Indices and tables
+++++++++++++++++++

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

