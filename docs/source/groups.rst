......................
Groups
......................

In order to perform pre-defined actions in several nodes in a row, CLAP uses the concept of groups, powered by `Ansible playbooks <https://www.ansible.com/>`_. Playbooks can be used to manage configurations of and deployments to remote machines.
Nodes can be added to and removed from a group and also, a node may belong to multiple groups at once.
Once a node belongs to a group, it can be used to execute group actions.

Every group have some actions associated with. For instance, when a node is being added to a group the group's ``setup`` action takes place,
configuring the node to belong to that particular group (e.g. installing desired packages, start services, etc). Basically a group defines a set of actions that can be performed to nodes that belongs to it.
When a node is successfully added to a group we are saying that all operations defined by this group can be performed by that node.

We now explain better the group concept and the commands used to it.
The :doc:`shared groups section <shared_groups>` describes the groups distributed with the CLAP and the :doc:`tutorials section <tutorials>` describes how to implement a new group and other tips.

====================================
Working with groups
====================================

By default CLAP groups are stored in the ``~/.clap/groups/`` directory. An example directory tree, starting from ``~/.clap/groups/`` directory is shown bellow:

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
            |   ├── meta/
            |   |   └── main.yml
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
    2. The ``actions`` (list of strings variable) that can be performed at nodes of this group (for a minimal group, at least the ``setup`` action must be defined).
       Then, the ``roles/group1.yml`` may select the desired tasks to execute based on the ``action`` parameter received.

       Shortly, we will explain the group action commands to become clearer.

    In this way, you can define as much groups as you want, just creating a new python file in the ``groups/groups/`` directory.
    The name of the file will be the group name and the file must contains the ``playbook`` variable (string) and the ``actions`` variable (list of strings).

* The ``groups/group_vars`` directory holds common variables for all groups (usually is not need to edit this file)

* The ``groups/roles`` define the Ansible roles, used by groups.
    * The ``*.yml`` files inside this directory
    * The directory...

===============================
Group Commands
===============================

A

===============================
Group Hosts
===============================

B

===============================
The ubuntu-common example group
===============================

C

===============================
Special variables
===============================

* X
* Y
* Z

Actions can be defined as you wish. The keys of the actions dictionary (`setup`, `copy-files` and `action-x` in the above example) are the action names and the list of string values are the playbooks that must be executed in nodes when this group action is called.

### Adding nodes to a group and performing actions

To perform group actions you must first add the nodes to the desired group. To list the available groups, use the command:
> clap -v group list

The name of the groups are the name of the directories in the `~/.clap/groups` with the `__init__.py` file inside.

To add a node to a group use the command bellow:
> clap -v group add group_name node-0 node-1 node-2 ...

Where the `group_name` in the above command is the name of the group to add the nodes (as shown in the `group list` command) and the `node-0, node-1 and node-2` are the nodes to be added to de group (a list of nodes can be passed to the command). By default, when you add a node to a group, the defined `setup` action defined in the group `__init__.py` file is executed. If no `setup` action is defined, the node is normally added to group. If anything fails on the execution, the node is not added to the group.
You can see which group belongs each node using the `node list` command. Each node can have multiple groups as desired.

