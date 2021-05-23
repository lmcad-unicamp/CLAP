.. _configuration:

============================
Basic Configuration Setup
============================

In order to create compute nodes and interact with them you will need provide
some information about how to connect to the cloud provider
(:ref:`providers configuration <cloud configuration>`), how to the login into
the machines (:ref:`logins configuration <login configuration>`) and details
about the cloud's virtual machines that can be used (:ref:`instances configuration <instance configuration>`).
The following sections will show how to configure these sections and the valid
values for each one. All configuration files use the
`YAML File Format <https://yaml.org/>`_ as default format.


.. note::

    YAML use spaces instead of tabs. Be careful to do not messing up!

.. _cloud configuration:

Cloud Provider Configuration
-------------------------------

The ``~/.clap/configs/providers.yaml`` file defines all properties needed to connect
to a specific cloud provider, such as the region, IAM access keys, among others.
In this file you can define multiple provider configurations that is used by
other configurations. An example ``providers.yaml`` file is shown below.

.. code-block:: yaml

    aws-east-1-config:                              # Name of the provider configuration ID
        provider: aws                               # Provider (currently only 'aws')
        access_keyfile: ec2_access_key.pub          # Name of the file in the ~/.clap/private/ directory containing the IAM AWS access key ID
        secret_access_keyfile: ec2_access_key.pem   # Name of the file in the ~/.clap/private directory containing the IAM AWS Secret Access Key (access ID)
        region: us-east-1                           # The availability zone you want to use

    my-cool-config-2:
        provider: aws
        access_keyfile: acesss.pub
        secret_access_keyfile: private_access.pem
        region: us-east-2
    
    my-cool-config-3:
        provider: aws
        ...

The YAML dictionary keys (``aws-east-1-config``, ``my-cool-config-2`` and
``my-cool-config-3`` in the above example) are the provider configuration names
(provider IDs) that can be referenced in other files. The values for each provider ID
are specific cloud provider information. You can define as many provider
configurations as you want just adding a new provider ID and the values for it.
Note that each provider ID must be unique. The valid values for a provider
configuration showed in the table below.

..  list-table:: Valid cloud provider configuration key and values
    :header-rows: 1

    *   - **Name**
        - **Valid Values or Type**
        - **Description**

    *   - **provider**
        - **valid values**: aws
        - Name of the cloud provider to be used

    *   - **access_keyfile**
        - **type**: string
        - **Name of the file** containing the AWS access key ID. The file must be placed at ``~/.clap/private`` and this field must be filled only with the name of file, not the whole path.

    *   - **secret_access_keyfile**
        - **type**: string
        - **Name of the file** containing the AWS Secret Access Key (access ID). The file must be placed at ``~/.clap/private`` and this field must be filled only with the name of file, not the whole path.

    *   - **region**
        - **type**: string
        - The availability zone you want to use (e.g. ``us-east-1``)

    *   - **vpc (optional)**
        - **type**: string
        - Name or ID of the AWS Virtual Private Cloud to provision resources in.


.. note::
    For CLAP, **all keys** must be stored at ``~/.clap/private/`` directory with
    400 permission (use the ``chmod 400`` command to set the read-only permission).


Note for AWS provider
++++++++++++++++++++++++

IAM Access keys consist of two parts: an access key ID (for example, ``AKIAIOSFODNN7EXAMPLE``)
and a secret access key (for example, ``wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY``).
These keys are **required** and is used to connect to the aws provider via third-party
applications (see the `AWS Access Keys documentation <https://docs.aws.amazon.com/general/latest/gr/aws-sec-cred-types.html#access-keys-and-secret-access-keys>`_ for more information).
So you must place your access key ID string inside a file in the ``~/.clap/private/``.
For instance, copy and paste access key ID in a file and save at ``~/.clap/private/ec2_access_key.pub``,
or other filename and the same for the secret access key.


.. _login configuration:

Login Configuration
-------------------------------

The ``~/.clap/configs/logins.yaml`` defines all properties needed to access a
started virtual machine via SSH, such as login user name, SSH key file used to
access, etc. In this file you can define multiple login information that is used
by other configurations. An example ``logins.yaml`` file is shown below.

.. code-block:: yaml

    ubuntu-login:                                       # Name of the login config (Login ID)
        user: ubuntu                                    # Login name used to SSH into the virtual machine
        keypair_name: key_us_east_1                     # Name of the keypair to use on the cloud provider
        keypair_public_file: key_us_east_1.pub          # Name of the file in the ~/.clap/private directory containing the RSA/DSA public key corresponding to the private key file
        keypair_private_file: key_us_east_1.pem         # Name of the file in the ~/.clap/private directory containing a valid SSH private key to be used to connect to the virtual machine.
        sudo: true                                      # True if the sudo_user can execute commands as root by running the sudo command
        sudo_user: root                                 # (OPTIONAL) Login name of the super user (default is root)

    example-centos:
        user: centos
        ...


The YAML dictionary keys (``ubuntu-login`` and ``example-centos`` in the above example)
are login's configuration name (also called login ID). The values are the specific
information about that configuration. You can define as many login configurations
as you want just adding a new login ID and the values for it. Note that each login
ID must be unique. The valid values for a login configuration are:


..  list-table:: Valid login configuration key and values
    :header-rows: 1

    *   - **Name**
        - **Values/Type**
        - **Description**

    *   - **user**
        - **type**: string
        - Name of the user used to perform SSH into the virtual machine.

    *   - **keypair_name**
        - **type**: string
        - Name of the keypair used on the cloud provider.

    *   - **keypair_public_file**
        - **type**: string
        - Name of the file in the ``~/.clap/private`` directory containing the RSA/DSA public key corresponding to the private key file.

    *   - **keypair_private_file**
        - **type**: string
        - Name of the file in the ``~/.clap/private`` directory containing a valid SSH private key to be used to connect to the virtual machine.

    *   - **sudo**
        - **type**: boolean
        - True if the sudo user can execute commands as root by running the sudo command.

    *   - **sudo_user (optional)**
        - **type**: string
        - Optional login name of the super user (default is root)

