.. _usage:

=============
Basic Usage
=============

CLAP is a platform to start, stop and manage cloud's instances (called CLAP nodes
or simply, nodes) at different cloud providers transparently, based on configuration
files. Also, it offers mechanisms to perform actions via SSH commands or Ansible
playbooks in single nodes or in a set of nodes in a row. To provide this, in a modular
way, CLAP provides modules to allow performing several operations.
You can use ``clapp --help`` command to list the available modules.

The most common modules are: ``node``, ``role`` and ``cluster``.

.. _node section:

Node Module
---------------------

The node module provides mechanisms to create, manage and interact with cloud's
instances. It provides the following features:

* Start nodes based on the instance templates with the ``start`` command.
* Stop (terminate) already started nodes using the ``stop`` command.
* Pause or resume already instantiated nodes using the ``pause`` and ``resume`` commands, respectively.
* Check the status of a node (if its accessible by SSH) using the ``alive`` command.
* List started nodes using the ``list`` command.
* Execute a shell command via SSH, using the ``execute`` command.
* Execute an Ansible Playbook using the ``playbook`` command.
* Obtain a shell session (via SSH) using the ``connect`` command.
* Add and remove tags from nodes using ``add-tag`` and ``remove-tag`` commands.
* List all available instance templates configurations using the ``list-templates`` command.

All these commands are detailed below.


Command ``node start``
+++++++++++++++++++++++++++

To launch a cloud's instance based on an instance template, defined in the
``~/.clap/configs/instances.yaml`` file, you can use the command below, where the
``ubuntu-instance-aws`` refers to the instance template ID defined in the
``~/.clap/configs/instances.yaml`` file. In this way, you need to configure the
files only once and launch instances at any time.

::

    clapp node start ubuntu-instance-aws

Once instances are successfully started, CLAP will assign an unique node ID to each
instance, used to perform other CLAP operation. Also, CLAP will try to login at
the instance with the login information provided, via SSH.

To launch more than one instance with the same instance template ID, you can
put the desired number after the instance template ID preceded by an ``:`` character.
For instance, the command below, launches 4 ``ubuntu-instance-aws`` instances in a row.

::

    clapp node start ubuntu-instance-aws:4


You can also launch different instances in a row using the same command, but just
appending more instance template IDs to it, as below. The above command launches
2 ``ubuntu-instance-aws`` VMs and 2 ``example-instance-aws`` VMs in a row.

::

    clapp node start ubuntu-instance-aws:2 example-instance-aws:2


Command ``node list``
+++++++++++++++++++++++++++

The ``clapp node list`` command can be used to show managed CLAP's nodes.
An example output of this command is shown below.

::

    * Node: ebcd658bacdf485487543cbcc721d1b3, config: type-a, nickname: MarjoryLang, status: reachable, ip: 3.87.87.154, tags: {}, roles: [], creation at: 21-05-21 14:11:55
    Listed 1 nodes


The node id (``ebcd658bacdf485487543cbcc721d1b3`` in the above example) is used
across all other modules and commands to perform commands in this node.


Command ``node alive``
+++++++++++++++++++++++++++

This command updates several node's information (such as IP) and check if the
node is reachable (if a SSH connection can be established).

The node's status can be:

* **started**: when the VM is up.
* **reachable**: when the VM is up and a SSH connection was successfully established.
* **unreachable**: when the SHH connection was not successfully established.
* **paused**: when VM is paused.
* **stopped**: when VM is terminated.

.. note::

    CLAP does not check the status of VM periodically. Use this command to update node status and information.



Command ``node stop``
+++++++++++++++++++++++++++

The ``clapp node stop`` command can be used to **terminate** an running VM (destroying it). The syntax is shown below:


Command ``node pause``
+++++++++++++++++++++++++++

The ``clapp node pause`` command can be used to **pause** an running instance.
When a node is paused, its status is changed to **paused** and its public IP is
changed to ``None``.

.. note::

    The command has no effect for nodes that already been paused.


Command ``node resume``
+++++++++++++++++++++++++++

The ``clapp node resume`` command can be used to **resume** a paused instance.
When a node is resumed, it status is changed to **started**. Then, it checked if
it is alive, testing its connection and updating its public IP (and changing its
status to **reachable**).

.. note::

    The command has no effect at nodes that were not paused. It will only check for its aliveness.


Command ``node connect``
+++++++++++++++++++++++++++

The ``clapp node connect`` command can be used to obtain a shell to a specific
node.

.. note::

    The connection may fail if node has an invalid public IP or a invalid login information. You may want to check if node is alive first to update node's information.


