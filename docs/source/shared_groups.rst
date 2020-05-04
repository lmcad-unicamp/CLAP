.. _shared groups:

==========================
Groups shared with CLAP
==========================

Here are some groups shared with CLAP. Setup action is **always** executed when adding a node to a group.
Also, the ``--nodes`` and ``--tag`` parameters can be passed to the ``clapp group action`` command to selectively select nodes inside the group that will execute the action, else the action will be performed in all nodes belonging to a group.


Commands common
-------------------

This group provide means to execute common known commands in several machines in the group, such as: reboot, copy files to nodes, copy and execute shell scripts, among others.
Consider add instances to this group to quickly perform common commands in several nodes in a row.

No hosts are needed for this group.

..  list-table.. code-block:: none Common available actions
    :header-rows: 1

    *   - **Name**
        - **Description**

    *   - ``copy``
        - Copy a file from the localhost to the remote nodes

    *   - ``fetch``
        - Fetch files from the remote nodes to the localhost

    *   - ``reboot``
        - Reboot a machine and waits it to become available

    *   - ``run-command``
        - Execute a **shell** command in the remote hosts

    *   - ``run-script``
        - Transfer a script from localhost to remote nodes and execute it in the remote hosts

    *   - ``update-packages``
        - Update packages in the remote hosts

Variables and examples for each action is shown below


copy action variables
++++++++++++++++++++++++++

The following variables must be informed when running the ``copy`` action (via ``extra`` parameter)

..  list-table.. code-block:: none Common-commands ``copy`` action variables
    :header-rows: 1

    *   - **Name**
        - **Type**
        - **Description**

    *   - ``src``
        - path
        - File to be copied to the remote hosts. If the path **is not absolute** (it is relative), it will search in the group's files directory else the file indicated will be copied.
          If the file is a directory, it will be recursive copied.

    *   - ``dest``
        - path
        - Destination path where the files will be put into (remote nodes)


Examples of the group's ``copy`` action is showed below:

.. code-block:: none

    clapp group action commands-common copy --extra src="/home/ubuntu/file" dest="~"

The above command copy the file at ``/home/ubuntu/file`` (localhost) the the ``~`` directory of the remote hosts

Or, you can use filters such as ``--nodes`` and ``--tag`` to the ``clapp group action`` command to selectively specify which nodes inside the group the action will be executed

.. code-block:: none

    clapp group action commands-common copy --nodes node-0  node-1 --extra src="/home/ubuntu/file" dest="~"
    clapp group action commands-common copy --tag 'x=y' --extra src="/home/ubuntu/file" dest="~"


The above (first one) command copy the file at ``/home/ubuntu/file`` (localhost) the the ``~`` directory of the nodes ``node-0`` and ``node-1``

The above (second one) command copy the file at ``/home/ubuntu/file`` (localhost) the the ``~`` directory of all nodes in the belonging to the ``commands-common`` group, tagged with ``x=y``


fetch action variables
++++++++++++++++++++++++++++

The following variables must be informed when running the ``fetch`` action (via ``extra`` parameter)

..  list-table.. code-block:: none Common-commands ``fetch`` action variables
    :header-rows: 1

    *   - **Name**
        - **Type**
        - **Description**

    *   - ``src``
        - path
        - File to be copied from the remote hosts.
          If the file is a directory, it will be recursive copied.

    *   - ``dest``
        - path
        - Destination path where the files will be put into (localhost)


Examples of the group ``fetch`` action is showed below:

.. code-block:: none

    clapp group action commands-common fetch --extra src="~/file" dest="/home/ubuntu/fetched_files/"

The above command fetch a file at ``~/file`` directory from the nodes and place at the  ``/home/ubuntu/fetched_files/`` directory of the localhost


reboot action variables
++++++++++++++++++++++++++++

This action does not require any additional variable to be passed