The keypair is used to login to the machine without password (and perform SSH).

Note for AWS users
++++++++++++++++++++++++

For AWS users, the keypair can be generated in the menu: ``EC2 --> Network & Security --> Key Pairs``.
A keypair can be created using the ``create key pair`` button providing an unique
keypair name (this name is used in the ``keypair_name`` field of the login configuration).
When a keypair is created, a private key file is generated to download. This is
the **private key file** (used to login to the instances).

For CLAP, all key files must be placed in the ``~/.clap/private/`` directory with
400 permission. In the **keypair_private_file** login configuration field, the name
of the private key file inside the ``~/.clap/private/`` must be inserted (e.g.
**only** the file name: ``key_us_east_1.pem.pem`` and not ``~/.clap/private/key_us_east_1.pem.pem``)

If you have a private key, the public key can be obtained with the command
``ssh-keygen -y -f /path_to_key_pair/my-key-pair.pem`` (where ``my-key_pair.pem`` is
the private key file. See `AWS Keypair Documentation <https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-key-pairs.html#retrieving-the-public-key>`_ for more details).
The generated public key must be saved to a file and placed at ``~/.clap/private/``
directory with 400 permission. So, in the ``keypair_public_file`` field of the
login configuration, the name of the public key file must be inserted.


.. _instance configuration:

Instance Templates Configuration
----------------------------------

To start virtual machines in a cloud, you must first setup some instance templates
in the ``~/.clap/configs/instances.yaml`` file. The template contains information
about the virtual machine to start, including its flavor (i.e. instance type,
for instance ``t2.micro`` on AWS clouds), security group information, AMI used,
the disk size and others. The instance template references the provider configuration
and login configuration by its ID. An example of ``instances.yaml`` file is shown below.

.. code-block:: yaml

    ubuntu-instance-aws:                    # Name of the instance template (instance template ID)
        provider: aws-east-1-config         # Provider configuration ID
        login: ubuntu-login                 # Login configuration ID
        flavor: t2.medium                   # The VM "size" to use. Different cloud providers call it differently: could be "instance type", "instance size" or "flavor".
        image_id: ami-07d0cf3af28718ef8     # Disk image ID to use in the VM. Amazon EC2 uses IDs like ami-123456
        security_group: xxx-secgroup        # Name of security group to use when starting the instance
        boot_disk_size: 10                  # (OPTIONAL) Size of the instance’s root filesystem volume, in Gibibytes (GiB)
        boot_disk_device: /dev/sda1         # (OPTIONAL) Device name of the instance’s root file system in the block device mapping
        boot_disk_type: gp2                 # (OPTIONAL) Root filesystem volume storage type, one of gp2 (general purpose SSD), io1 (provisioned IOPS SSD), or standard (the default).
        placement_group: XXX                # (OPTIONAL) Placement group to enable low-latency networking between compute nodes
        image_userdata: '...'               # (OPTIONAL) Shell script to be executed (as root) when the machine starts.
        network_ids:  subnet-abcdfefxx      # (OPTIONAL) Subnet IDs the nodes will be connected to

    instance-t2small-us-east-1:
        provider: aws-east-1-config
        ...


The YAML dictionary keys (``ubuntu-instance-aws`` and ``instance-t2small-us-east-1``
in the above example) are the name of the instance templates (also called instance
template ID) and the values are the specific information about that instance template.
You can define as many instance templates configurations as you want just adding
a new instance template ID and the values for it. Note that each instance template
ID must be unique. Commands will use the instance template ID to start instances
based on this information. The valid values for the instance templates are:

..  list-table:: Valid instance template key and values
    :header-rows: 1

    *   - **Name**
        - **Values/Type**
        - **Description**

    *   - **provider**
        - **type**: string
        - The ID of the provider configuration to be used for this instance. The ID must match the provider ID at ``providers.yaml``

    *   - **login**
        - **type**: string
        - The ID of the login configuration to be used for this instance. The ID must match the login ID at ``logins.yaml``

    *   - **flavor**
        - **type**: string
        - The provider instance type to use (e.g. ``t2.micro``, ``c5.large``, etc)

    *   - **image_id**
        - **type**: string
        - Disk image ID to use in the VM (basically the OS to be used). Amazon EC2 uses IDs like ``ami-123456``. Note that the image_id is dependent of the provider region and a error may be raised if an invalid AMI id is specified

    *   - **security_group**
        - **type**: string
        - Name of security group to use when starting the instance

    *   - **boot_disk_size (optional)**
        - **type**: string
        - Size of the instance’s root filesystem volume, in Gibibytes (GiB)

    *   - **boot_disk_device (optional)**
        - **type**: string
        - Device name of the instance’s root file system in the block device mapping. For AWS, see `block device mapping docs <http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/block-device-mapping-concepts.html>`_ for more information

    *   - **boot_disk_type (optional)**
        - **type**: string
        - Root filesystem volume storage type, one of gp2 (general purpose SSD), io1 (provisioned IOPS SSD), or standard (default). See `Root filesystem volume storage type <http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/EBSVolumeTypes.html>`_ for more information

    *   - **placement_group (optional)**
        - **type**: string
        - Placement group to enable low-latency networking between compute nodes. See `placement groups <https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/placement-groups.html>`_ for more information

    *   - **network_ids (optional)**
        - **type**: string
        - Subnet ID that the nodes of the cluster will be connected to