Command ``node execute``
+++++++++++++++++++++++++++

The ``clapp node execute`` command can be used to execute a shell command on an
reachable node. The syntax is shown below:

::

    Usage: clapp node execute [OPTIONS] [NODE_ID]...

      Execute a shell command in nodes (via SSH)

    Options:
      -t, --tags TEXT        Filter nodes by tags. There are two formats: <key> or
                             <key>=<val>
      -cmd, --command TEXT   Shell Command to be executed in nodes  [required]
      --timeout INTEGER      Timeout to execute command in host (0 to no timeout)
                             [default: 0]
      -a, --additional TEXT  Additional arguments to connection. Format:
                             <key>=<val>
      --help                 Show this message and exit.

One or more nodes can be passed as argument, or can be selected based on their tags.
The ``--command`` parameter specify the command that will be executed in nodes.

An example is shown below, executing a simple ``ls -lha`` command in the node
``ebcd658bacdf485487543cbcc721d1b3``

::

    clapp node execute ebcd658bacdf485487543cbcc721d1b3 -cmd "ls -lha"

And the result:

::

    ------------------------ ebcd658bacdf485487543cbcc721d1b3 ------------------------
    return code ebcd658b: 0
    stdout ebcd658b: drwxr-xr-x 5 ubuntu ubuntu 4.0K May 21 17:12 .
    stdout ebcd658b: drwxr-xr-x 3 root   root   4.0K May 21 17:12 ..
    stdout ebcd658b: -rw-r--r-- 1 ubuntu ubuntu  220 Apr  4  2018 .bash_logout
    stdout ebcd658b: -rw-r--r-- 1 ubuntu ubuntu 3.7K Apr  4  2018 .bashrc
    stdout ebcd658b: drwx------ 2 ubuntu ubuntu 4.0K May 21 17:12 .cache
    stdout ebcd658b: drwx------ 3 ubuntu ubuntu 4.0K May 21 17:12 .gnupg
    stdout ebcd658b: -rw-r--r-- 1 ubuntu ubuntu  807 Apr  4  2018 .profile
    stdout ebcd658b: drwx------ 2 ubuntu ubuntu 4.0K May 21 17:12 .ssh


.. note::

    You may want to check for nodes aliveness first.


Command ``node playbook``
+++++++++++++++++++++++++++

The ``clapp node playbook`` command can be used to execute an Ansible playbook
in a set of reachable nodes. The syntax is shown below:

::

    clapp node playbook [OPTIONS] [NODE_ID]...

        Execute an Ansible playbook in a set of nodes.

        The NODE_ID argument is a list of strings (optional) and can filter nodes to
        execute the playbook by their node ids

    Options:
        -p, --playbook TEXT    Path of the playbook to be executed  [required]
        -t, --tags TEXT        Filter nodes by tags. There are two formats: <key> or
                             <key>=<val>
        -e, --extra TEXT       Extra variables to be passed. Format: <key>=<val>
        -nv, --node-vars TEXT  Host variables to be passed. Format:
                             <node_id>:<key>=<val>,<key>=<val>,...
        --help                 Show this message and exit.


One or more nodes can be passed as argument, or can be selected based on their tags.

The ``--playbook`` parameter specify the playbook to execute in nodes.

The ``--extra`` parameter can be used to pass keyword arguments to the playbook.

The ``--node-vars`` parameter can be used to pass keyword arguments to a specific node
when building the inventory.

An example is shown below. The playbook ``install_packages.yml`` is executed in node
``ebcd658bacdf485487543cbcc721d1b3``.
Extra playbook variables (in jinja format, e.g. "{{ var1 }}") will be replaced by
the extra variables informed. In the example below the playbook's variable
``packages`` will be replaced by ``gcc``.

::

    clapp node playbook ebcd658bacdf485487543cbcc721d1b3 -p install_packages.yml -e "packages=gcc"


.. _tags section:

Command ``node add-tag``
+++++++++++++++++++++++++

This ``clapp node add-tag`` command adds a tag to a set of nodes and has the
following syntax:

::

    Usage: clapp node add-tag [OPTIONS] NODE_ID...

      Add tags to a set of nodes.

      The NODE_ID argument is a list of node_ids to add tags.

    Options:
      -t, --tags TEXT  Tags to add. Format: <key>=<val>  [required]
      --help           Show this message and exit.


One or more nodes can be passed as argument. The ``tags`` parameter must be a
keyword value in the format ``key=value``. You can add as many tags to a node as
you want. An example of adding tags is shown below:

::

    clapp node add-tag ebcd658bacdf485487543cbcc721d1b3 -t x=10