.. code-block:: none

    clapp group action commands-common reboot
    clapp group action commands-common reboot --nodes node-0
    clapp group action commands-common reboot --tag 'x=y'

The first command reboot all machines belonging to the ``commands-common`` group.

The second one reboot the ``node-0`` and the third one reboot the machines belonging to the group and tagged with ``'x=y'``


run-command action variables
+++++++++++++++++++++++++++++

The following variables must be informed when running the ``run-command`` action (via ``extra`` parameter)

..  list-table.. code-block:: none Common-commands ``run-command`` action variables
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


Examples of the group ``run-command`` action is showed below:

.. code-block:: none

    clapp group action commands-common run-command --extra cmd="ls"
    clapp group action commands-common run-command --extra cmd="ls" workdir="/bin"

The above command (first one) runs the command ``ls`` in the remote nodes

The above command (second one) runs the command ``ls`` in the remote nodes, after changing to the "/bin" directory


run-script action variables
++++++++++++++++++++++++++++

The following variables must be informed when running the ``run-script`` action (via ``extra`` parameter).

..  list-table.. code-block:: none Common-commands ``run-script`` action variables
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


Examples of the group ``run-script`` action is showed below:

.. code-block:: none

    clapp group action commands-common run-script --extra src="/home/ubuntu/echo.sh"
    clapp group action commands-common run-script --extra src="/home/ubuntu/echo.sh" args="1 2 3"
    clapp group action commands-common run-script --extra src="/home/ubuntu/echo.sh" args="1 2 3" workdir="/home"


The above command (first one) will copy the ``/home/ubuntu/echo.sh`` script from localhost to the remote nodes and execute it (similar to run ``bash -c echo.sh`` in the hosts).

The above command (second one) will copy the ``/home/ubuntu/echo.sh`` script from localhost to the remote nodes and execute it using the arguments "1 2 3" (similar to run ``bash -c echo.sh 1 2 3`` in the hosts).

The above command (third one) is similar to the second one but will execute the script in the ``/home`` directory.



update-packages action variables
++++++++++++++++++++++++++++++++++

This action does not require any additional variable to be passed

.. code-block:: none

    clapp group action commands-common update-packages

The above command will update the package list from remote hosts (similar to ``apt update`` command)



EC2 Common
---------------

This group provide means to interact with AWS EC2 instances, such as pausing and resuming nodes

The actions for the group is listed below (the ``setup`` action is automatically executed when the node is added to the group).
No hosts are needed for this group.

..  list-table.. code-block:: none EC2 Common group actions
    :header-rows: 1

    *   - **Name**
        - **Description**

    *   - ``pause``
        - Pause (stop) instances in the EC2 cloud

    *   - ``resume``
        - Resume paused (stopped) instances in the EC2 cloud

    *   - ``list-vols``
        - List mounted volumes from instances


    *   - ``attach-ebs``
        - Mount EBS volume to instances


- Adding nodes to the group

.. code-block:: none

    clapp group add ec2-common node-0


The above command add ``node-0`` to the EC2 Common group


Other variables and commands for each action are shown in sections below.


Pause action and variables
++++++++++++++++++++++++++++

This action does not require any additional variable to be passed.
To pause instances (not destroy), use te following commands

.. code-block:: none

    clapp group action ec2-common pause
    clapp group action ec2-common pause --nodes node-0 node-1
    clapp group action ec2-common pause --tag "x=y"

For the above commands, the first one pause (stop) all EC2 instances belonging tho the EC2 Common group
and the second one pause only the nodes ``node-0`` and ``node-1``.
The third one pause instances of the group tagged with "x=y"


Resume action and variables
++++++++++++++++++++++++++++

This action does not require any additional variable to be passed.
To resume paused instances, use te following commands

.. code-block:: none

    clapp group action ec2-common resume
    clapp group action ec2-common resume --nodes node-0 node-1
    clapp group action ec2-common resume --tag "x=y"

