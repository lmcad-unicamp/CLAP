.. _usage:

=============
Basic Usage
=============

CLAP is a platform to start, stop and manage cloud's instances (called CLAP nodes or simply ,nodes) at different cloud providers transparently, based on configuration files. Also, it offers mechanisms to perform actions via SSH commands or Ansible playboks in single nodes or in a set of nodes in a row.
To provide this, in a modular way, CLAP provides modules to allow performing several operations (see <ARCH> section for more information about the CLAP architecture). You can use ``clapp --help`` command to list the available modules or ``clapp -v --show-all`` to show all available commands that can be used. 

The most common modules are: ``node``, ``tags`` and ``groups``.

.. One of the most common modules is the ``node`` module which can be used to perform operations with single or multiple instances in a row. The commands of this module is detailed in the next section. Other modules such as ``cluster``, can be used to manage entire clusters (see section <CLUSTER> for more details).

.. _node section:

Node Module
---------------------

The node module provides mechanisms to create, manage and interact with cloud's instances. It provides the following features:

* Start nodes based on the instance templates with the ``start`` command
* Stop (terminate) already started nodes using the ``stop`` command
* Pause or resume already instantiated nodes using the ``pause`` and ``resume`` commands, respectively
* Check the status of a node (if its accessible by SSH) using the ``alive`` command
* List started nodes using the ``list`` command
* Execute a shell command via SSH, using the ``execute`` command
* Execute an Ansible Playbook using the ``playbook`` command
* Obtain a shell session (via SSH) using the ``connect`` command

All these commands are detailed below.


Command ``node start``
+++++++++++++++++++++++++++

To launch a cloud's instance based on an instance template, defined in the ``~/.clap/configs/instances.yaml`` file, you can use the command below, where the ``ubuntu-instance-aws`` refers to the instance template ID defined in the ``~/.clap/configs/instances.yaml`` file. In this way, you need to configure the files only once and launch instances at any time.

.. code-block:: none

    clapp node start ubuntu-instance-aws

Once instances are successfully started, CLAP will assign an unique node ID to each instance, used to perform other CLAP operation. Also, CLAP will try to login at the instance with the login information provided (via SSH).

To launch more than one instance with the same instance template ID, you can put the desired number after the instance template ID preceded by an ``:``. For instance, the command below, launches 4 ``ubuntu-instance-aws`` instances in a row.

.. code-block:: none

    clapp node start ubuntu-instance-aws:4


You can also launch different instances in a row using the same command, but just appending more instance template IDs to it, as below. The above command launches 2 ``ubuntu-instance-aws`` machines and 2 ``example-instance-aws`` machines in a row.

.. code-block:: none

    clapp node start ubuntu-instance-aws:2 example-instance-aws:2


Command ``node list``
+++++++++++++++++++++++++++

The ``clapp node list`` command can be used to show managed CLAP nodes. An example output of this command is shown below.