Where tag ``x=10`` is added to nodes ``ebcd658bacdf485487543cbcc721d1b3``.

Command ``node remove-tag``
++++++++++++++++++++++++++++

This ``clapp tag remove`` command removes a tag from a set of nodes and has the
following syntax:

::

    clapp node remove-tag [OPTIONS] NODE_ID...

      Remove tags from a set of nodes.

      The NODE_ID argument is a list of node_ids to remove tags.

    Options:
      -t, --tags TEXT  Tags to remove. Format: <key>  [required]
      --help           Show this message and exit.

One or more nodes can be passed as argument. The ``tag`` parameter must be a string.
The tags from nodes that matches to the informed tag is removed (tag and value).

.. _role section:

Role Module
-------------------

The role module allows to perform pre-defined actions to a set of nodes that
belongs to a role. When a node is added to a role, it is said that this node
is ready to perform tasks of this role.
Thus, each role defines their set of specific actions that can be performed to
nodes that belongs to that particular role.

In this way, the role module consists of three steps:

1. Add nodes to a role.
2. Perform role's action to nodes that belongs to a role.
3. Optionally, remove nodes from the group.

The nodes of a role can also be logically divided in hosts. Thus, role actions
can be performed to all nodes of the role or to a subset of nodes of role (hosts).

CLAP's roles and actions
++++++++++++++++++++++++++++++

Role's actions are `Ansible playbooks <https://www.ansible.com/>`_ that are
executed when an action is invoked (e.g. using ``role action`` command). By
default CLAP's roles are stored in the ``~/.clap/roles/`` directory and each
role consists in at minimum of two files:

