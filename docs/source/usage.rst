==========================
Usage
==========================

CLAP is a platform to start, stop and manage instances (nodes) in different cloud providers transparently.
CLAP also offer mechanisms to control what is installed in each node and to perform actions in a group of nodes in a row.

This section describes the common use commands to start, stop and manage instances.

To use clap, first activate the virtual environment running the following command (inside CLAP directory):

::

    source clap-env/bin/activate

CLAP has several commands, you can use

::

    clapp -v --show-all

command to get information about all available commands.
Alternatively you can use ``--help`` in each command to see the features.
The ``-v`` parameter can always be used, increasing he verbosity level of CLAP. ``-vv`` allows showing DEBUG messages.


-------------------------
List available instances
-------------------------

To list the nodes managed by CLAP, you can use the command:

::

    clapp node list

If there is any node already instantiated, an example output is shown below:

::

    *  Node(id=`node-1`, instance_type=`type-a`, status=`reachable`, provider_id: `aws-config-us-east-1`, connection_ip=`54.89.209.193`, groups=`spits/jobmanager`, tags=`spits=cluster-spits`)
    *  Node(id=`node-2`, instance_type=`type-a`, status=`reachable`, provider_id: `aws-config-us-east-1`, connection_ip=`54.157.8.46`, groups=`spits/taskmanager`, tags=`spits=cluster-spits`)
    Listed 2 nodes(s)

For several commands, CLAP uses the node id (e.g. ``node-1``, ``node-2``) to perform operation in the nodes, transparently.
Nodes may have tags (discussed lately) to easily perform selections and mey belong to groups, to perform group actions (discussed later).

You may want to see the :doc:`troubleshooting page <troubleshooting>` if any failure occurs when working with nodes.

------------------------------------
Start Instances and Check Aliveness
------------------------------------

To instantiate one node based on an instance template defined in the ``~/.clap/configs/instances.yaml`` file, you can use the command:

::

    clapp -v node start ubuntu-instance-aws


Where the ``ubuntu-instance-aws`` refers to the instance template ID defined in the ``~/.clap/configs/instances.yaml`` file.
In this way, you need to configure the files only once and launch instances any time.

To launch more than one machine with the same instance template ID, you can put the desired number after the instance template ID preceded by an ``:``. For instance, the command below:

::

    clapp -v node start ubuntu-instance-aws:4

Instantiates 4 ``ubuntu-instance-aws`` virtual machines in a row!
Once the instance is started, CLAP will try to login (via SSH) with the login information provided.
The machine is considered instantiated when the SSH connection is performed successfully. Machines instantiated that cannot perform SSH in a timeout (600 seconds) are automatically **stopped**.

You can also instantiate different machines in a row using the same command, but just appending more instance template IDs to it:

::

    clapp -v node start ubuntu-instance-aws:2 example-instance-aws:2

The above command instantiates 2 ``ubuntu-instance-aws`` machines and 2 ``example-instance-aws`` machines in a row!

Once instances are successfully started, CLAP will assign to each one an unique node ID used to perform other operations to it.
The ``clapp node list`` command can be used to show managed clap instances and a more detailed information of a specific node can be obtained with the command below:

::

    clapp node show node-1

Replacing ``node-1`` with the id of the node to be detailed.

**NOTE**

* If the message below appears, don't worry, just ignore it.

::

    [ERROR] Thread-XXX: Apparently, Amazon does not compute the RSA key fingerprint as we do! We cannot check if the uploaded keypair is correct!


After the node is started, you can check if it is alive using the command below:

::

    clapp node alive node-1 ...

Where ``node-0`` must be replaced with the node ID of interest. Also, more nodes can be checked, simple appending their node IDs to the command.

The ``node alive`` command also updates the node connection IP and can be very useful when the node IP changes (e.g. instance stopped comes alive, or when using floating ips)
Its recommended to run the command periodically to update nodes information.


----------------------
Terminating Instances
----------------------

The ``stop`` command can be used to **terminate** an running instance (in AWS, stop/resume instance is **not supported yet**, so the nodes are terminated).
The command is shown below

::

    clapp -v node stop node-1 ...

Where ``node-0`` must be replaced with the node ID of interest. Also, more nodes can be stopped, simple appending their node IDs to the command.

If an instance is stopped (not terminated) in the AWS EC2 console, it must be resumed from there.
After an instance is resumed it is prudent to run the ``node alive`` command to update instance information.

-------------------------------
Executing and Connecting
-------------------------------

CLAP provides three simple commands to interact directly with the nodes.

* The ``node connect`` command can be used to get an SSH shell to the desired node, as shown in the command below:

::

        clapp node connect node-1

* The ``node execute`` command can be used to execute an shell script command in a node and print the respective ``stdout`` and ``stderr`` outputs.
  An example is shown below, used to execute the command ``echo ola`` in the node ``node-0`` and retrieve its outputs.

::

        clapp node execute node-0 'echo ola'

* The ``node playbook`` command allows to execute an `Ansible playbook <https://www.ansible.com/>`_ in several nodes in a row.
  An example is shown below, used to execute the playbook ``example.yml`` in three nodes (``node-0``, ``node-1`` and ``node-2``)

  ::

        clapp node playbook example.yml node-0 node-1 node-2

  And if your playbook contains variables that must be passed from the command line, you can use the ``extra`` parameter.
  The below example shows how to pass a keyworded value to a variable in the playbook.

  ::

        clapp node playbook example.yml node-0 node-1 node-2 --extra variable1="any value" variable2="another value"

  Where the ``variable1`` and ``variable2`` are passed to the playbook in your execution.

  **NOTE**

  * The ``extra`` parameter must be the last one in the ``node playbook`` command
  * You may want to set a higher verbosity level to see Ansible outputs (not just errors). For that, use the ``-v`` parameter, just after ``clapp`` command.


-------------------------------
Tagging Nodes
-------------------------------

Tags is a (key, value) pair that can be associated to nodes aiming to easily select it when needed.
Almost every command that you must supply nodes as input may have options to select nodes by tag (will be shown later).

You can use the command below to added a tag to some nodes:

::

    clapp tag add "key=value" node-0 node-1

Where the tag must be a string in the format (``"key=value"``) and the nodes must be specified after.

To remove tags, you can use the ``tag remove`` command, similarly to the ``tag add`` command, as shown below:

::

    clapp tag remove "key=value" node-0 node-1

Where the tag must be a string in the format (``"key=value"``).

Finally, you can also start nodes and tag them right after its creation, by using the below command:

::

    clapp -v node start ubuntu-instance-aws:4 --tag "key=value"
    
The above command instantiates 4 ``ubuntu-instance-aws`` machines and tags them with tag ``"key=value"``, after its creation.

