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

Setups and cluster section may be written in multiple different files (or at the same file), as CLAP's cluster modules will read all files (and setups and clusters configurations, respectively) inside the cluster's directory.

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

Some action examples are briefly shown below:

.. code-block:: yaml

    # Setup configurations must be declared inside setups key
    setups: 

        # This is a setup configuration called setup-common. The actions are executed sequentially
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

The cluster configuration defines a set of nodes that must be created and setups that must be executed. Clusters are written inside ``clusters`` YAML-dictionary key and each dictionary inside ``clusters`` key denotes a cluster (where the dictionary key is the cluster's name). Above is an example of a cluster configuration:

.. code-block:: yaml

  # Clusters must be defined inside clusters key
  clusters:
    # This is the cluster name
    my-cool-cluster-1:  
      # Nodes that must be created when a cluster is instantiated  
      nodes:
        # Node named master-node
        master-node:
          type: aws-instance-t2.large   # Instance type that must be created (must match instances.yaml name)
          count: 1                      # Number of instances that must be created
          setups:                       # Optionally, list of setups to be executed when the master-nodes is created (reference setup configuration names, at setups section)
          - another-example-setup
          - master-setup
        
        # Node named taskmanager
        slave-nodes:
          type: aws-instance-t2.small  # Instance type that must be created (must match instances.yaml name)
          count: 2                     # Number of instances that must be created
          min_count: 1                 # Minimum desired number of instances that must effectively be created
          setups:                      # Optionally, list of setups to be executed when the slave-nodes is created
          - setup-slave-node

Clusters must have the ``nodes`` section, which defines the nodes that must be created when the cluster is instantiated. As example above, each cluster's node have a name (``master-node`` and ``slave-node``) and values, that specify the cluster's node characteristics. Each node may have the values listed in is table below.

..  list-table:: code-block:: none Cluster's nodes valid parameters
    :header-rows: 1

    *   - **Name**
        - **Type**
        - **Description**

    *   - ``type``
        - string
        - Instance type that must to be created. The type must match the node name at ``instances.yaml`` file

    *   - ``count``
        - Positive integer
        - Number of instances of this type to be launched
    
    *   - ``min_count`` (OPTIONAL)
        - Positive integer (less then or equal ``count`` parameter)
        - Minimum number of instances of this type that must effectively be launched. If this parameter is not supplied the value of ``count`` parameter is assumed

    *   - ``setups``
        - List of strings
        - List with the name of the setup configurations that must be executed after nodes are created

When a cluster is created, the instance types specified in the each node section is created with the desired ``count`` number. The cluster is considered created when all nodes are effectively created. The ``min_count`` parameter at each node specify the minimum number of instances of that type that must effectively be launched. If some instances could not be instantiated, with less than ``min_count`` parameter, the cluster creation process fails and all nodes are terminated.

After the cluster is created, i.e. the minimum number of nodes of each type is successfully created, the ``setups`` for each node is executed, in order. If some setup does not execute correctly, the cluster remains created and the ``setup`` phase can be executed again.

Controlling cluster's setups execution phases
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

CLAP's cluster module also offers some other facilities to configure the cluster. By default the cluster module create nodes and run the setup from each node type. You can control the flow of the setup execution using some optional keys at your cluster configuration. The keys: ``before_all``, ``before``, ``after`` and ``after_all`` can be plugged into a cluster's configuration, in order to execute setups in different set of nodes, before and after the nodes setups. These keys takes a list of setups to execute.
CLAP's setup phases are executed in the order, as shown in table bellow.


..  list-table:: code-block:: none Cluster's setups execution phases (in order)
    :header-rows: 1

    *   - **Phase name**
        - **Description**

    *   - ``before_all``
        - Setups inside this key are executed in all cluster's nodes before specific setup of the nodes.

    *   - ``before``
        - Setups inside this key are executed only in nodes that are currently being added to the cluster, before the setup specific setup of the nodes. Its useful when resizing cluster, i.e., adding more nodes. This phase is always executed at cluster creation, as all created nodes are being added to the cluster.

    *   - ``node``
        - The setup for each node is executed, for the nodes that are being added to the cluster

    *   - ``after``
        - Setups inside this key are executed only in nodes that are currently being added to the cluster, after the setup specific setup of the nodes. Its useful when resizing cluster, i.e., adding more nodes. This phase is always executed at cluster creation, as all created nodes are being added to the cluster.

    *   - ``after_all``
        - Setups inside this key are executed in all cluster's nodes after specific setup of the nodes.

.. note:: 

  All setups are executed after the nodes are created and are all optional


An example is shown below:

.. code-block:: yaml

  # Clusters must be defined inside clusters key
  clusters:
    # This is the cluster name
    my-cool-cluster-1:  
      # These setups are executed at all cluster's nodes, before setups at nodes section
      before_all:
      - my-custom-setup-1

      # These setups are executed at nodes that are currently being added to cluster, before setups at nodes section
      before:
      - my-custom-setup-2

      # These setups are executed at nodes that are currently being added to cluster, after setups at nodes section
      after:
      - my-custom-setup-3
      - my-custom-setup-4

      # These setups are executed at all cluster's nodes, after setups at nodes section
      after_all:
      - final_setup

      # Nodes that must be created when a cluster is instantiated 
      nodes:
        # Node named master-node
        master-node:
          type: aws-instance-t2.large   # Instance type that must be created (must match instances.yaml name)
          count: 1                      # Number of instances that must be created
          setups:                       # Optionally, list of setups to be executed when the master-nodes is created (reference setup configuration names, at setups section)
          - another-example-setup
          - master-setup
        
        # Node named taskmanager
        slave-nodes:
          type: aws-instance-t2.small  # Instance type that must be created (must match instances.yaml name)
          count: 2                     # Number of instances that must be created
          min_count: 1                 # Minimum desired number of instances that must effectively be created
          setups:                      # Optionally, list of setups to be executed when the slave-nodes is created
          - setup-slave-node


In the above example, supposing you are creating a new cluster, thus after 1 ``master-node`` and 2 ``slave-nodes`` were created, the following setups are executed (in order):

- ``before_all`` setups: ``my-custom-setup-1`` at all nodes
- ``before`` setups: ``my-custom-setup-2`` at all nodes
- ``nodes`` setups (not necessary in order): ``another-example-setup``and ``master-setup`` at ``master-nodes`` nodes and ``setup-slave-node`` at ``slave-nodes`` nodes.
- ``after`` setups: ``my-custom-setup-3`` and ``my-custom-setup-4`` at all nodes
- ``after_all`` setups: ``final_setup`` at all nodes
    
Now supposing you are resizing the already created cluster (adding more ``slave-nodes`` to it), the ``before_all`` and ``after_all`` setups will be executed in all cluster's nodes (including the new ones, that are being added) and ``before``, ``nodes`` and ``after`` phase setups will only be executed at nodes that are being added to the the cluster.

Other cluster's setups optional keys
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The ``options`` key can be plugged at a cluster configuration allowing some special options to cluster. The ``options`` key may have the following parameters:

..  list-table:: code-block:: none Cluster's options keys
    :header-rows: 1

    *   - **Option name**
        - **Description**

    *   - ``ssh_to``
        - Connect to a specific node when performing the ``cluster connect`` command

A example is shown below:

.. code-block:: yaml

  # Clusters must be defined inside clusters key
  clusters:
    # This is the cluster name
    my-cool-cluster-1:  
      # Additional cluster's options (optional)
      options:
        # When connecting to a cluster, connect to a master-node 
        ssh_to: master-node

      # Nodes that must be created when a cluster is instantiated  
      nodes:
        # Node named master-node
        master-node:
          type: aws-instance-t2.large   # Instance type that must be created (must match instances.yaml name)
          count: 1                      # Number of instances that must be created
          setups:                       # Optionally, list of setups to be executed when the master-nodes is created (reference setup configuration names, at setups section)
          - another-example-setup
          - master-setup
        
        # Node named taskmanager
        slave-nodes:
          type: aws-instance-t2.small  # Instance type that must be created (must match instances.yaml name)
          count: 2                     # Number of instances that must be created
          min_count: 1                 # Minimum desired number of instances that must effectively be created
          setups:                      # Optionally, list of setups to be executed when the slave-nodes is created
          - setup-slave-node


Command ``cluster start``
++++++++++++++++++++++++++

Start a cluster given a cluster configuration name. The syntax of the command is shown below 

.. code-block:: none

  clapp cluster start [-h] [--file FILE] [--directory DIRECTORY] [--no-setup] [--extra ...] cluster_name

By default, the CLAP's cluster module search for configurations at all ``.yml`` files inside ``~/.clap/configs/clusters`` directory. This can be changed with ``--directory`` parameter. Or if you want to search for the cluster configuration at only one file, use the ``--file`` parameter.
After the cluster is created, the setups are automatically executed. You can omit this phase by using the ``--no-setup`` option.

The ``--extra`` parameter performs Jinja variable replacements at the cluster configuration files.

An example of the command is shown below, which starts and instantiate nodes from a cluster called ``my-cool-cluster-1``.

.. code-block:: none

  clapp cluster start my-cool-cluster-1

.. note::
  - After the cluster's creation a new ``cluster_id`` will be assigned to it. Thus, multiple clusters with same cluster configuration can be launched Also, all commands will reference to ``cluster_id`` to perform their actions.
  - When a cluster is started its initial configuration is copied to cluster metadata. If you update the cluster configuration while having already started clusters use the ``clapp cluster update`` command to update the cluster configuration.


Command ``cluster setup``
++++++++++++++++++++++++++

Setup an existing cluster. The command has the following syntax:

.. code-block:: none

  clapp cluster setup [-h] [--readd-group] [--nodes NODES] [--at [AT]] cluster_id

Given the ``cluster_id``, the command will execute all setup phases in all cluster nodes. Some phases of the setup pipeline can be skipped informing at which phase the setup must begin with the ``at`` parameter. Also, if you want to execute the setup only in selected nodes of the cluster you can use the ``nodes`` parameter, passing the node ids. Finally, the ``readd-group`` option specify if nodes must be added to a group, even if they are already on them.

Examples are shown below:

.. code-block:: none

  clapp cluster setup cluster-0
  clapp cluster setup cluster-0 --at "before"
  clapp cluster setup cluster-0 --nodes node-4 node-5

In the above examples, the first one setups all cluster nodes from ``cluster-0``, the second one setups all nodes, but starting at ``before`` phase and the third one setup only ``node-4`` and ``node-5`` of cluster ``cluster-0``.

.. note::
  The ``before_all`` and ``after_all`` phases will be executed at all cluster's nodes, even if setting the ``nodes`` parameter.


Command ``cluster add``
++++++++++++++++++++++++++

Start and add a new node to cluster, based on its cluster's node name. The command has the following syntax:

.. code-block:: none

  clapp cluster add [-h] [--readd-group] [--at [AT]] [--no-setup] cluster_id node_type:num [node_type:num ...]

The ``node_type:num`` parameter determines how much nodes will be added to cluster. If ``--no-setup`` is provided no setup phase will be executed, else the setup phase to be executed can be controlled with ``--at`` parameter. Finally, the ``readd-group`` option specify if nodes must be added to a group, even if they are already on them.

Examples are shown below:

.. code-block:: none

  clapp cluster add cluster-0 slave-nodes:2

In the above example, two ``slave-nodes`` will be added to cluster ``cluster-0`` and all setup phases will be executed.


Command ``cluster add-existing``
++++++++++++++++++++++++++++++++++

Add an already started CLAP's node to a cluster. The command has the following syntax:

.. code-block:: none

  clapp cluster add-existing [-h] [--readd-group] [--at [AT]] [--no-setup] cluster_id node_type node_ids [node_ids ...]

The command allow to add multiple started nodes by its node IDs (``node_ids`` parameter) to a already started cluster. The nodes will be added as the cluster's node type, defined by ``node_type`` parameter If ``--no-setup`` is provided no setup phase will be executed, else the setup phase to be executed can be controlled with ``--at`` parameter. Finally, the ``readd-group`` option specify if nodes must be added to a group, even if they are already on them.

Examples are shown below:

.. code-block:: none

  clapp cluster add-existing cluster-0 slave-nodes node-0 node-1 node-2

In the above example, nodes ``node-0``, ``node-1`` and ``node-2``  will be added to cluster ``cluster-0`` as ``slave-nodes`` cluster's node type and all setup phases will be executed.

Command ``cluster list``
++++++++++++++++++++++++++

List all available CLAP's clusters. The command has the following syntax:

.. code-block:: none

  clapp cluster list [-h] [--id ID] [--full]

Optionally, if ``--id`` parameter is passed, only a cluster with this ID is listed. Also, if ``--full`` parameter is passed it will print all cluster information, including it's configuration used.

An output example is shown below:

.. code-block:: none

  creation time: 01-01-20 00:00:00
  id: cluster-0
  name: my-cool-cluster-1
  nodes:
      master-node:
      - node-0
      slave-node:
      - node-1
      - node-2
  state: running
  update time: 01-15-20 00:01:40

Command ``cluster alive``
++++++++++++++++++++++++++

Check if all nodes of the cluster are alive. The command has the following syntax:

.. code-block:: none

  clapp cluster alive [-h] cluster_id

.. note::

  The ``clapp cluster alive`` command also updates the nodes connection's IP and can be very useful when node's IP changes (e.g. and stopped node comes alive or when using floating IPs). As CLAP is an ad-hoc tool and does not monitor each node, its recommended to run this command periodically to update nodes information.

Command ``cluster resume``
++++++++++++++++++++++++++

Resume all nodes of the cluster. The command has the following syntax:

.. code-block:: none

  clapp cluster resume [-h] [--setup] [--at [AT]] cluster_id

Given a ``cluster_id`` all nodes in the cluster will be resumed. If option ``setup`` is set, it also runs setups in nodes. The ``at`` parameter controls the setup phase. 

Command ``cluster pause``
++++++++++++++++++++++++++

Pause all nodes of the cluster. The command has the following syntax:

.. code-block:: none

  clapp cluster pause [-h] cluster_id

Given a ``cluster_id`` all nodes in the cluster will be paused.

.. note::

  If a node belongs to more than one cluster, it will only be paused if all clusters that contains this node is paused.


Command ``cluster stop``
++++++++++++++++++++++++++

Stop all nodes of the cluster. The command has the following syntax:

.. code-block:: none

  clapp cluster stop [-h] cluster_id

Given a ``cluster_id`` all nodes in the cluster will be stopped.

.. note::

  If a node belongs to more than one cluster, it will only be stopped if all clusters that contains this node are stopped. Else, the node is just removed from the cluster.


Command ``cluster list-templates``
+++++++++++++++++++++++++++++++++++

List all available cluster templates at directory. The command has the following syntax:

.. code-block:: none

  clapp cluster list-templates [-h] [--file FILE] [--directory DIRECTORY]

All clusters at ``~/clap/configs/clusters`` directory will be listed. A different directory can be specified with ``--directory`` parameter. If the ``--file`` parameter is passed, clusters will only be listed from this file.


Command ``cluster update``
+++++++++++++++++++++++++++++

Update a cluster configuration from a created cluster. The command has the following syntax:

.. code-block:: none

  clapp cluster update [-h] [--file FILE] [--directory DIRECTORY] [--extra ...] cluster_id

By default, the cluster's configuration and its name is stored when a cluster is created. If you update configurations files, you can update a running cluster's configuration using this command (note, the cluster configuration name must not change). 

Clusters will be searched at ``~/clap/configs/clusters`` directory. A different directory can be specified with ``--directory`` parameter. If the ``--file`` parameter is passed, clusters will only be listed from this file. Finally ``--extra`` parameter is used to perform Jinja replacements.


Command ``cluster group``
+++++++++++++++++++++++++++++

Add cluster's nodes to a group. The command has the following syntax:

.. code-block:: none

  clapp cluster group [-h] [--nodes NODES [NODES ...]] [--readd-group] [--extra ...] cluster_id group

Given a ``cluster_id``, adds all nodes belonging to this cluster to the group, informed by ``group`` parameter. If the ``--readd-group`` option is set nodes will be added to a group, even if they are already on them. Nodes of cluster can be filtered using the ``--nodes`` parameter. Finally, the ``--extra`` parameter pass keyword variables to the group's setup action.

Examples are shown below:

.. code-block:: none

  clapp cluster group cluster-0 commands-common
  clapp cluster group cluster-0 commands-common --nodes node-0 node-1
  clapp cluster group cluster-0 commands-common --nodes node-0 node-1 --extra "foo=bar"

In the above examples, the first one adds all nodes from ``cluster-0`` to the group ``commands-common``. The second one, added only nodes ``node-0`` and ``node-1`` from ``cluster-0`` to the group ``commands-common``. The third one is similar to the second one but pass the variable ``foo`` with value ``bar`` to the ``commands-common setup`` action.


Command ``cluster action``
+++++++++++++++++++++++++++++

Perform a group action to cluster's nodes. The command has the following syntax:

.. code-block:: none

  clapp cluster action [-h] [--nodes NODES [NODES ...]] [--extra ...] cluster_id group action

Given a ``cluster_id``, it will perform a group action, informed by ``group`` and ``action`` parameters, to all nodes of the cluster. Nodes of cluster can be filtered using the ``--nodes`` parameter. Finally, the ``--extra`` parameter pass keyword variables to the group's action.

Examples are shown below:

.. code-block:: none

  clapp cluster action cluster-0 commands-common update-packages
  clapp cluster action cluster-0 commands-common update-packages --nodes node-0 node-1
  clapp cluster action cluster-0 commands-common update-packages --nodes node-0 node-1 --extra "foo=bar"

In the above examples, the first one adds perform the ``update-packages`` action from ``commands-common`` group at all nodes of cluster ``cluster-0``. The second one, perform the ``update-packages`` action from ``commands-common`` group only at nodes ``node-0`` and ``node-1`` from ``cluster-0`. The third one is similar to the second one but pass the variable ``foo`` with value ``bar`` to the ``commands-common update-packages`` action.

.. note::

  The action is performed only in nodes of cluster that belongs to the specified group


Command ``cluster connect``
+++++++++++++++++++++++++++++

Get a SSH shell to a node of the cluster. The command has the following syntax:

.. code-block:: none

  clapp cluster connect [-h] [--node NODE] cluster_id

Given a ``cluster_id`` it will try to get an SSH shell to a node type specified in ``ssh_to`` cluster configuration option. If no ``ssh_to`` option is informed at cluster's configuration the ``--node`` parameter must be informed. If the ``--node`` parameter is informed an SSH shell from that node will be get.


Command ``cluster execute``
+++++++++++++++++++++++++++++

Execute a shell command in nodes of the cluster. The command has the following syntax:

.. code-block:: none

  clapp cluster execute [-h] [--nodes NODES [NODES ...]] --command COMMAND cluster_id

Given a ``cluster_id`` execute the string command passed from ``command`` parameter in cluster's nodes. The ``--nodes`` parameters can be populated with the cluster's nodes ids to limit the execution of the command to these nodes.

Examples are shown below:

.. code-block:: none

  clapp cluster execute --command "ls -lha" cluster-0
  clapp cluster execute --command "ls -lha" cluster-0 --nodes node-0 node-1

In the above examples, the first one execute the command ``ls -lha`` in all cluster ``cluster-0`` nodes. The second ne is similar to the first, but execute the command in nodes ``node-0`` and ``node-1`` only.


Command ``cluster playbook``
+++++++++++++++++++++++++++++

Execute an Ansible Playbook in nodes of the cluster. The command has the following syntax:

.. code-block:: none

  clapp cluster playbook [-h] [--nodes NODES [NODES ...]] [--extra ...] cluster_id playbook_file

Given a ``cluster_id``, the Ansible playbook located at the informed parameter ``playbook_file`` is executed. The ``--nodes`` parameters can be populated with the cluster's nodes ids to limit the execution of the playbook to these nodes. Finally, the ``--extra`` parameter pass keyword variables to the playbook.

Examples are shown below:

.. code-block:: none

  clapp cluster playbook cluster-0 /home/my-playbook.yml
  clapp cluster playbook cluster-0 /home/my-playbook.yml --nodes node-0 node-1
  clapp cluster playbook cluster-0 /home/my-playbook.yml --nodes node-0 node-1 --extra "foo=bar" "var1=abaco"

In the above examples, the first one execute the playbook ``/home/my-playbook.yml`` at all cluster's nodes. The second one also execute the ``/home/my-playbook.yml`` playbook, but limiting to nodes ``node-0`` and ``node-1`` only. The third one is similar to the second, but also pass the extra variables ``foo`` and ``var1`` with values ``bar`` and ``abaco`` (respectively) to the playbook.


Command ``cluster copy``
+++++++++++++++++++++++++++++

Copy files from the localhost to all cluster's nodes. The command has the following syntax:

.. code-block:: none

  clapp cluster copy [-h] [--nodes NODES [NODES ...]] cluster_id from dest

Given a ``cluster_id``, the files informed at ``from`` parameter are all copied (recursively) from localhost to the ``dest`` directory at all nodes. 

Examples are shown below:

.. code-block:: none

  clapp cluster copy cluster-0 /home/my-file "{{ ansible_env.HOME }}/my-folder"
  clapp cluster copy cluster-0 /home/my-directory/ "{{ ansible_env.HOME }}/my-folder" --nodes node-0

In the above examples, the first one will copy the file at ``/home/my-file`` (from localhost) to nodes ``"{{ ansible_env.HOME }}/my-folder"`` directory (see notes below). The second one will copy the  directory at  ``/home/my-directory/`` (from localhost) to node's ``node-0`` ``"{{ ansible_env.HOME }}/my-folder"`` directory (see notes below).

.. note::

  - Use the value ``"{{ ansible_env.HOME }}"`` as a special variable to access a node's user home directory. 
  - The command uses the `rsync copy format <https://rsync.samba.org/>`_ to select files to copy.
  


Command ``cluster fetch``
+++++++++++++++++++++++++++++

Fetch files from remote nodes to localhost. The command has the following syntax:

.. code-block:: none

  clapp cluster fetch [-h] [--nodes NODES [NODES ...]] cluster_id from dest

Given a ``cluster_id``, the files informed at ``from`` parameter are all copied (recursively) from the cluster's nodes to the ``dest`` directory at localhost.

Examples are shown below:

.. code-block:: none

  clapp cluster fetch cluster-0 "{{ ansible_env.HOME }}/my-file" /home/my-directory
  clapp cluster fetch cluster-0 "{{ ansible_env.HOME }}/my-folder" /home/my-directory/ --nodes node-0

In the above examples, the first one will fetch the file at ``"{{ ansible_env.HOME }}/my-folder"`` from cluster's nodes (see notes below) to the localhost's ``/home/my-directory"`` directory. The second one will fetch the  directory at ``"{{ ansible_env.HOME }}/my-folder"`` from cluster's nodes ``node-0`` (see notes below) to the localhost's ``/home/my-directory"`` directory.


.. note::

  - Use the value ``"{{ ansible_env.HOME }}"`` as a special variable to access a node's user home directory. 
  - The command uses the `rsync copy format <https://rsync.samba.org/>`_ to select files to fetch.