* A YAML description file describing the actions that can be performed (and informing the playbook that must be called) and, optionally, the hosts (subset of role's nodes to execute the playbook)
* The Ansible Playbook called when each action is invoked.

You can see some roles shared with CLAP and their requirements at :ref:`shared_roles` section.


Role description file
^^^^^^^^^^^^^^^^^^^^^^^

The role's description files are python files placed at ``~/.clap/groups/actions.d``
directory. The name of the YAML file defines the role's name.
Each role description file defines the key ``actions`` and, optionally, the ``hosts``
key. Inside ``actions`` key, each dictionary defines a role action where the
key name is the action name and the values informs characteristic of that action.

An example role description file is shown below, for a role named ``commands-common``
(placed at ``~/.clap/roles/actions.d/commands-common.yaml``).

.. code-block:: yaml

    ---
    actions:                                                        # Defines the actions of this group
        setup:                                                      # Action called setup
            playbook: roles/commands-common_setup.yml               # Playbook to be executed when this group action is invoked

        copy:                                                       # Action called copy
            playbook: roles/commands-common_copy.yml                # Playbook to be executed when this group action is invoked
            description: Copy files from localhost to remote hosts  # Optional action's description
            vars:                                                   # Optional variables required
            - name: src                                             # src variable
              description: Source files/directory to be copied      # Optional variable's description
              optional: no                                          # Informs if this variable is optional
            - name: dest                                            # dest variable
              description: Destination directory where files will be placed # Optional variable's description
        
        fetch:
            playbook: roles/commands-common_fetch.yml
            description: Fetch files from remote hosts to localhost
            vars:
            - name: src
              description: Source files/directory to be fetched
            - name: dest
              description: Destination directory where files will be placed
        
    hosts:                                                          # (optional) List of hosts that are used in this role. The host name can be used in the playbooks.
    - master
    - slave

.. note::

    Action's playbook is relative to the ``~/.clap/roles/`` directory.

For role's description files, ``actions`` dictionary is required, and ``hosts`` optional.
The keys inside ``actions`` dictionary are the action names and the possible
values for each action are described in table below.

..  list-table:: Valid values for actions
    :header-rows: 1

    *   - **Name**
        - **Type**
        - **Description**

    *   - ``playbook``
        - path
        - Playbook to be executed when this action is invoked. The path is relative to ``~/.clap/roles/`` directory.

    *   - ``description`` (optional)
        - string
        - Action's descriptive information

    *   - ``vars`` (optional)
        - List of variable dictionaries
        - List informing variables needed for this action

And optionally, the actions can define their variables to use. The possible
values are listed table below

..  list-table:: Valid action's values
    :header-rows: 1

    *   - **Name**
        - **Type**
        - **Description**

    *   - ``name``
        - string
        - Name of the variable

    *   - ``description`` (optional)
        - string
        - Variable's descriptive information

    *   - ``optional`` (optional)
        - boolean
        - Inform if variable is optional (default is ``no``)


Finally the hosts specify the ``hosts`` used by role actions. It's optional and
when specified Ansible playbooks can segment their execution using the ``hosts``
variable at each play. If no hosts are specified you must use ``hosts: all``
to perform the action over all nodes that belong to the role.


Command ``role list``
+++++++++++++++++++++++++++

The ``clapp role list`` command can be used to list all available role and their
respective actions and hosts. An example of output is shown below

::

    * name: commands-common
      Has 7 actions and 2 hosts defined
        actions: copy, fetch, install-packages, reboot, run-command, run-script, update-packages
        hosts: h1, h2

    * name: ec2-efs
      Has 3 actions and 0 hosts defined
        actions: mount, setup, unmount
        hosts:

    * name: spits
      Has 6 actions and 2 hosts defined
        actions: add-nodes, job-copy, job-create, job-status, setup, start
        hosts: jobmanager, taskmanager

    Listed 3 roles



Command ``role add``
+++++++++++++++++++++++++++

The ``clapp role add`` command can be used to add a node to a role. The syntax
is shown below:

::

    clapp role add [OPTIONS] ROLE

      Add a set of nodes to a role.

      The ROLE argument specify the role which the nodes will be added.

    Options:
      -n, --node TEXT        Nodes to be added. Can use multiple "-n" commands and
                             it can be a list of colon-separated nodes as
                             "<node>,<node>,..." or
                             "<role_host_name>:<node>,<node>". The formats are
                             mutually exclusive  [required]
      -nv, --node-vars TEXT  Node's arguments. Format
                             <node_id>:<key>=<value>,<key>=<val>
      -hv, --host-vars TEXT  Role's host arguments. Format
                             <host_name>:<key>=<value>,...
      -e, --extra TEXT       Extra arguments. Format <key>=<value>
      --help                 Show this message and exit.


The nodes can be supplied with ``--node`` parameter using two formats (mutually
exclusive): with host or without host.

If the role does not define any host, nodes must be informed supplying only their
node ids in the ``--node`` parameter. Multiple ``--node`` parameters can be used
to indicate multiple nodes ids. Besides that, multiple nodes ids can be passed to
``--node`` parameter by separating them with comma.
The both examples below add nodes ``ebcd658bacdf485487543cbcc721d1b3`` and
``455e9c5da5c4417abc757f587a31c105`` to role ``commands-common``.

::

    clapp role add commands-common -n ebcd658bacdf485487543cbcc721d1b3 -n 455e9c5da5c4417abc757f587a31c105
    clapp role add commands-common -n ebcd658bacdf485487543cbcc721d1b3,455e9c5da5c4417abc757f587a31c105

If the role defines one or more hosts, the ``--node`` parameter can be supplied
with the  "<node>,<node>,..." format (1) or with the "<role_host_name>:<node>,<node>"
format (2) (both are mutually exclusive). If the format (1) is used, the nodes
are added to all role's hosts defined .
Two examples are shown below, one for format (1) and other for format (2).

::

    clapp role add commands-common -n ebcd658bacdf485487543cbcc721d1b3 -n 455e9c5da5c4417abc757f587a31c105
    clapp role add commands-common -n masters:ebcd658bacdf485487543cbcc721d1b3 -n slaves:455e9c5da5c4417abc757f587a31c105

Supposing the role ``commands-common`` defines 2 hosts: ``masters`` and ``slaves``,
the first one adds nodes ``ebcd658bacdf485487543cbcc721d1b3`` and ``ebcd658bacdf485487543cbcc721d1b3``
to both role's host.
The second one adds node ``ebcd658bacdf485487543cbcc721d1b3`` as commands-common
masters and node ``455e9c5da5c4417abc757f587a31c105`` as commands-common slaves host.

The ``--extra`` parameter can be used to pass keyword arguments to the playbook.

The ``--node-vars`` parameter can be used to pass keyword arguments to a specific node
when building the inventory.

The ``--host-vars`` parameter can be used to pass keyword arguments to a hosts.

.. note::

    If the role's setup action is defined this action is immediately executed
    when adding a role to a node. If this action fails, the node is not added to
    the role.


Command ``role action``
+++++++++++++++++++++++++++

The ``clapp role action`` command can be used to perform an action in all nodes
belonging to a particular role. The syntax is shown below:

.. code-block:: none

    clapp role action [OPTIONS] ROLE

      Perform an group action at a set of nodes.

      The ROLE argument specify the role which the action will be performed.

    Options:
      -a, --action TEXT      Name of the group's action to perform  [required]
      -n, --node TEXT        Nodes to perform the action. Can use multiple "-n"
                             commands and it can be a list of colon-separated node
                             as "<node>,<node>,..." or
                             "<role_host_name>:<node>,<node>". The formats are
                             mutually exclusive. If not is passed, the action will
                             be performed in all nodes that belongs to the role.
      -nv, --node-vars TEXT  Node's arguments. Format
                             <node_id>:<key>=<value>,<key>=<val>
      -hv, --host-vars TEXT  Role's host arguments. Format
                             <host_name>:<key>=<value>,...
      -e, --extra TEXT       Extra arguments. Format <key>=<value>
      --help                 Show this message and exit.


The ``--node`` parameter is optional and if is not supplied, the role action will
be executed in all nodes that belongs to the role. If ``--node`` parameter is
supplied it may be in two formats (mutually exclusive): with host or without host.

If nodes are informed in format without host, the selected nodes will be automatically
placed in their correct hosts (if any). Otherwise, the nodes will be placed in
informed hosts.

Examples are shown below:

::

    clapp role action commands-common -a install-packages -n ebcd658bacdf485487543cbcc721d1b3 -e packages=gcc
    clapp role action commands-common -a install-packages -n masters:ebcd658bacdf485487543cbcc721d1b3 -e packages=gcc
    clapp role action commands-common -a install-packages -e packages=gcc


The first command perform ``install-packages`` action, from ``commands-common`` role
in nodes ``ebcd658bacdf485487543cbcc721d1b3``.  The node's hosts are the same when
the nodes added. The second command perform ``install-packages`` action, from
``commands-common`` role in node ``ebcd658bacdf485487543cbcc721d1b3``. The node's hosts
acts only as ``masters``, additional hosts from this node are discarded.
The last command perform ``install-packages`` action, from ``commands-common`` role
at all nodes that belongs to ``commands-common``.
For all commands, the extra variable ``package`` with value ``gcc`` is passed.

The ``--extra`` parameter can be used to pass keyword arguments to the playbook.

The ``--node-vars`` parameter can be used to pass keyword arguments to a specific node
when building the inventory.

The ``--host-vars`` parameter can be used to pass keyword arguments to a hosts.

Command ``role remove``
+++++++++++++++++++++++++++

The ``clapp role action`` command can be used to perform an action in all nodes
belonging to a particular role. The syntax is shown below:

::

    clapp role remove [OPTIONS] ROLE

      Perform an group action at a set of nodes.

      The ROLE argument specify the role which the action will be performed.

    Options:
      -n, --node TEXT  Nodes to perform the action. Can use multiple "-n" commands
                       and it can be a list of colon-separated node as
                       "<node>,<node>,..." or "<role_host_name>:<node>,<node>".
                       The formats are mutually exclusive. If not is passed, the
                       action will be performed in all nodes that belongs to the
                       role.  [required]
      --help           Show this message and exit.

The ``--node`` parameter is used to inform the nodes to remove from a role.
The parameter can be supplied using two formats (mutually exclusive): with host
or without host.
If host is passed, the node is removed from the host's role else the node is removed
from all hosts in the role (if any). An example is shown below:

::

    clapp role remove commands-common -n ebcd658bacdf485487543cbcc721d1b3 -n 455e9c5da5c4417abc757f587a31c105
    clapp role remove commands-common -n masters:ebcd658bacdf485487543cbcc721d1b3 -n slaves:455e9c5da5c4417abc757f587a31c105

The first example remove nodes ``ebcd658bacdf485487543cbcc721d1b3`` and ``455e9c5da5c4417abc757f587a31c105``
from role ``commands-common`` and from all ``commands-common`` role hosts (if any).
The second example removes node ``ebcd658bacdf485487543cbcc721d1b3`` from host
called ``masters`` from ``commands-common`` role and node ``455e9c5da5c4417abc757f587a31c105``
from hosts called ``slaves`` from ``commands-common`` role.


.. _cluster module:

Cluster Module
-------------------

The cluster module allows CLAP to work with cluster, which is a set of CLAP's nodes
tagged with a specific tag. A CLAP's cluster is created taking as input configuration
files, in YAML format, which will create nodes and setup each of them properly.
After created, the cluster can be resized (adding or removing nodes), paused,
resumed, stopped, among other things.

By default, the CLAP's cluster module will find configurations inside
``~/clap/configs/clusters`` directory. At next sections, we will assume that
files will be created inside this directory (in ``.yaml`` format).

The next section will guide you to write a cluster configuration and then,
module's commands will be presented.

Cluster Configuration
++++++++++++++++++++++++++

To create a CLAP's cluster you will need to write:

- **Setup configuration sections**: which define a series of groups and actions that must be performed.
- **Cluster configuration sections**: which define a set of nodes that must be created and the setups that must be performed in each node.

Setups and cluster section may be written in multiple different files (or at the
same file), as CLAP's cluster modules will read all files (and setups and clusters
configurations, respectively) inside the cluster's directory.

