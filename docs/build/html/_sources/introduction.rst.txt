.. _installation:

==========================
Introduction
==========================

Installation Guide
---------------------


To install CLAP in a linux-based system follow the instructions below.

1. Install requirement packages

.. code-block:: bash

    gcc g++ git libc6-dev libffi-dev libssl-dev virtualenv python3 python3-pip python3-venv

.. note::

    CLAP requires Python 3.7 or higher.


2.  Clone the git repository and enter inside clap's directory 

.. code-block:: bash

    git clone https://github.com/lmcad-unicamp/CLAP.git clap
    cd clap

3.  Set execution flags of the install script  using the ``chmod`` command.
Then just run the ``install.sh`` script!

.. code-block:: bash

    chmod +x install.sh
    ./install.sh

4.  To use CLAP, you will need to activate the ``virtual-env``, for each shell you are using it.
    Inside the ``clap`` root directory, where the ``git`` repository was cloned use the following command:

.. code-block:: bash

    source clap-env/bin/activate

5. Finally, test CLAP, via the CLI interface. The ``clapp`` command should be
available to use at this point.

.. code-block:: bash

    clapp --help

    clapp node list

.. note::

    As CLAP is at development stage, use the ``update.sh`` periodically to fetch updates!


Quickly CLAP usage description
------------------------------------

To use CLAP you will first need to provide some information about how to launch instances in the cloud. By default, CLAP holds all information about configurations in the ``~/.clap/configs`` directory. The ``~/.clap/configs/providers.yaml`` file describes how to connect to the cloud provider, the ``~/.clap/configs/logins.yaml`` file describes how to login into machines and the ``~/.clap/configs/instances.yaml`` describe the instances that can be used with CLAP. 
The :ref:`configuration section <configuration>` will guide you to write all these configuration sections easily.

Once configurations written, the :ref:`usage section <usage>` will show you how to execute CLAP commands based on the configurations written.
CLAP can be used to start, configure and manage single or multiple cloud's instances using the :ref:`node module <node section>` as well as entire compute clusters using the :ref:`cluster module <cluster module>`.


.. _clap directory archtecture:

Quickly CLAP directory architecture description
-----------------------------------------------
By default, CLAP holds all of it information needed inside the ``~/.clap``
directory (where ``~`` stands for the user home directory). The minimal structure
of ``~/.clap`` directory is shown below:

.. code-block::

    ~/ (home directory)
    └── .clap/
        ├── configs/
        │   ├── clusters/
        │   ├── instances.yaml
        │   ├── logins.yaml
        │   └── providers.yaml
        ├── roles/
        │   ├── actions.d/
        │   ├── group_vars/
        │   │   └── all.yml
        │   └── roles/
        ├── private/
        └── storage/


- The ``~/.clap/configs/providers.yaml`` `YAML <https://yaml.org/>`_ file inside the ``~/.clap/configs`` directory holds the information about the cloud provider and how to connect to it.

- The ``~/.clap/configs/logins.yaml`` file holds information about how to connect to an instance (e.g. login user, keyfile, etc)

- The ``~/.clap/configs/instances.yaml`` holds the information about the instances to launch, i.e. the instance templates.

- The ``roles`` directory store role's files and actions, used to perform action in several nodes. For more detailed information about roles and actions refer to the :ref:`roles section <role section>`

- The ``private`` stores keys and passwords files used to connect to the cloud provider and to the instance itself. Every key/secret files needed in the configuration files must be placed inside this directory (usually with 0400 permissions).

- The ``storage`` directory store metadata information used by CLAP.
