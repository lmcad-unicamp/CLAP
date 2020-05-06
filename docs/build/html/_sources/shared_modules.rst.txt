.. _shared modules:

==========================
Modules shared with CLAP
==========================

.. _cluster module:
Cluster Module
-------------------

The cluster module allows CLAP to work with cluster, which is a set of CLAP's nodes tagged with a specific tag. A CLAP's cluster is created taking as input configuration files, in YAML format, which will create nodes and setup each of them properly. After created, the cluster can be resized (adding or removing nodes), paused, resumed, stopped, among other things.
By default, the CLAP's cluster module will find configurations inside ``~/clap/configs/clusters`` directory. At next sections, we will assume that files will be created inside this directory (in ``.yml`` format). 

The next section will guide you to write a cluster configuration and then, module's commands will be presented.

Cluster Configuration
++++++++++++++++++++++++++

To create a CLAP's cluster you will need to write:

- **Setup configuration sections**: which define a series of groups and actions that must be performed.
- **Cluster configuration sections**: which define a set of nodes that must be created and the setups that must be performed in each node.

Setups and cluster section may be written in multiple different files, as CLAP's cluster modules will read all files (and setups and clusters configurations, respectively) inside the cluster's directory.

.. note::

    Cluster's configuration files accepts `Jinja-like variables <https://jinja.palletsprojects.com>`_ that can be populated using ``--extra`` parameters at each cluster's commands. Any part of the configuration can use Jinja-like variables.

Setup Configuration Sections
+++++++++++++++++++++++++++++

Setup configuration sections define a series of groups and/or actions that must be performed cluster's nodes. An example of a setup configuration section is shown below.

.. code-block:: yaml

    # Setup configurations must be declared inside setups key
    setups: 

        # This is a setup configuration called setup-common
        setup-common:
            groups: 
            - name: commands-common     # Add nodes to commands-common group 
            - name: example-group       # Add nodes to example-group group 

            actions:
            - type: action              # Perform action update-packages from group commands-common at nodes
              name: update-packages
              group: commands-common

        # This is a setup configuration called setup-spits-jobmanager
        setup-spits-jobmanager:
            groups:
            - name: spits/jobmanager   # Add nodes to spits/jobmanager group 

        # This is a setup configuration called setup-spits-taskmanager
        setup-spits-taskmanager:
            groups:
            - name: spits/taskmanager   # Add nodes to spits/taskmanager group 

Setup configurations must be written inside ``setups`` YAML-dictionary. You can define as many setup configurations as you want, even at different files (since inside the ``setups`` YAML-dictionary), but each one must have a unique name.
Inside the ``setups`` section, each dictionary represents a setup configuration. The dictionary key (``setup-common``, ``setup-spits-jobmanager`` and ``setup-spits-taskmanager`` in above example) represent the setup configuration ID.

Each setup configuration may contain two dictionaries: ``groups`` and ``actions`` (both are optional). Both sections, for a setup configuration is described in the next two subsections.

Groups key at an setups configuration
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The ``groups`` section inside a setup configuration tells to add nodes, which perform this setup, to the defined groups. The ``groups`` section contains a **list** describing each group that the nodes must be added. Also, the groups is always added in the order defined in the list.

Each element of the list must have a ``name`` key, which describe the name of the group that the node must be added.
For instance, the ``setup-common`` at above example, defines two groups which nodes that perform this setup must be added: ``commands-common`` and ``example-group`` (in this order).

Optionally an ``extra`` key can be defined by each group, as a dictionary. The key and values is passed as ``extra`` parameter to the ``group add`` module command.
For instance, the setup below, will add nodes that perform this setup (``setup-common-2``) to group ``example-group`` passing variables, ``foo`` and ``another_var`` with values ``bar`` and ``10``, respectively.

.. code-block:: yaml

    # Setup configurations must be declared inside setups key
    setups: 

        # This is a setup configuration called setup-common
        setup-common-2:
            groups: 
            - name: example-group     # Add nodes to example-group group
              extra:
                foo: bar
                another_var: 10


Actions key at an setups configuration
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The ``actions`` section inside a setup configuration tells to perform actions at nodes which perform this setup. The ``actions`` section contains a **list** describing each action that must be performed (in order). Each element of the action list must have a type.
A type may have three values:

- **action**: will perform an group action. Thus, the ``group`` and ``name`` key must be informed. The ``group`` key will tell the name of the group and the ``name`` key will tell which action from that group which will be performed. Optionally, an ``extra`` dictionary can be informed to pass keyword variables to the group's action.
- **playbook**: will execute an Ansible Playbook. Thus, the ``path`` key must be informed, telling the absolute path of the playbook that will be executed. Optionally an ``extra`` dictionary can be informed to pass keyword variables to the playbook.
- **command**: will execute a shell command. Thus, the ``command`` key must be informed, telling which shell command must be executed.

Some actions example are briefly shown below:

.. code-block:: yaml

    # Setup configurations must be declared inside setups key
    setups: 

        # This is a setup configuration called setup-common
        another-setup-example:
            actions: 
            
            # Perform mount action from group nfs-client, passing the variable mount_path with value /mnt
            - type: action
              name: mount 
              group: nfs-client
              extra:
                mount_path: /mnt
            
            # Execute the playbook /home/my-cool-ansible-playbook with an variable foo with value bar
            - type: playbook
              path: /home/my-cool-ansible-playbook
              extra:
                foo: bar

            # Execute a shell command: hostname
            - type: command
              command: hostname

            # Perform reboot action from commands-common group
            - type: action
              group: commands-common
              name: reboot

.. note:: 
    
    If a setup configuration contains both ``groups`` and ``actions`` sections, commands at ``groups`` section will **always** be executed before ``actions``.


Cluster Configuration Sections
++++++++++++++++++++++++++++++

XXXX


Command ``cluster start``
++++++++++++++++++++++++++
After