Setup Configuration Sections
+++++++++++++++++++++++++++++

Setup configuration sections define a series of roles and/or actions that must be
performed at cluster's nodes. An example of a setup configuration section is
shown below.

.. code-block:: yaml

    # Setup configurations must be declared inside setups key
    setups:

        # This is a setup configuration called setup-common
        setup-common:
            roles:
            - name: commands-common         # Add nodes to commands-common role
            - name: another-role            # Add nodes to another-role role
            actions:
            - role: commands-common
              action: update-packages       # Perform action update-packages from role commands-common
            - command: "git init"           # Perform shell command 'git init'

        # This is a setup configuration called setup-spits-jobmanager
        setup-spits-jobmanager:
            roles:
            - name: spits/jobmanager        # Add nodes to spits' role as jobmanager host

        # This is a setup configuration called setup-spits-taskmanager
        setup-spits-taskmanager:
            roles:
            - name: spits/taskmanager       # Add nodes to spits' role as taskmanager host

Setup configurations must be written inside ``setups`` YAML-dictionary. You can
define as many setup configurations as you want, even at different files but each
one must have a unique name. Inside the ``setups`` section, each dictionary
represents a setup configuration. The dictionary key (``setup-common``,
``setup-spits-jobmanager`` and ``setup-spits-taskmanager`` in above example)
represent the setup configuration ID.

