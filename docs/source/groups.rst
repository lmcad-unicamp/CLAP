......................
Groups
......................

In order to perform pre-defined actions in several nodes in a row, CLAP uses the concept of groups, powered by `Ansible playbooks <https://www.ansible.com/>`_. Playbooks can be used to manage configurations of and deployments to remote machines.
Nodes can be added to and removed from a group and also, a node may belong to multiple groups at once.

Every group have some actions associated with it. For instance, when a node is being added to a group the group's ``setup`` action takes place,
configuring the node to belong to that particular group (e.g. installing desired packages, start services, etc). Basically a group defines a set of actions that can be performed to nodes that belongs to it.
When a node is successfully added to a group we are saying that all operations defined by this group can be performed by that node.

We now explain better the group concept and the commands used to it.
The :doc:`shared groups section <shared_groups>` describes the groups distributed with the CLAP and the :doc:`tutorials section <tutorials>` describes how to implement a new group and other tips.

====================================
Working Groups in CLAP
====================================

By default CLAP groups are stored in the ``~/.clap/groups/`` directory. An example directory tree, starting from ``~/.clap/groups/`` directory is shown below:

::

    groups/
        ├── main.yml
        ├── groups/
        |   ├── group1.py
        |   └── group2.py
        ├── group_vars/
        │   └── all.yml
        └── roles/
            ├── group1.yml
            ├── group2.yml
            ├── group-role-1/
            |   └── tasks/
            |       └── main.yml
            └── group-role-2/
                └── tasks/
                    └── main.yml


The groups directory tree format follow the `Ansible directory layout <https://docs.ansible.com/ansible/latest/user_guide/playbooks_best_practices.html#directory-layout>`_ for content organization.

* The ``groups/main.yml`` is the default entry point for all group playbooks (it should not be edited)

* The ``groups/groups/`` directory contain files specifying the group and which action the nodes of the group can perform.
  In general, this directory contains python files, where every python file determines a group (the name of the python file is the group name).

  Let's look at an example group file at ``groups/groups/group1.py`` (where the group is called ``group1``)

.. code-block:: python

    playbook = 'roles/group1.yml'
    actions = ['setup', 'start', 'terminate']

This file defines:
    1. The ``playbook`` (string variable) to be executed when a group command is invoked
    2. The ``actions`` (list of strings variable) that can be performed at nodes of this group.
       For this example the ``setup``, ``start`` and ``terminate`` actions can be performed in the nodes belonging to the ``group1`` (for a minimal group, at least the ``setup`` action must be defined).

    3. Then, the ``roles/group1.yml`` may select the desired tasks to execute based on the ``action`` parameter received.
       Shortly, we will explain the group action commands to become clearer.

       In this way, you can define as much groups as you want, just creating a new python file in the ``groups/groups/`` directory.
       The name of the file will be the group name and the file must contains the ``playbook`` variable (string) and the ``actions`` variable (list of strings).
       **NOTE**: The ``setup`` action is mandatory

* The ``groups/group_vars`` directory holds common variables for all groups (usually you do not need to edit this file)

