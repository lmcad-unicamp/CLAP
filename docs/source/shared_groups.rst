.. _shared groups:

==========================
Groups shared with CLAP
==========================

Here are some groups shared by default with CLAP. Setup action is **always** executed when adding a node to a group. Also, variables needed by actions must be passed via ``extra`` parameter, as keyword value (see :ref:`group section`).



Group ``commands-common``
--------------------------

This group provide means to execute common known commands in several machines in the group, such as: reboot, copy files to nodes, copy and execute shell scripts, among others.
Consider add nodes to this group to quickly perform common commands in several nodes in a row.

The following actions is provided by this group:

- ``copy``: Copy a file from the localhost to the remote nodes
- ``fetch``: Fetch files from the remote nodes to the localhost
- ``setup``: Does nothing
- ``reboot``: Reboot a machine and waits it to become available
- ``run-command``: Execute a shell command in the remote hosts
- ``run-script``: Transfer a script from localhost to remote nodes and execute it in the remote hosts
- ``update-packages``: Update packages in the remote hosts

Hosts
+++++++++++++++++++

No host must be specified by this group.


Action ``commands-common copy``
++++++++++++++++++++++++++++++++++

Copy a file from the localhost to the remote nodes

Required Variables
^^^^^^^^^^^^^^^^^^^

..  list-table.. code-block:: none ``commands-commands copy`` action variables
    :header-rows: 1

    *   - **Name**
        - **Type**
        - **Description**

    *   - ``src``
        - path
        - File to be copied to the remote hosts. If the path **is not absolute** (it is relative), it will search in the group's files directory else the file indicated will be copied. If the path is a directory, it will be recursive copied.

    *   - ``dest``
        - path
        - Destination path where the files will be put into at remote nodes

Examples
^^^^^^^^^^^^

.. code-block:: none

    clapp group action commands-common copy --extra src="/home/ubuntu/file" dest="~"

The above command copy the file at ``/home/ubuntu/file`` (localhost) the the ``~`` directory of the remote hosts

Or, you can use filters such as ``--nodes`` and ``--tag`` to the ``clapp group action`` command to selectively specify which nodes inside the group the action will be executed.

.. code-block:: none

    clapp group action commands-common copy --nodes node-0  node-1 --extra src="/home/ubuntu/file" dest="~"
    clapp group action commands-common copy --tag 'x=y' --extra src="/home/ubuntu/file" dest="~"


- The first above example copy the file at ``/home/ubuntu/file`` (localhost) the the ``~`` directory of the nodes ``node-0`` and ``node-1``
- The second above example copy the file at ``/home/ubuntu/file`` (localhost) the the ``~`` directory of all nodes in the belonging to the ``commands-common`` group, tagged with ``x=y``


Action ``commands-common fetch``
+++++++++++++++++++++++++++++++++

Fetch files from the remote nodes to the localhost

Required Variables
^^^^^^^^^^^^^^^^^^^

..  list-table.. code-block:: none ``commands-common fetch`` action variables
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

.. code-block:: none

    clapp group action commands-common fetch --extra src="~/file" dest="/home/ubuntu/fetched_files/"

The above command fetch a file at ``~/file`` directory from the nodes and place at the  ``/home/ubuntu/fetched_files/`` directory of the localhost


Action ``commands-common reboot``
++++++++++++++++++++++++++++++++++

Reboot a machine and waits it to become available

Required Variables
^^^^^^^^^^^^^^^^^^^

This action does not require any additional variable to be passed.

Examples
^^^^^^^^^^^^^^^^^^^

.. code-block:: none

    clapp group action commands-common reboot
    clapp group action commands-common reboot --nodes node-0
    clapp group action commands-common reboot --tag 'x=y'

The first command reboot all machines belonging to the ``commands-common`` group, the second one reboot the ``node-0`` and the third one reboot the machines belonging to the group and tagged with ``'x=y'``


Action ``commands-common run-command``
+++++++++++++++++++++++++++++++++++++++++

Execute a shell command in the remote hosts

Required Variables
^^^^^^^^^^^^^^^^^^^

..  list-table.. code-block:: none ``commands-common run-command`` action variables
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

    clapp group action commands-common run-command --extra cmd="ls"
    clapp group action commands-common run-command --extra cmd="ls" workdir="/bin"

In the above command (first one) runs the command ``ls`` in the remote nodes, the second one runs the command ``ls`` in the remote nodes, after changing to the "/bin" directory


Action ``commands-common run-script``
++++++++++++++++++++++++++++++++++++++

Transfer a script from localhost to remote nodes and execute it in the remote hosts

Required Variables
^^^^^^^^^^^^^^^^^^^

