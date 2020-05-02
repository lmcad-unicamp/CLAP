.. _usage:

=============
Basic Usage
=============

CLAP is a platform to start, stop and manage cloud's instances (called CLAP nodes or simply ,nodes) at different cloud providers transparently, based on configuration files. Also, it offers mechanisms to perform actions via SSH commands or Ansible playboks in single nodes or in a set of nodes in a row.
To provide this, in a modular way, CLAP provides modules to allow performing several operations (see <ARCH> section for more information about the CLAP architecture). You can use ``clapp --help`` command to list the available modules or ``clapp -v --show-all`` to show all available commands that can be used. 

The most common modules are: ``node``, ``tags`` and ``groups``, described in next sections.

.. One of the most common modules is the ``node`` module which can be used to perform operations with single or multiple instances in a row. The commands of this module is detailed in the next section. Other modules such as ``cluster``, can be used to manage entire clusters (see section <CLUSTER> for more details).

.. _nodes section:

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



.. _group section:

Group Module 
-------------------





.. Executing and Connecting
.. ++++++++++++++++++++++++++

.. CLAP provides three simple commands to interact directly with the nodes.

.. * The ``node connect`` command can be used to get an SSH shell to the desired node, as shown in the command below:

.. .. code-block:: none

..     clapp node connect node-1

.. The ``node execute`` command can be used to execute an shell script command in a node and print the respective ``stdout`` and ``stderr`` outputs.
.. An example is shown below, used to execute the command ``echo ola`` in the node ``node-0`` and retrieve its outputs.

.. .. code-block:: none

..     clapp node execute node-0 'echo ola'

.. The ``node playbook`` command allows to execute an `Ansible playbook <https://www.ansible.com/>`_ in several nodes in a row.
.. An example is shown below, used to execute the playbook ``example.yml`` in three nodes (``node-0``, ``node-1`` and ``node-2``)

.. .. code-block:: none

..     clapp node playbook example.yml node-0 node-1 node-2

.. And if your playbook contains variables that must be passed from the command line, you can use the ``extra`` parameter.
.. The below example shows how to pass a keyworded value to a variable in the playbook.

..   .. code-block:: none

..     clapp node playbook example.yml node-0 node-1 node-2 --extra variable1="any value" variable2="another value"

.. Where the ``variable1`` and ``variable2`` are passed to the playbook in your execution.


.. .. note::

..   * The ``extra`` parameter must be the last one in the ``node playbook`` command
..   * You may want to set a higher verbosity level to see Ansible outputs (not just errors). For that, use the ``-v`` parameter, just after ``clapp`` command.


.. .. tag section:

.. Tagging Nodes
.. ----------------

.. Tags is a (key, value) pair that can be associated to nodes aiming to easily select it when needed.
.. Almost every command that you must supply nodes as input may have options to select nodes by tag (will be shown later).

.. You can use the command below to added a tag to some nodes:

.. .. code-block:: none

..     clapp tag add "key=value" node-0 node-1

.. Where the tag must be a string in the format (``"key=value"``) and the nodes must be specified after.

.. To remove tags, you can use the ``tag remove`` command, similarly to the ``tag add`` command, as shown below:

.. .. code-block:: none

..     clapp tag remove "key=value" node-0 node-1

.. Where the tag must be a string in the format (``"key=value"``).

.. Finally, you can also start nodes and tag them right after its creation, by using the below command:

.. .. code-block:: none

..     clapp -v node start ubuntu-instance-aws:4 --tag "key=value"
    
.. The above command instantiates 4 ``ubuntu-instance-aws`` machines and tags them with tag ``"key=value"``, after its creation.