Each setup configuration may contain two dictionaries: ``roles`` and ``actions``
(both are optional). Both sections, for a setup configuration is described in the
next two subsections.

Roles key at setups configuration
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The ``role`` section inside a setup configuration tells to add nodes, whose perform
this setup, to the defined roles. The ``roles`` section contains a **list** describing
each role that the nodes must be added. Also, the role is always added in the order
defined in the list.

Each element of the list must have a ``name`` key, which describe the name of the role
that the node must be added. For instance, the ``setup-common`` at above example,
defines two roles which nodes that perform this setup must be added: ``commands-common``
and ``another-role`` (in this order).

Optionally an ``extra`` key can be defined by each role, as a dictionary. The key
and values is passed as ``extra`` parameter similar to the ``role add`` module
command. For instance, the setup below, will add nodes that perform this setup
(``setup-common-2``) to role ``example-role`` passing variables, ``foo`` and
``another_var`` with values ``bar`` and ``10``, respectively.

.. code-block:: yaml

    # Setup configurations must be declared inside setups key
    setups:

        # This is a setup configuration called setup-common
        setup-common-2:
            roles:
            - name: example-group     # Add nodes to example-role role
              extra:
                foo: bar
                another_var: 10


Actions key at an setups configuration
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The ``actions`` section inside a setup configuration tells to perform actions at
nodes which perform this setup. The ``actions`` section contains a **list**
describing each action that must be performed (in order).
There are three types of actions:

- **role action**: will perform an role action. Thus, the ``role`` and ``action`` keys must be informed. The ``role`` key will tell the name of the role and the ``action`` key will tell which action from that role which will be performed. Optionally, an ``extra`` dictionary can be informed to pass keyword variables to the role's action.
- **playbook**: will execute an Ansible Playbook. Thus, the ``playbook`` key must be informed, telling the absolute path of the playbook that will be executed. Optionally an ``extra`` dictionary can be informed to pass keyword variables to the playbook.
- **command**: will execute a shell command. Thus, the ``command`` key must be informed, telling which shell command must be executed.

Some action examples are briefly shown below:

.. code-block:: yaml

    # Setup configurations must be declared inside setups key
    setups:

        # This is a setup configuration called setup-common. The actions are executed sequentially
        another-setup-example:
            actions:
            # Perform mount action from role nfs-client, passing the variable mount_path with value /mnt
            - action: mount
              role: nfs-client
              extra:
                mount_path: /mnt
            # Execute the playbook /home/my-cool-ansible-playbook with an variable foo with value bar
            - playbook: /home/my-cool-ansible-playbook
              extra:
                foo: bar
            # Execute a shell command: hostname
            - command: hostname
            # Perform reboot action from commands-common role
            - role: commands-common
              action: reboot

.. note::

    If a setup configuration contains both ``roles`` and ``actions`` sections,
    the ``roles`` section will **always** be executed before ``actions`` section.


Cluster Configuration Sections
++++++++++++++++++++++++++++++