* The ``groups/roles`` define the Ansible roles, used by groups.
    1. The ``*.yml`` files inside this directory are the playbooks executed by a group (specified in the group's python file).
       This playbook include roles conditionally based on the ``action`` parameter
    2. The directories inside ``groups/roles`` directory are `Ansible Roles <https://docs.ansible.com/ansible/latest/user_guide/playbooks_reuse_roles.html>`_.
       Roles are ways of automatically loading desired variables based on a known file structure.
       Inside of every role directory, a exists a ``tasks`` directory.
       The ``main.yml`` inside the tasks directory defines the tasks to be executed when the role in included.

       For more information about roles see `Ansible Roles <https://docs.ansible.com/ansible/latest/user_guide/playbooks_reuse_roles.html>`_.
       See the :doc:`tutorials section <tutorials>` to better understanding how to create a group ans use roles.

===============================
Group Commands
===============================

You can see the available groups and their actions with the command below:

::

    clapp group list

And the example output would be:

::

    * docker-ce (roles/docker-ce.yml)
      actions: setup, start-container, stop-container

    * ec2-efs (roles/ec2-efs.yml)
      actions: mount, setup, umount

    Listed 2 groups

As shown, we have the ``ec2-efs`` and ``docker-ce`` groups, each one with their actions associated.


Once nodes are up and started you can perform actions in several nodes by using groups.
So, you first must to add the desired nodes to a group which can be accomplished by using the command below:

::

    clapp group add example_group node-0 node-1 ...

This command will add the nodes ``node-0`` and ``node-1`` to the group called ``example_group``. Note that you can add more nodes to the group, just appending more node ids in the list.
When a node is added to a group, the group's ``setup`` action takes place configuring (e.g. installing packages, starting services) the nodes to belong to that particular group.
If the ``setup`` action fails, the node are not added to the group.

  You can see which group belongs each node using the ``clapp node list`` command. Each node can have belong to several groups as desired.

After a node is added to a group, you can perform group actions using the command below:

::

    clapp group action example_group example_action

Where the ``example_group`` is the group and ``example_action`` is the action to be performed for that group.
In this way, the ``example_action`` is executed in **all** nodes belonging to the ``example_group`` group.

You can also filter a subset of nodes from the group to execute the action by using ``--nodes`` parameter to the group action command as below:

::

    clapp group action example_group example_action --nodes node-0 node-1 ...

For this example, the ``example_action`` action is just performed in the nodes ``node-0`` and ``node-1``.

  **NOTE**: When filtering nodes with ``--nodes`` parameter, all nodes must belong to the desired group, else the action will fail.

Sometimes, group actions may require some variables to be passed from the command-line.
You can use the ``extra`` parameter to pass keyworded values to the group, as the command below (also works for ``group add`` and ``group remove`` commands):

::

    clapp group action example_group example_action --nodes node-0 node-1 --extra variable1="value1" var2="another value"

The above command pass the ``variable1``and ``var2`` to the group action.

  **NOTE**: The ``extra`` parameter must be the last in the command

If a required vaiable is not passed the following error will appear (and action will fail):

::

    The task includes an option with an undefined variable. The error was: 'variable' is undefined.


And finally, you can remove a node from a group by using the ``group remove`` command as below:

::

    clapp group remove example_group node-0 node-1

Where in the above command, the nodes ``node-0`` and ``node-1`` will be removed from group ``example_group``.
Usually the remove action may stop services, uninstall packages or copy valuable data from the host.

Some groups distributed with CLAP and their requirements can be found in the :doc:`groups shared with CLAP section <shared_groups>`.

  **NOTE**: You may want to use the ``-v`` (verbose) parameter for clap to show all Ansible messages (not only error messages)

===============================
Group Hosts
===============================

Group may also have hosts to orchestrate the group action in different nodes.
Hosts are subsets of nodes of a group and can be used to split the action to the different subsets of nodes.

Suppose you have a group called ``example`` which provide means to execute a program that operates in a master/slave nodes fashion.
For the traditional operation, we instantiate the nodes and them adds them to the ``example`` group using the ``group add`` command.
How can we say each node of the group is the master and which nodes are the slaves?
You can use tags for that, but Ansible provides hosts, that bypass this problem.

Let's look to an example group python file at ``groups/groups/example.py``:

.. code-block:: python

    playbook = 'roles/example.yml'
    actions = ['setup', 'start', 'terminate']
    hosts = ['master', 'slave']

The hosts variable is optional. For the example we have two hosts for group example: ``master`` and ``slave``.
So the nodes belonging to the group example can be master or slave or both.

When hosts for a group is defined, the node must be added to the group and the host type must be speficied on the ``group add`` command as below:

::

    clapp group add example/master node-0 node-1

The above command adds the ``node-0`` and ``node-1`` to the group ``example`` being ``master`` hosts.
The backslash (/) character denotes the host of a group. The node can also be added to a group being a slave, using:

::

    clapp group add example/slave node-0 node-1

The above command adds the ``node-0`` and ``node-1`` to the group ``example`` being ``slave`` hosts.

This format (group and hosts) CLAP can optimize Ansible execution. Playbooks can use the ``hosts`` keyword to perform a specific action to a group of nodes.
Anyway if no ``hosts`` is specified in the playbook, the playbook will execute in all nodes belonging to the group.

  **NOTE**:
    * Hosts are optional
    * If the group has hosts defined and in the add command no specific host is passed, this is, only the group name, the node is added to group and for all hosts that the group has defined.
      So in the above example if the command below is executed

    ::

         clapp group add example node-0 node-1

    nodes ``node-0`` and ``node-1`` will be added to hosts ``master`` and ``slaves`` of group ``example``

The ``group list`` command also list hosts when available to the group. See the example below (an output for ``group list`` command):

::

    * docker-ce (roles/docker-ce.yml)
      actions: setup, start-container, stop-container

    * ec2-efs (roles/ec2-efs.yml)
      actions: mount, setup, umount

    * example (roles/example.yml)
      actions: setup, start-masters, start-slaves, terminate-all
      hosts: master, slave

    Listed 3 groups

In the above example, the group ``example`` has hosts ``master`` and ``slave`` so nodes can belong to ``example/master`` or ``example/slave`` (or both).
Some actions in the ``example`` group may execute in all hosts of the group (for instance ``setup`` and ``terminate-all``) and others may execute only in some hosts.
This is defined in the group implementation.

Let's suppose the ``start-masters`` action for example group execute only in master hosts of the group, this is, inside the ``example.yml`` playbook the keyword ``hosts: master`` is defined for action ``start-masters``.
You just need to run the action command

::

    clapp group action example start-masters

And the ``start-master`` action will only execute in nodes of the group ``example`` that is ``master`` hosts.

More information about hosts can be found in the :doc:`tutorials section <tutorials>`.

===============================
Special variables
===============================

For all Ansible playbooks the following variables can be used:

* **inventory_name**
* **ansible_host**
* XXX