.. code-block:: none

    *  Node(id=`node-0`, type=`ubuntu-instance-aws`, status=`reachable`, public_ip=`54.152.26.1`, groups=``, tags=``, last_update=`02-05-20 14:48:04`
    *  Node(id=`node-1`, type=`example-instance`, status=`reachable`, public_ip=`3.90.153.213`, groups=``, tags=``, last_update=`02-05-20 14:48:04`
    Listed 2 node(s)

The node id (``node-0`` and ``node-1`` in the above example) is used across all other modules and commands to perform commands in the specific node.


Command ``node alive``
+++++++++++++++++++++++++++

After the node is started, you can check if it is alive using the command ``clapp node alive``. The command has the following sintax:

.. code-block:: none

    clapp node alive [-h] [--tag TAG] [node_ids [node_ids ...]]

One or more node ids can be supplied to the command to check their aliveness. If no node id is supplied, all CLAP nodes is checked for their aliveness. Optionally you can filter nodes based in their tags (see :ref:`tags section <tags section>`). 

The ``clapp node alive`` command also updates the node status. Thus, each node can have the following status:

* **started**:  when the cloud's instance is successfully launched
* **reachable**: when the SSH login was successfully performed
* **unreachable**: when the login was not successfully performed
* **paused**: when node is paused

.. note::
    The ``clapp node alive`` command also updates the node connection IP and can be very useful when the node IP changes (e.g. and stopped node comes alive or when using floating IPs). As CLAP is an ad-hoc tool and does not monitor each node, its recommended to run this command periodically to update nodes information.


Command ``node show``
+++++++++++++++++++++++++++

For more detailed information of a CLAP node, you can use the ``clapp node show`` command, which have the sintax showed bellow. The node id is the unique ID associated to each CLAP node when it is started.

.. code-block:: none

    clapp node show [-h] [--tag TAG] [node_ids [node_ids ...]]

One or more node ids can be supplied to the command to show information. If no node id is supplied, all CLAP nodes is shown. Optionally you can filter nodes based in their tags (see :ref:`tags section <tags section>`).



Command ``node stop``
+++++++++++++++++++++++++++

The ``clapp node stop`` command can be used to **terminate** an running instance (destroying it). The sintax is shown below:

.. code-block:: none

    clapp node stop  [-h] [--tag TAG] node_ids [node_ids ...]

One or more node ids can be supplied to the command to stop them. Optionally you can filter nodes based in their tags (see :ref:`tags section <tags section>`). 


Command ``node pause``
+++++++++++++++++++++++++++

The ``clapp node pause`` command can be used to **pause** an running instance. The sintax is shown below:

.. code-block:: none

    clapp node pause [-h] [--tag TAG] node_ids [node_ids ...]

One or more node ids can be supplied to the command to pause them. Optionally you can filter nodes based in their tags (see :ref:`tags section <tags section>`). 
When a node is paused, it state is changed to **paused** and it's public IP is changed to ``None``.

.. note::

    The command has no effect for nodes that already been paused.


Command ``node resume``
+++++++++++++++++++++++++++

The ``clapp node resume`` command can be used to **resume** an paused instance. The sintax is shown below:

.. code-block:: none

    clapp node resume [-h] [--tag TAG] node_ids [node_ids ...]

One or more node ids can be supplied to the command to resume them. Optionally you can filter nodes based in their tags (see :ref:`tags section <tags section>`). 
When a node is resumed, it state is changed to **started**. Then, it checked if it is alive, testing its connection and updating its public I (changing its state to **reachable**).

.. note::

    The command has no effect for nodes have not been paused, it will only check for its aliveness.


Command ``node connect``
+++++++++++++++++++++++++++

The ``clapp node connect`` command can be used to obtain a shell to a specific node. The sintax is shown below:

.. code-block:: none

    clapp node connect [-h] node_id

.. note::

    The connection may fail if node has an invalid public IP or a invalid login information. You may want to check if node is alive firstto update node's information.


Command ``node execute``
+++++++++++++++++++++++++++

The ``clapp node execute`` command can be used to execute a shell command on an reachable node. The sintax is shown below:

.. code-block:: none

    clapp node execute [-h] [--tag TAG] --command command [node_ids [node_ids ...]]


One or more node ids can be supplied to the command to execute the provided command in all of them. Optionally you can filter nodes based in their tags (see :ref:`tags section <tags section>`). 
The ``--command`` parameter specify the command that will be executed in nodes. An example is shwon below, executing a simple ``ls -lha`` command in nodes ``node-0`` and ``node-1``.

.. code-block:: none

    clapp node execute --command "ls -lha" node-0 node-1

.. note::

    Nodes that cannot be reachable will be ignored. You may want to check for nodes aliveness first.


Command ``node playbook``
+++++++++++++++++++++++++++

The ``clapp node playbook`` command can be used to execute an Ansible playbook in a set of reachable nodes. The sintax is shown below:

.. code-block:: none

    clapp node playbook [-h] [--tag TAG] [--extra ...] playbook_file [node_ids [node_ids ...]]

One or more node ids can be supplied to the command in order to execute the playbook in all of them. Optionally you can filter nodes based in their tags (see :ref:`tags section <tags section>`). The playbook file must be a valid playbook file and the extra parameter is used if you want to pass keyword values to your playbook, and must be passed in the ``key=value`` format. 

An example is shwon below. The playbook ``playbook.yml`` is executed in nodes ``node-0`` and ``node-1``. Extra playbook variables (jinja format, e.g. "{{ var1 }}") will be replaced by the extra variables informed. In the example below the playbook's variable ``var1`` will be replaced by ``value of var 1`` and the playbook's variable ``anothervar`` will be replaced by ``10``.

.. code-block:: none

    clapp node playbook  playbook.yml node-0 node-1 --extra "var1=value of var 1" "anothervar= 10"

.. note::

    * For this command, the ``extra`` paramter **must be the last** parameter.
    * The Ansible playbook must use **hosts: all** as all select CLAP nodes will be put in the inventory as a single host. To specify different hosts in you playbook use the :ref:`group command <group section>`, described in later sections.


.. _tags section:

Tags Module 
-------------------

The tags module provides mechanisms to add and remove tags at CLAP's nodes. Tags are efficient ways to select CLAP nodes. For instance, several comamands from ``node`` module has support to select nodes to limit to nodes which it will actuate.
A tag is just a key (string) which have its list of values (list of strings), thus you can have multiple values for same key.

Command ``tag add``
+++++++++++++++++++++

This ``clapp tag add`` command adds a tag to a set of nodes and has the following sintax:

.. code-block:: none

    clapp tag add [-h] tag node_ids [node_ids ...]

The ``tag`` parameter must be a keyword value in the format ``key=value``. You can add as many tags to a node as you want. If you add more than one tag with same key, the values are appended to the key. An example of adding tags is shown below:

.. code-block:: none

    clapp tag add x=y node-0 node-1

Where tag ``x=y`` is added to nodes ``node-0`` and ``node-1``. If you add another tag, ``x=z`` to same nodes, for instance, each node will have tags: ``x=y,z``.


Command ``tag remove``
++++++++++++++++++++++++

This ``clapp tag remove`` command removes a tag from a set of nodes and has the following sintax:

.. code-block:: none

    clapp tag remove [-h] tag node_ids [node_ids ...]

If the ``tag`` is a keyword value, such as ``x=y``, the value ``y`` will be removed from tag ``x`` from the speficied nodes. If the ``tag`` keyword is not a keyword value, such as simply ``x``, all values from tag ``x`` will be removed (and also the tag ``x``) from specified nodes. 


.. _group section:

Group Module 
-------------------

The group module allows to perform pre-defined actions to a set of nodes that belongs to a group. When a node is added to a group, it is said that this node plays a role in that group.
Thus, each group defines their set of specific actions that can be performed to nodes that belongs to that particular group.

In this way, the group module consists of three steps:

1. Add nodes to a group.
2. Perform group's action to nodes that belongs to a group.
3. Optionally, remove nodes from the group.

.. The next section describes how groups can be implemented. You can see the groups commands at section 


CLAP's groups and actions
++++++++++++++++++++++++++++++

Group's actions are `Ansible playbooks <https://www.ansible.com/>`_ that are executed when an action is invoked (using ``group action`` command, described below). By default CLAP's groups are stored in the ``~/.clap/groups/`` directory and each group consists in at minimum of two files: (1) a python file describing the group and its actions and; (2) the Ansible Playbook called when each action is invoked. 
By default, when each action is invoked a variable called ``action`` is passed to the Ansible Playbook with the name of the invoked action. 
You can see some groups shared with CLAP and their requirements at :ref:`shared groups` section.


Group description file
^^^^^^^^^^^^^^^^^^^^^^^

The group's description files are python files placed at ``~/.clap/groups/groups`` directory. The name of the python file defines the group's name.
Each group's python file defines three variables: 

- ``playbook``: A string, with the name of the path of playbook to be executed (the path can be relative to ``~/.clap/groups/`` directory)
- ``actions``: A list of string, defining each group's action name.
- ``hosts``: Optionally, a list of strings defining the hosts used in Ansible Playbooks can be defined. Hosts is used for Ansible to segment the execution of the playbook to specific nodes. If no hosts is defined, the Ansible Playbook must use ``hosts: all``, to perform the operation at all nodes belonging to the group.

An example of a group called ``example-1``, placed at ``~/.clap/groups/groups/example-1.py`` is shown below. The ``~/clap/groups/roles/example1.yml`` will be executed and the group has three actions: ``setup``, ``start`` and ``terminate``.


.. code-block:: python

    # example-1 group
    playbook = 'roles/example1.yml'
    actions = ['setup', 'start', 'terminate']
    
    # Optionally, playbook can specify hosts e.g. master and slaves
    # hosts = ['master', 'slaves']

.. note::

    - The ``setup`` action is **always** called when a node is added to a group.
    - The Ansible Playbook may perform the desired action by inspecting the ``action`` variable.

.. warning::

    The ``setup`` action is **always** required. So a minimal group's description file must contains the variable: ``actions = ['setup']``.


Command ``group list``
+++++++++++++++++++++++++++

The ``clapp group list`` command can be used to list all available groups and their respective actions and hosts. An example of output is shown below, for a group called ``spits``, which has actions ``add-nodes``, ``job-copy``, ``job-create``, ``setup`` and ``start``. Besides that, the nodes from this group can be segmented in ``jobmanager`` and ``taskmanager`` hosts.

.. code-block:: none

    * spits (roles/spits.yml)
        actions: add-nodes, job-copy, job-create, job-status, setup, start
        hosts: jobmanager, taskmanager
    Listed 1 groups


Command ``group add``
+++++++++++++++++++++++++++

The ``clapp group add`` command can be used to execute add a node to a group. The sintax is shown below:

.. code-block:: none

    clapp group add [-h] [--tag TAG] [--extra ...] group [node_ids [node_ids ...]]


One or more node ids can be supplied to the command in order to add all of them to the group. Optionally you can filter nodes to add to the group based in their tags. Some group's actions may require some additional variables to be passed to the playbook (similar to Ansible's extra parameter). Additional keyword variables can be passed via ``extra`` parameter.

For instance, the command below, adds nodes ``node-0`` and ``node-1`` to group ``example`` and pass the variables ``x`` and ``a``, with values ``y`` and ``1``, respectively, to the ``example`` group's ``setup`` action.

.. code-block:: none

    clapp group add example node-0 node-1 --extra "x=y" "a=1"


.. note::

    * When a node is added to a group, the group's setup action is automatically executed.
    * The ``extra`` parameter **must be the last** parameter.


When a group specify hosts, you can add nodes to a group being a defined host using the ``/`` succeeded the group's name. For instance the command below adds the node ``node-0`` to the group ``spits`` being a ``jobmanager`` host.

.. code-block:: none

    clapp group add spits/jobmanager node-0

.. note::

    If a group has defined hosts but you do not specify which host of the group the node is being added, then the node will be added to all available hosts of that group.


Command ``group action``
+++++++++++++++++++++++++++

The ``clapp group action`` command can be used to perform an action in all nodes belonging to the group. The sintax is shown below:

.. code-block:: none

    clapp group action [-h] [--nodes NODES [NODES ...]] [--tag TAG] [--extra ...] group_name action_name

If no nodes is specified, the group's action will be performed in all CLAP's nodes that belongs to the group. You can limit the action to nodes that belongs to the group using the ``nodes`` parameter (which can be supplied with node ids) or ``tag`` parameter (which can be supplied with tags). Some examples is shown below:

.. code-block:: none

    clapp group action spits start
    clapp group action spits/jobmanager start
    clapp group action spits start --nodes node-0 node-4 --tags "x=y" --extra "a=1"

- The first example above performs action ``start``from group ``spits`` in all CLAP's nodes belonging to ``spits`` group.
- The second example above performs action ``start``from group ``spits`` in all CLAP's nodes belonging to ``spits`` group being ``jobmanager`` host.
- The third example above performs action ``start``from group ``spits`` in CLAP's nodes ``node-0``, ``node-4`` and nodes with ``x=y`` tag.


.. note::

    When performing a group action, all nodes must belong to the group that the action will be performed (even when filtering nodes). Thus, the ``group add`` command is always required before performing an action.


Command ``group remove``
+++++++++++++++++++++++++++

The ``clapp group remove`` command removes nodes from a specified group. The sintax is shown below:

.. code-block:: none

    clapp group remove [-h] [--extra ...] group node_ids [node_ids ...]

Similarly to ``group add`` command, you can the node from being a host from a group using the ``/`` succeeded by the group name. Some examples is shown below:

.. code-block:: none

    clapp group remove spits node-0 node-1
    clapp group remove spits/jobmanager node-0

- The first example above, remove ``node-0`` and ``node-1`` from group ``spits``
- The second example above, remove ``node-0`` from being host ``jobmanager`` at the group ``spits``

.. note::
    - If a group has hosts and no host is specified when removing it from the group, the node is removed from being all hosts that it belongs to that group
    - If a group has hosts and the node is removed from all hosts from that group, the node does not belong to the group anymore