After a node is added to a group, you can perform actions (defined in the group's `__init__.py` file) using the command:
> clapp -v group action group_name action_name

Where the `group_name` parameter is the name of the group and the `action_name` parameter is the name of the action defined in the group's `__init__.py` file. Note that the command execute the action in all nodes that belongs the the specified group. You can filter the nodes to execute the action using the `--nodes` parameter in the command.

Finally, you can remove a node from a group using the command:
> clapp -v group remove group_name node-0

Where the `group_name` parameter is the name of the group and `node-0` is the node to be removed from the group. By default, when a node is removed from a group the `stop` action is executed. If the `stop` action is not defined, the group is simply removed from the node.


### Keyword arguments to actions

To allow more flexibility in the playbooks, CLAP allows to pass keyword arguments to the playbook (action) using the `--extra` parameter. Suppose the following hello world playbook bellow, that is executed when the `hello` action of the group `example` is performed.
>
    - hosts: all
      tasks:
      - name: Print hello world in nodes!
        shell: echo "Hello world {{ name }}"

    - import_playbook: ../finish.yml

This playbook simple executes a shell command in the nodes of the group printing a hello world message. Note that the `{{ name }}` between double angle-brackets in the playbook is a variable (called name) of the playbook that must be filled when executing the command (See [Ansible Jinja2 Templating](https://docs.ansible.com/ansible-container/container_yml/template.html) for more information about templating a playbook).

To run the group action command correctly, you will need to use the `--extra` parameter, to set vaiables used in the playbook, as bellow:
> clapp -v group action example hello node-0 --extra name='ola'

Where the keyword extra parameters will fill the playbook variables. If your playbook have more than one variable, you simple continue extra list.

If no extra variable is passed, a similar error message as bellow will appear:
> The task includes an option with an undefined variable. The error was: 'name' is undefined.

And the playbook will fail to execute.

---
**NOTE**

* Ansible Playbooks use spaces not tabs!

* Ansible Jinja Variables (with angle brackets) usually must be inside quotes (e.g `"{{ name }}"`)

* **For now** the `- import_playbook: ../finish.yml` line must appear in the end of every group playbook used.
If you are running a playbook without group command, add the content of `~/.clap/groups/finish.yml` to your playbook.

* Extra parameter **must be the last parameter** in the command!

* **For now** the `hosts: all` in the playbook is needed for CLAP execution.

* You may want to use the `-v` parameter to CLAP in order to see the Ansible echo output (from `stdout`).

---


### The `ubuntu-common` group example

The `ubuntu-common` in the `~/.clap/groups/` directory is a useful group to keep a traditional ubuntu system updated. When a node is added to the group the setup action takes place (executing the playbook `update_sys.yml`) and update the packages on the system and install some python packages.

Nodes belonging to this group can perform the following actions:
* `reboot`: this action reboots the system and wait until the SSH is performed (max 600 seconds)
* `copy`: This action copies a file from local host to the remote hosts. This action requires the following extra parameters:
    * `src`: Source file or directory to copy to the remote host
    * `dest`: Destination in the remote host
* `fetch`: This action copies a file from the remote hosts to the local host. This action requires the following extra parameters:
    * `src`: Source file or directory to copy from the remote hosts
    * `dest`: Destination in the local host (for multiple hosts, different sub-directories will be generated)
* `script`: Transfer the script to remote host and run it with arguments. This action requires the following extra parameters:
    * `src`: Path to the script to be executed
    * `args`: Arguments for the script
* `command`: Execute a shell command in the remote hosts. This action requires the following extra parameters:
    * `cmd`: Full command string (with arguments) to be executed in the remote host.

Some examples using the `ubuntu-common` group follows:
* Adding a node to the `ubuntu-common` group
> clapp -v group add ubuntu-common node-0

* Executing a script in the nodes belonging to the group with three arguments
> clapp -v group action ubuntu-common script --extra src='my_script.sh' args='argument1 arg2 a3'

* Executing a shell command in the nodes belonging to the group with arguments
> clapp -v group action ubuntu-common command --extra cmd='uname -a'

* Copying a file from local (\_\_init\_\_.py) to the nodes belonging to the group (in `~` directory)
> clapp -v group action ubuntu-common copy --extra src='\~\/.clap/groups/ubuntu-common/\_\_init\_\_.py' dest='~'

### Other Groups

Finally, to create a new group, simple copy/paste the `ubuntu-common` example and rename-it (with no spaces). The `run-script.yml` can be modified to run your scripts, for instance (note that for ansible script module, files must come with the `#!/bin/sh` in the initial line).
Also, you may wish to put all of your files needed for the group inside the group directory.