..  list-table.. code-block:: none ``commands-common run-script`` action variables
    :header-rows: 1

    *   - **Name**
        - **Type**
        - **Description**

    *   - ``src``
        - string
        - Shell script file to be executed in the remote nodes. The file will be first copied (from localhost) to the nodes and after will be executed. Note: the script file **must begin** with the bash shebang (``#!/bin/bash``). Also the script filepath must be **absolute** else, if relative path is passed, Ansible seach in the group's file directory. The script will be deleted from nodes after execution.

    *   - ``args`` (optional)
        - string
        - Command-line arguments to be passed to the script.

    *   - ``workdir`` (optional)
        - path
        - Change into this directory before running the command. If none is passed, home directory of the remote node will be used (Path must be absolute for Unix-aware nodes)

Examples
^^^^^^^^^^^^^^^^^^^

.. code-block:: none

    clapp group action commands-common run-script --extra src="/home/ubuntu/echo.sh"
    clapp group action commands-common run-script --extra src="/home/ubuntu/echo.sh" args="1 2 3"
    clapp group action commands-common run-script --extra src="/home/ubuntu/echo.sh" args="1 2 3" workdir="/home"


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

    clapp group action commands-common update-packages

The above command will update the package list from remote hosts (similar to ``apt update`` command)



Group ``docker``
-----------------

This group installs docker-ce in debian and red-hat based systems. The following actions are provided by this group.

- ``setup``: Install docker-ce and start the service

Hosts
+++++++++++++++++++

No host must be specified by this group.



Group ``ec2-efs``
--------------------

This group setup and mount an network EFS filesystem on AWS provider. The following actions are provided by the group.

- ``setup``: Install nfs client and mount EC2 file system 
- ``umount``: Unmount EC2 File System

Hosts
+++++++++++++++++++

No host must be specified by this group.

Action ``ec2-efs setup``
++++++++++++++++++++++++++++

Install nfs client and mount EC2 file system. This action is executed when nodes are added to the group.

Required Variables
^^^^^^^^^^^^^^^^^^^
..  list-table.. code-block:: none ``ec2-efs setup`` action variables
    :header-rows: 1

    *   - **Name**
        - **Type**
        - **Description**

    *   - ``efs_mount_point``
        - path
        - Directory path where the filesystem will be mounted

    *   - ``user``
        - string
        - Name of the user owner (e.g. ubuntu)

    *   - ``group``
        - string
        - Name of the group owner (e.g. ubuntu)

    *   - ``mount_ip``
        - string
        - Mount ip of the filesystem (see `AWS EFS Documentation <https://docs.aws.amazon.com/efs/latest/ug/accessing-fs.html>`_ for more information)

    *   - ``mount_permissions``
        - string
        - Permission used tomount the filesystem (e.g. 0644)

Examples
^^^^^^^^^^^^^^^^^^^

.. code-block:: none

    clapp group add ec2-efs node-0 --extra efs_mount_point="/efs" user="ubuntu" group="ubuntu" mount_ip="192.168.0.1" mount_permissions="0644"

The above command will install EC2 EFS filesystem on ``node-0`` and mount the EFS Filesystem from ``192.168.0.1`` it at ``/efs`` with ``0644`` permissions (read-write for user and read-only for others).

Action ``ec2-efs umount``
++++++++++++++++++++++++++++

Unmount the EC2 File System

Required Variables
^^^^^^^^^^^^^^^^^^^

..  list-table.. code-block:: none ``ec2-efs umount`` action variables
    :header-rows: 1

    *   - **Name**
        - **Type**
        - **Description**

    *   - ``efs_mount_point``
        - path
        - Directory path where the filesystem will be unmounted


Examples
^^^^^^^^^^^^^^^^^^^

.. code-block:: none

    clapp group action ec2-efs umount --nodes node-0 --extra efs_mount_point="/efs"

The above command will unmount EC2 EFS filesystem from ``node-0``



Group ``spits``
-------------------

Install `spits runtime for the SPITS programming model <https://github.com/lmcad-unicamp/spits-2.0/>`_ in nodes, deploy SPITS applications and collect results from execution. The following actions are provided by this group.

- ``add-nodes``: If no shared filesystem is being used, this action informs to the job manager node, the address of all task managers.
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

This group defines two host types:

- ``spits/jobmanager``: Nodes where job manager will be executed for a job
- ``spits/taskmanager``: Nodes where task manager will be executed for a job

Typical Workflow
+++++++++++++++++++

The ``spits`` group is used to run SPITS applications. For each SPITS application to run, you must create a SPITS job, with an unique Job ID. One node can execute multiple SPITS jobs. 

Thus, a typical workflow for usage is:

1. Add job manager desired nodes to ``spits/jobmanager`` group and task manager desired nodes to ``spits/taskmanager``
2. Use ``job-create`` action the create a new SPITS job in all machines belonging to ``spits`` group (filter nodes if you want to create a job at selected nodes only).
3. Use ``start`` action to start the SPITS job manager and SPITS task manager at nodes to run the SPITS job
4. If you are not using a shared filesystem, use the ``add-nodes`` action to copy addresses from task manager nodes to the job manager node.
5. Optionally, check the job status using the ``job-status`` action.
6. When job is finished, use ``job-copy`` action to get the results.

Action ``spits add-nodes``
++++++++++++++++++++++++++++

If no shared filesystem is being used, this action informs to the job manager node, the address of all task managers.

Required Variables
^^^^^^^^^^^^^^^^^^^

..  list-table.. code-block:: none ``spits add-nodes`` action variables
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

    clapp group action spits add-nodes --extra "jobid=my-job-123"

The above example will add all task manager addresses, from nodes belonging to the ``spits/taskmanager`` group to the ``spits/jobmanager`` nodes at job ``my-job-123``. At this point, the job manager nodes recognizes all task managers.

.. note::
    
    - This action is not needed if job manager and task managers are running at same node


Action ``spits job-copy``
++++++++++++++++++++++++++++

Copy the results (job directory) from the job manager to the localhost

Required Variables
^^^^^^^^^^^^^^^^^^^

..  list-table.. code-block:: none ``spits job-copy`` action variables
    :header-rows: 1

    *   - **Name**
        - **Type**
        - **Description**

    *   - ``jobid``
        - string
        - Unique job identifier (must match the job ID used in the ``job-create`` action)

    *   - ``outputdir``
        - path
        - Path where 

    *   - ``PYPITS_PATH`` (OPTIONAL)
        - path
        - Directory path where the pypits will be installed (default: ``${HOME}/pypits/``)

    *   - ``SPITS_JOB_PATH`` (OPTIONAL)
        - path
        - Directory path where the spits jobs will be created (default: ``${HOME}/spits-jobs/``)

Examples
^^^^^^^^^^^^^^^^^^^

.. code-block:: none

    clapp group action spits job-copy --extra "jobid=my-job-123" "outputdir=/home/app-output"

The above example will copy the entire job folder (including logs/results) to the localhost and put at ``/home/app-output`` directory.


Action ``spits job-create``
++++++++++++++++++++++++++++

Create a SPITS job in nodes to run an SPITS application.


Required Variables
^^^^^^^^^^^^^^^^^^^

..  list-table.. code-block:: none ``spits job-create`` action variables
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

    clapp group action spits job-create --extra "jobid=my-job-123" "spits_binary=/home/xxx/spits-app" "spits_args=foo bar 10"

The above example create the a job called ``my-job-123`` in all nodes belonging to the ``spits`` group. The job will execute the SPITS runtime with the binary ``/home/xxx/spits-app`` (that will be copied from localhost to nodes) with arguments ``foo bar 10``.

Action ``spits job-status``
++++++++++++++++++++++++++++

Query job manager nodes the status and the metrics of a running SPITS job

Required Variables
^^^^^^^^^^^^^^^^^^^

..  list-table.. code-block:: none ``spits job-status`` action variables
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

    clapp group action spits job-status --extra "jobid=my-job-123"

The above example query the status of a SPITS job with ID ``my-job-123`` from nodes belonging to ``spits/jobmanager`` group. The job status will be displayed at the command output (in green).


Action ``spits setup``
++++++++++++++++++++++++++++

Install SPITS runtime and its dependencies at nodes

Required Variables
^^^^^^^^^^^^^^^^^^^

This action does not require any additional variable to be passed. Optional variables can be passed.

..  list-table.. code-block:: none ``spits setup`` action variables
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

    clapp group add spits/jobmanager node-0
    clapp group add spits/taskmanager node-1 node-2

The above examples install SPITS runtime at ``node-0``, ``node-1`` and ``node-2``. ``node-0`` is set as job manager host and nodes ``node-1`` and ``node-2`` are set as task manager host.


Action ``spits start``
++++++++++++++++++++++++++++

Start a SPITS job at job manager and task manager nodes


Required Variables
^^^^^^^^^^^^^^^^^^^

..  list-table.. code-block:: none ``spits job-create`` action variables
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

    clapp group action spits start --extra "jobid=my-job-123" "jm_args=-vv"

The above example starts job managers and task managers for job ``my-job-123`` in nodes belonging to ``spits`` group. Also, job managers SPITS runtime are executed passing the ``-vv`` parameter.

.. note::

    The ``job-create`` action must be used before to create the SPITS job at nodes belonging to ``spits`` group. 


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