The cluster configuration defines a set of nodes that must be created and setups
that must be executed. Clusters are written inside ``clusters`` YAML-dictionary
key and each dictionary inside ``clusters`` key denotes a cluster (where the
dictionary key is the cluster's name).
Above is an example of a cluster configuration:

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

Clusters must have the ``nodes`` section, which defines the nodes that must be
created when the cluster is instantiated. As example above, each cluster's node
have a type (``master-node`` and ``slave-node``) and values, that specify the
cluster's node characteristics. Each node may have the values listed in is table
below.

..  list-table:: Cluster's nodes valid parameters
    :header-rows: 1

    *   - **Name**
        - **Type**
        - **Description**

    *   - ``type``
        - string
        - Instance type that must to be created. The type must match the node name at ``instances.yaml`` file

    *   - ``count``
        - Integer
        - Number of instances of this type to be launched

    *   - ``min_count`` (OPTIONAL)
        - Positive integer (less then or equal ``count`` parameter)
        - Minimum number of instances of this type that must effectively be launched. If this parameter is not supplied the value of ``count`` parameter is assumed

    *   - ``setups``
        - List of strings
        - List with the name of the setup configurations that must be executed after nodes are created

When a cluster is created, the instance types specified in the each node section
is created with the desired ``count`` number. The cluster is considered created
when all nodes are effectively created. The ``min_count`` parameter at each node
specify the minimum number of instances of that type that must effectively be
launched. If some instances could not be instantiated (or created wwith less than
``min_count`` parameter) the cluster creation process fails and all nodes are terminated.

After the cluster is created, i.e. the minimum number of nodes of each type is
successfully created, the ``setups`` for each node is executed, in order. If some
setup does not execute correctly, the cluster remains created and the ``setup``
phase can be executed again.

Controlling cluster's setups execution phases
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

CLAP's cluster module also offers some other facilities to configure the cluster.
By default the cluster module create nodes and run the setup from each node type.
You can control the flow of the setup execution using some optional keys at your
cluster configuration. The keys: ``before_all``, ``before``, ``after`` and
``after_all`` can be plugged into a cluster's configuration, in order to execute
setups in different set of nodes, before and after the nodes setups. These keys
takes a list of setups to execute. CLAP's setup phases are executed in the order,
as shown in table bellow.


..  list-table:: Cluster's setups execution phases (in order)
    :header-rows: 1

    *   - **Phase name**
        - **Description**

    *   - ``before_all`` (#1)
        - Setups inside this key are executed in all cluster's nodes before specific setup of the nodes (#3).

    *   - ``before`` (#2)
        - Setups inside this key are executed only in nodes that are currently being added to the cluster, before the setup specific setup of the nodes (#3). Its useful when resizing cluster, i.e., adding more nodes. This phase is always executed at cluster creation, as all created nodes are being added to the cluster.

    *   - ``node`` (#3)
        - The setup for each node is executed. The setup (inventory generated) is executed only at nodes of this type

    *   - ``after`` (#4)
        - Setups inside this key are executed only in nodes that are currently being added to the cluster, after the setup specific setup of the nodes (#3). Its useful when resizing cluster, i.e., adding more nodes. This phase is always executed at cluster creation, as all created nodes are being added to the cluster.

    *   - ``after_all`` (#5)
        - Setups inside this key are executed in all cluster's nodes after specific setup of the nodes (#3).

.. note::

  All setups are optional


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


In the above example, supposing you are creating a new cluster, after the creation
of nodes the following setups are executed (in order):

- ``before_all`` setups: ``my-custom-setup-1`` at all nodes
- ``before`` setups: ``my-custom-setup-2`` at all nodes
- ``nodes`` setups (not necessary in order): ``another-example-setup`` and ``master-setup`` at ``master-nodes`` nodes and ``setup-slave-node`` at ``slave-nodes`` nodes.
- ``after`` setups: ``my-custom-setup-3`` and ``my-custom-setup-4`` at all nodes
- ``after_all`` setups: ``final_setup`` at all nodes

Now supposing you are resizing the already created cluster (adding more
``slave-nodes`` to it), the ``before_all`` and ``after_all`` setups will be executed
in all cluster's nodes (including the new ones, that are being added) and
``before``, ``nodes`` and ``after`` phase setups will only be executed at nodes
that are being added to the the cluster.

Other cluster's setups optional keys
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The ``options`` key can be plugged at a cluster configuration allowing some special
options to cluster. The ``options`` key may have the following parameters:

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

Start a cluster given a cluster configuration name. The syntax of the command is
shown below

::

    clapp cluster start [OPTIONS] CLUSTER_TEMPLATE

      Start cluster based on a cluster template.

      The CLUSTER TEMPLATE is the ID of the cluster configuration at cluster
      configuration files.

    Options:
      -n, --no-setup  Do not perform setup  [default: False]
      --help          Show this message and exit.



By default, the CLAP's cluster module search for configurations at all ``.yaml``
files inside ``~/.clap/configs/clusters`` directory. After cluster is created,
the setups are automatically executed. You can omit this phase by using the
``--no-setup`` option.

An example of the command is shown below, which starts a cluster called
``example-cluster``.

::

  clapp cluster start example-cluster

.. note::
  - After the cluster's creation a new ``cluster_id`` will be assigned to it. Thus, multiple clusters with same cluster configuration can be launched Also, all commands will reference to ``cluster_id`` to perform their actions.
  - When a cluster is started its initial configuration is copied to cluster metadata. If you update the cluster configuration while having already started clusters use the ``clapp cluster update`` command to update the cluster configuration.


Command ``cluster setup``
++++++++++++++++++++++++++

Setup an existing cluster. The command has the following syntax:

::

    clapp cluster setup [OPTIONS] CLUSTER_ID

      Perform cluster setup operation at a cluster.

      The CLUSTER_ID argument is the id of the cluster to perform the setup

    Options:
      -a, --at TEXT  Stage to start the setup action  [default: before_all]
      --help         Show this message and exit.


Given the ``cluster_id``, the command will execute all setup phases in all cluster
nodes. Some phases of the setup pipeline can be skipped informing at which phase
the setup must begin with the ``at`` parameter.
Examples are shown below:

::

  clapp cluster setup cluster-faa4017e10094e698aed56bb1f3369f9
  clapp cluster setup cluster-faa4017e10094e698aed56bb1f3369f9 --at "before"

In the above examples, the first one setups all cluster nodes from
``cluster-faa4017e10094e698aed56bb1f3369f9``, the second one setups all nodes,
but starting at ``before`` phase.

.. note::

  The ``before_all`` and ``after_all`` phases will be executed at all cluster's nodes, even if setting the ``nodes`` parameter.


Command ``cluster grow``
++++++++++++++++++++++++++

Start and add a new node to cluster, based on its cluster's node name. The command
has the following syntax:

::

    clapp cluster grow [OPTIONS] CLUSTER_ID

      Start more nodes at a cluster by cluster node type.

      The CLUSTER_ID argument is the id of the cluster to add more nodes.

    Options:
      -n, --node TEXT  Type of node to start. Format: <node_type>:<num>
                       [required]
      -n, --no-setup   Do not perform setup  [default: False]
      --help           Show this message and exit.


The ``--node`` parameter determines how much nodes will be added to cluster.
If ``--no-setup`` is provided no setup phase will be executed.

Command ``cluster list``
++++++++++++++++++++++++++

List all available CLAP's clusters.

Command ``cluster alive``
++++++++++++++++++++++++++

Check if all nodes of the cluster are alive.

Command ``cluster resume``
++++++++++++++++++++++++++

Resume all nodes of the cluster.

Command ``cluster pause``
++++++++++++++++++++++++++

Pause all nodes of the cluster.

Command ``cluster stop``
++++++++++++++++++++++++++

Stop all nodes of the cluster, terminating them (destroying).

Command ``cluster list-templates``
+++++++++++++++++++++++++++++++++++

List all available cluster templates at ``~/clap/configs/clusters`` directory.

Command ``cluster update``
+++++++++++++++++++++++++++++

Update a cluster configuration of an already created cluster. The command's
syntax is shown below.

::

    clapp cluster update [OPTIONS] CLUSTER_ID

      Perform cluster setup operation at a cluster.

      The CLUSTER_ID argument is the id of the cluster to perform the setup

    Options:
      -c, --config TEXT  New cluster config name
      --help             Show this message and exit.

If ``--config`` option is provided, the cluster configuration will be replaced
with the informed configuration. Otherwise, the cluster will be updated with the
same configuration.

.. note::

    The configurations will be searched in ``~/clap/configs/clusters`` directory.


Command ``cluster connect``
+++++++++++++++++++++++++++++

Get a SSH shell to a node of the cluster. Given a ``cluster_id`` it will try to
get an SSH shell to a node type specified in ``ssh_to`` cluster configuration
option. If no ``ssh_to`` option is informed at cluster's configuration the command
will try to connect to any other node that belongs to the cluster.

Command ``cluster execute``
+++++++++++++++++++++++++++++

Execute a shell command in nodes of the cluster.

Command ``cluster playbook``
+++++++++++++++++++++++++++++

Execute an Ansible Playbook in nodes of the cluster.