For the above commands, the first one resume all EC2 instances belonging tho the EC2 Common group
and the second one resume only the nodes ``node-0`` and ``node-1``.
The third one resume instances of the group tagged with "x=y"

**NOTE**: When instances are resumed their public IP may change. Use the ``clapp node alive`` command to refresh the nodes and their respective IPs!



List volumes action and variables
+++++++++++++++++++++++++++++++++++++

This action does not require any additional variable to be passed.
To list mounted volumes of isntances, use the commands below:

.. code-block:: none

    clapp group action ec2-common list-vols

The command outputs the volumes attached to each instance in the ec2-common group


Attach EBS volumes action and variables
+++++++++++++++++++++++++++++++++++++++++

The following variables must be informed when running the ``attach-ebs`` action (via ``extra`` parameter). Only one EBS can be mounted per instance.

..  list-table.. code-block:: none Common-commands ``run-script`` action variables
    :header-rows: 1

    *   - **Name**
        - **Type**
        - **Description**

    *   - ``ebs_volume_id``
        - string
        - ID of the volume to be mounted

    *   - ``ebs_device_name``
        - string
        - Name ofthe device to be mounted (e.g. ``/dev/sdf``)

    *   - ``ebs_delete_upon_termination`` (optional)
        - boolean (yes or no)
        - Delete EBS volume when instance is terminated? (default: yes)

Examples of the group ``attach-ebs`` action is showed below:

.. code-block:: none

    clapp group action ec2-common attach-ebs --nodes node-2 --extra ebs_device_name="/dev/sdf" ebs_volume_id="vol-0c4b1c38682bd9903"

The above example attach the EBS volume ``vol-0c4b1c38682bd9903`` on ``node-2`` in the ``/dev/sdf`` (note, you must format and mount the volume yet)


EC2 EFS
----------

This group setup and mount an network EFS filesystem on AWS provider.

The actions for the group is listed below (the ``setup`` action is automatically executed when the node is added to the group).
No hosts are needed for this group.


..  list-table.. code-block:: none EC2 EFS group actions
    :header-rows: 1

    *   - **Name**
        - **Description**

    *   - ``setup``
        - Install nfs client and mount EC2 file system

    *   - ``umount``
        - Umount EC2 File System


Setup action variables
++++++++++++++++++++++++++++

The following variables must be informed when running the ``setup`` action (via ``extra`` parameter)

..  list-table.. code-block:: none EC2 EFS ``setup`` action variables
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


An example of the command would be:

.. code-block:: none

    clapp group add ec2-efs node-0 --extra efs_mount_point="/efs" user="ubuntu" group="ubuntu" mount_ip="192.168.0.1" mount_permissions="0644"

The above command will install EC2 EFS filesystem on ``node-0`` and mount the EFS Filesystem from ``192.168.0.1`` it at ``/efs`` with ``0644`` permissions (read-write for user and read-only for others).



Umount action variables
++++++++++++++++++++++++++++

The following variables must be informed when running the ``umount`` action (via ``extra`` parameter)

..  list-table.. code-block:: none EC2 EFS ``umount`` action variables
    :header-rows: 1

    *   - **Name**
        - **Type**
        - **Description**

    *   - ``efs_mount_point``
        - path
        - Directory path where the filesystem will be unmounted


An example of the command would be:

.. code-block:: none

    clapp group action ec2-efs umount --nodes node-0 --extra efs_mount_point="/efs"

The above command will unmount EC2 EFS filesystem from ``node-0``


Docker
----------

This group installs docker-ce in debian and red-hat based systems

The actions for the group is listed below (the ``setup`` action is automatically executed when the node is added to the group).
No hosts are needed for this group.


..  list-table.. code-block:: none Docker group
    :header-rows: 1

    *   - **Name**
        - **Description**

    *   - ``setup``
        - Install docker-ce and start the service


No additional variables is needed for the group
