==========================
Groups shared with CLAP
==========================

Here are some groups shared with CLAP:


EC2 EFS
====================

This group setup and mount an network EFS filesystem on AWS provider.

The actions for the group is listed below (the ``setup`` action is automatically executed when the node is added to the group).
No hosts are needed for this group.


..  list-table:: EC2 EFS group
    :header-rows: 1

    *   - **Name**
        - **Description**

    *   - ``setup``
        - Install nfs client and mount EC2 file system

    *   - ``umount``
        - Umount EC2 File System

---------------------------
Setup action variables
---------------------------

The following variables must be informed when running the ``setup`` action (via ``extra`` parameter)

..  list-table:: EC2 EFS ``setup`` action variables
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

::

    clapp group add ec2-efs node-0 --extra efs_mount_point="/efs" user="ubuntu" group="ubuntu" mount_ip="192.168.0.1" mount_permissions="0644"

The above command will install and mount EC2 EFS filesystem on ``node-0``


---------------------------
Umount action variables
---------------------------

The following variables must be informed when running the ``umount`` action (via ``extra`` parameter)

..  list-table:: EC2 EFS ``umount`` action variables
    :header-rows: 1

    *   - **Name**
        - **Type**
        - **Description**

    *   - ``efs_mount_point``
        - path
        - Directory path where the filesystem will be unmounted


An example of the command would be:

::

    clapp group action ec2-efs umount --nodes node-0 --extra efs_mount_point="/efs"

The above command will unmount EC2 EFS filesystem from ``node-0``




Docker
====================

This group installs docker-ce in debian and red-hat based systems

The actions for the group is listed below (the ``setup`` action is automatically executed when the node is added to the group).
No hosts are needed for this group.


..  list-table:: Docker group
    :header-rows: 1

    *   - **Name**
        - **Description**

    *   - ``setup``
        - Install docker-ce and start the service


No additional variables is needed for the group
