.. _shared_roles:

==========================
Roles shared with CLAP
==========================

Here are some roles shared by default with CLAP. Setup action is **always**
executed when adding a node to a role. Also, variables needed by actions must be
passed via ``extra`` parameter, as keyword value.


Role ``commands-common``
--------------------------

This role provide means to execute common known commands in several machines in
the role, such as: reboot, copy files to nodes, copy and execute shell scripts,
among others. Consider add nodes to this role to quickly perform common commands
in several nodes in a row.

The following actions is provided by this role:

- ``copy``: Copy a file from the localhost to the remote nodes
- ``fetch``: Fetch files from the remote nodes to the localhost
- ``reboot``: Reboot a machine and waits it to become available
- ``run-command``: Execute a shell command in the remote hosts
- ``run-script``: Transfer a script from localhost to remote nodes and execute it in the remote hosts
- ``update-packages``: Update packages in the remote hosts

Hosts
+++++++++++++++++++

No host must be specified by this role.


Action ``commands-common copy``
++++++++++++++++++++++++++++++++++

Copy a file from the localhost to the remote nodes

Required Variables
^^^^^^^^^^^^^^^^^^^

..  list-table::  ``commands-commands copy`` action variables
    :header-rows: 1

    *   - **Name**
        - **Type**
        - **Description**

    *   - ``src``
        - path
        - File to be copied to the remote hosts. If the path **is not absolute** (it is relative), it will search in the role's files directory else the file indicated will be copied. If the path is a directory, it will be recursive copied.

    *   - ``dest``
        - path
        - Destination path where the files will be put into at remote nodes

Examples
^^^^^^^^^^^^

::

    clapp role action commands-common copy --extra src="/home/ubuntu/file" -e dest="~"

The above command copy the file at ``/home/ubuntu/file`` (localhost) the the ``~`` directory of the nodes.


Action ``commands-common fetch``
+++++++++++++++++++++++++++++++++

Fetch files from the remote nodes to the localhost

Required Variables
^^^^^^^^^^^^^^^^^^^

..  list-table::  ``commands-common fetch`` action variables
    :header-rows: 1

    *   - **Name**
        - **Type**
        - **Description**

    *   - ``src``
        - path
        - File to be copied from the remote hosts. If the file is a directory, it will be recursive copied.

    *   - ``dest``
        - path
        - Destination path where the files will be put into (localhost)

Examples
^^^^^^^^^^^^^^^^^^^

::

    clapp role action commands-common fetch --extra src="~/file" --extra dest="/home/ubuntu/fetched_files/"

The above command fetch a file at ``~/file`` directory from the nodes and place
at the ``/home/ubuntu/fetched_files/`` directory of the localhost.


Action ``commands-common install-packages`` 
++++++++++++++++++++++++++++++++++++++++++++++

Install packages in the remote hosts

Required Variables
^^^^^^^^^^^^^^^^^^^

..  list-table::  ``commands-common install-packages`` action variables
    :header-rows: 1

    *   - **Name**
        - **Type**
        - **Description**

    *   - ``packages``
        - string
        - Comma-separated list of packages to install.

Examples
^^^^^^^^^^^^^^^^^^^

::

    clapp role action commands-common install-packages --extra "packages=openmpi-bin,openmpi-common"

The above command will install ``openmpi-bin`` and ``openmpi-common`` packages to remote hosts


Action ``commands-common reboot``
++++++++++++++++++++++++++++++++++

Reboot a machine and waits it to become available

Required Variables
^^^^^^^^^^^^^^^^^^^

This action does not require any additional variable to be passed.

Examples
^^^^^^^^^^^^^^^^^^^

::

    clapp role action commands-common reboot

The command reboot all machines belonging to the ``commands-common`` role.

Action ``commands-common run-command``
+++++++++++++++++++++++++++++++++++++++++

Execute a shell command in the remote hosts

Required Variables
^^^^^^^^^^^^^^^^^^^

..  list-table::  ``commands-common run-command`` action variables
    :header-rows: 1

    *   - **Name**
        - **Type**
        - **Description**

    *   - ``cmd``
        - string
        - String with the command to be executed in the nodes

    *   - ``workdir`` (optional)
        - path
        - Change into this directory before running the command. If none is passed, home directory of the remote node will be used

Examples
^^^^^^^^^^^^^^^^^^^

.. code-block:: none

    clapp role action commands-common run-command --extra cmd="ls"
    clapp role action commands-common run-command --extra cmd="ls" -e "workdir=/bin"

In the above command (first one) runs the command ``ls`` in the remote nodes,
the second one runs the command ``ls`` in the remote nodes, after changing to the
"/bin" directory


Action ``commands-common run-script``
++++++++++++++++++++++++++++++++++++++

Transfer a script from localhost to remote nodes and execute it in the remote hosts

Required Variables
^^^^^^^^^^^^^^^^^^^

..  list-table::  ``commands-common run-script`` action variables
    :header-rows: 1

    *   - **Name**
        - **Type**
        - **Description**

    *   - ``src``
        - string
        - Shell script file to be executed in the remote nodes. The file will be first copied (from localhost) to the nodes and after will be executed. Note: the script file **must begin** with the bash shebang (``#!/bin/bash``). Also the script filepath must be **absolute** else, if relative path is passed, Ansible search in the role's file directory. The script will be deleted from nodes after execution.

    *   - ``args`` (optional)
        - string
        - Command-line arguments to be passed to the script.

    *   - ``workdir`` (optional)
        - path
        - Change into this directory before running the command. If none is passed, home directory of the remote node will be used (Path must be absolute for Unix-aware nodes)

Examples
^^^^^^^^^^^^^^^^^^^

.. code-block:: none

    clapp role action commands-common run-script --extra src="/home/ubuntu/echo.sh"
    clapp role action commands-common run-script --extra src="/home/ubuntu/echo.sh" -e args="1 2 3"
    clapp role action commands-common run-script --extra src="/home/ubuntu/echo.sh" -e args="1 2 3" -e workdir="/home"


The above command (first one) will copy the ``/home/ubuntu/echo.sh`` script from localhost to the remote nodes and execute it (similar to run ``bash -c echo.sh`` in the hosts).

The above command (second one) will copy the ``/home/ubuntu/echo.sh`` script from localhost to the remote nodes and execute it using the arguments "1 2 3" (similar to run ``bash -c echo.sh 1 2 3`` in the hosts).

The above command (third one) is similar to the second one but will execute the script in the ``/home`` directory.


Action ``commands-common update-packages`` 
++++++++++++++++++++++++++++++++++++++++++++++

Update packages in the remote hosts

Required Variables
^^^^^^^^^^^^^^^^^^^

This action does not require any additional variable to be passed

Examples
^^^^^^^^^^^^^^^^^^^

.. code-block:: none

    clapp role action commands-common update-packages

The above command will update the package list from remote hosts (similar to ``apt update`` command)



.. Group ``docker``
.. -----------------

.. This group installs docker-ce in debian and red-hat based systems. The following actions are provided by this group.

.. - ``setup``: Install docker-ce and start the service

.. Hosts
.. +++++++++++++++++++

.. No host must be specified by this group.



Group ``ec2-efs``
--------------------

This role setup and mount an network EFS filesystem on AWS provider.
The following actions are provided by the role.

- ``setup``: Install nfs client
- ``mount``: Mount an EFS filesystem
- ``umount``: Unmount EC2 File System

Hosts
+++++++++++++++++++

No hosts must be specified by this role.

Action ``ec2-efs setup``
++++++++++++++++++++++++++++

Install nfs client at remote host. This action is executed when nodes are added
to the role.

Required Variables
^^^^^^^^^^^^^^^^^^^

This action does not require any additional variable to be passed

Action ``ec2-efs mount``
++++++++++++++++++++++++++++

Mount an AWS EC2 EFS filesystem at remote host.

Required Variables
^^^^^^^^^^^^^^^^^^^
..  list-table::  ``ec2-efs mount`` action variables
    :header-rows: 1

    *   - **Name**
        - **Type**
        - **Description**

    *   - ``efs_mount_ip``
        - string
        - Mount IP of the filesystem (see `AWS EFS Documentation <https://docs.aws.amazon.com/efs/latest/ug/accessing-fs.html>`_ for more information)

    *   - ``efs_mount_point`` (OPTIONAL)
        - path
        - Directory path where the filesystem will be mounted. Default path is: ``/efs``

    *   - ``efs_owner`` (OPTIONAL)
        - string
        - Name of the user owner (e.g. ubuntu). Default user is the currently logged user

    *   - ``efs_group`` (OPTIONAL)
        - string
        - Name of the group owner (e.g. ubuntu). Default group is the currently logged user

    *   - ``efs_mount_permissions`` (OPTIONAL)
        - string
        - Permission used to mount the filesystem (e.g. 0644). Default permission is ``0744``

Examples
^^^^^^^^^^^^^^^^^^^

.. code-block:: none

    clapp role action ec2-efs mount --extra "efs_mount_ip="192.168.0.1" -e "efs_mount_point=/tmp"

The above command will mount the EFS Filesystem from ``192.168.0.1`` it at ``/tmp``
with ``744`` permissions (read-write-execute for user and read-only for group and others).

Action ``ec2-efs umount``
++++++++++++++++++++++++++++

Unmount the EC2 File System

Required Variables
^^^^^^^^^^^^^^^^^^^

..  list-table::  ``ec2-efs umount`` action variables
    :header-rows: 1

    *   - **Name**
        - **Type**
        - **Description**

    *   - ``efs_mount_point`` (OPTIONAL)
        - path
        - Directory path where the filesystem will be mounted. Default path is: ``/efs``


Examples
^^^^^^^^^^^^^^^^^^^

.. code-block:: none

    clapp role action ec2-efs umount --nodes node-0 --extra efs_mount_point="/efs"

The above command will unmount EC2 EFS filesystem at ``/efs`` directory from ``node-0``



Role ``spits``
-------------------

Install `spits runtime for the SPITS programming model <https://github.com/lmcad-unicamp/spits-2.0/>`_
in nodes, deploy SPITS applications and collect results from execution. The
following actions are provided by this role.

- ``add-nodes``: This action informs to the job manager node, the public address of all task managers.
- ``job-copy``: Copy the results (job directory) from the job manager to the localhost.
- ``job-create``: Create a SPITS job in nodes
- ``job-status``: Query job manager nodes the status and the metrics of a running SPITS job
- ``setup``: Install SPITS runtime and its dependencies at nodes
- ``start``: Start a SPITS job at job manager and task manager nodes

.. note::

    For now, shared filesystem is **not supported** for SPITS runtime.

.. warning:: 

   SPITS application are started using random TCP ports. For now, your security group must allows the communication from/to random IP addresses and ports. So, set inbound and outbound rules from you security group to allow the communication from anywhere to anywhere at any port.

Hosts
+++++++++++++++++++

This role defines two host types:

- ``jobmanager``: Nodes where job manager will be executed for a job
- ``taskmanager``: Nodes where task manager will be executed for a job

Typical Workflow
+++++++++++++++++++

The ``spits`` role is used to run SPITS applications. For each SPITS application to run, you must create a SPITS job, with an unique Job ID. One node can execute multiple SPITS jobs.

Thus, a typical workflow for usage is:

1. Add job manager desired nodes to ``spits/jobmanager`` role and task manager desired nodes to ``spits/taskmanager``
2. Use ``job-create`` action the create a new SPITS job in all machines belonging to ``spits`` role (filter nodes if you want to create a job at selected nodes only).
3. Use ``start`` action to start the SPITS job manager and SPITS task manager at nodes to run the SPITS job
4. Use the ``add-nodes`` action to copy public addresses from task managers nodes to the job manager node.
5. Optionally, check the job status using the ``job-status`` action.
6. When job is finished, use ``job-copy`` action to get the results.

Action ``spits add-nodes``
++++++++++++++++++++++++++++

This action informs to the job manager node, the public address of all task managers.

Required Variables
^^^^^^^^^^^^^^^^^^^

..  list-table::  ``spits add-nodes`` action variables
    :header-rows: 1

    *   - **Name**
        - **Type**
        - **Description**

    *   - ``jobid``
        - string
        - Unique job identifier (must match the job ID used in the ``job-create`` action)

    *   - ``PYPITS_PATH`` (OPTIONAL)
        - path
        - Directory path where the pypits will be installed (default: ``${HOME}/pypits/``)

    *   - ``SPITS_JOB_PATH`` (OPTIONAL)
        - path
        - Directory path where the spits jobs will be created (default: ``${HOME}/spits-jobs/``)


Examples
^^^^^^^^^^^^^^^^^^^

.. code-block:: none

    clapp role action spits add-nodes --extra "jobid=my-job-123"

The above example will add all task manager addresses, from nodes belonging to
the ``spits/taskmanager`` role to the ``spits/jobmanager`` nodes at job ``my-job-123``.
At this point, the job manager nodes recognizes all task managers.

.. note::
    
    - This action is not needed if job manager and task managers are running at same node


Action ``spits job-copy``
++++++++++++++++++++++++++++

Copy the results (job directory) from the job manager to the localhost

Required Variables
^^^^^^^^^^^^^^^^^^^

..  list-table::  ``spits job-copy`` action variables
    :header-rows: 1

    *   - **Name**
        - **Type**
        - **Description**

    *   - ``jobid``
        - string
        - Unique job identifier (must match the job ID used in the ``job-create`` action)

    *   - ``outputdir``
        - path
        - Path where job will be copied to

    *   - ``PYPITS_PATH`` (OPTIONAL)
        - path
        - Directory path where the pypits will be installed (default: ``${HOME}/pypits/``)

    *   - ``SPITS_JOB_PATH`` (OPTIONAL)
        - path
        - Directory path where the spits jobs will be created (default: ``${HOME}/spits-jobs/``)

Examples
^^^^^^^^^^^^^^^^^^^

.. code-block:: none

    clapp role action spits job-copy -e "jobid=my-job-123" -e "outputdir=/home/app-output"

The above example will copy the entire job folder (including logs/results) to the
localhost and put at ``/home/app-output`` directory.


Action ``spits job-create``
++++++++++++++++++++++++++++

Create a SPITS job in nodes to run an SPITS application. If you are using a shared
filesystem, use this action in only one node and set the ``SPITS_JOB_PATH``
variable to the desired location.


Required Variables
^^^^^^^^^^^^^^^^^^^

..  list-table::  ``spits job-create`` action variables
    :header-rows: 1

    *   - **Name**
        - **Type**
        - **Description**

    *   - ``jobid``
        - string
        - Unique job ID to identify the SPITS job.

    *   - ``spits_binary``
        - path
        - Absolute path to the SPITS binary (at localhost) that will be copied to nodes

    *   - ``spits_args``
        - string
        - Arguments that will be passed to the SPITS binary when executing the SPITS application

    *   - ``PYPITS_PATH`` (OPTIONAL)
        - path
        - Directory path where the pypits will be installed (default: ``${HOME}/pypits/``)

    *   - ``SPITS_JOB_PATH`` (OPTIONAL)
        - path
        - Directory path where the spits jobs will be created (default: ``${HOME}/spits-jobs/``)

Examples
^^^^^^^^^^^^^^^^^^^

.. code-block:: none

    clapp role action spits job-create --extra "jobid=my-job-123" -e "spits_binary=/home/xxx/spits-app" -e "spits_args=foo bar 10"

The above example create the a job called ``my-job-123`` in all nodes belonging
to the ``spits`` role. The job will execute the SPITS runtime with the binary
``/home/xxx/spits-app`` (that will be copied from localhost to nodes) with
arguments ``foo bar 10``.

Action ``spits job-status``
++++++++++++++++++++++++++++

Query job manager nodes the status and the metrics of a running SPITS job

Required Variables
^^^^^^^^^^^^^^^^^^^

..  list-table::  ``spits job-status`` action variables
    :header-rows: 1

    *   - **Name**
        - **Type**
        - **Description**

    *   - ``jobid``
        - string
        - Unique job identifier (must match the job ID used in the ``job-create`` action)

    *   - ``PYPITS_PATH`` (OPTIONAL)
        - path
        - Directory path where the pypits will be installed (default: ``${HOME}/pypits/``)

    *   - ``SPITS_JOB_PATH`` (OPTIONAL)
        - path
        - Directory path where the spits jobs will be created (default: ``${HOME}/spits-jobs/``)


Examples
^^^^^^^^^^^^^^^^^^^
.. code-block:: none

    clapp role action spits job-status --extra "jobid=my-job-123"

The above example query the status of a SPITS job with ID ``my-job-123`` from
nodes belonging to ``spits/jobmanager`` role. The job status will be displayed
at the command output (in green).


Action ``spits setup``
++++++++++++++++++++++++++++

Install SPITS runtime and its dependencies at nodes

Required Variables
^^^^^^^^^^^^^^^^^^^

This action does not require any additional variable to be passed. Optional
variables can be passed.

..  list-table::  ``spits setup`` action variables
    :header-rows: 1

    *   - **Name**
        - **Type**
        - **Description**

    *   - ``PYPITS_PATH`` (OPTIONAL)
        - path
        - Directory path where the pypits will be installed (default: ``${HOME}/pypits/``)

    *   - ``SPITS_JOB_PATH`` (OPTIONAL)
        - path
        - Directory path where the spits jobs will be created (default: ``${HOME}/spits-jobs/``)

Examples
^^^^^^^^^^^^^^^^^^^

.. code-block:: none

    clapp role add -n jobmanager:node-0 -n taskmanager:node-1,node-2

The above example install SPITS runtime at ``node-0``, ``node-1`` and ``node-2``.
``node-0`` is set as job manager host and nodes ``node-1`` and ``node-2`` are
set as task manager host.


Action ``spits start``
++++++++++++++++++++++++++++

Start a SPITS job at job manager and task manager nodes


Required Variables
^^^^^^^^^^^^^^^^^^^

..  list-table::  ``spits start`` action variables
    :header-rows: 1

    *   - **Name**
        - **Type**
        - **Description**

    *   - ``jobid``
        - string
        - Unique job identifier (must match the job ID used in the ``job-create`` action)

    *   - ``jm_args``
        - string
        - Arguments to be passed to the job manager SPITS runtime

    *   - ``tm_args``
        - string
        - Arguments to be passed to the task manager SPITS runtime

    *   - ``PYPITS_PATH`` (OPTIONAL)
        - path
        - Directory path where the pypits will be installed (default: ``${HOME}/pypits/``)

    *   - ``SPITS_JOB_PATH`` (OPTIONAL)
        - path
        - Directory path where the spits jobs will be created (default: ``${HOME}/spits-jobs/``)

Examples
^^^^^^^^^^^^^^^^^^^

.. code-block:: none

    clapp role action spits start --extra "jobid=my-job-123" -e "jm_args=-vv"

The above example starts job managers and task managers for job ``my-job-123`` in
nodes belonging to ``spits`` role. Also, job managers SPITS runtime are executed
passing the ``-vv`` parameter.

.. note::

    The ``job-create`` action must be used before to create the SPITS job at nodes belonging to ``spits`` role.


.. Group ``nfs-client``
.. ---------------------

.. This group setup and mount an network EFS filesystem on AWS provider.

.. - ``setup``: Install nfs client and mount EC2 file system 
.. - ``umount``: Unmount EC2 File System

.. Hosts
.. +++++++++++++++++++

.. No host must be specified by this group.

.. Action ``ec2-efs setup``
.. ++++++++++++++++++++++++++++

.. Install nfs client and mount EC2 file system. This action is executed when nodes are added to the group.

.. Required Variables
.. ^^^^^^^^^^^^^^^^^^^
