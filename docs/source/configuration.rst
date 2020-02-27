..........................
Basic Configuration Setup
..........................

In order to create compute nodes and interact with them, you will need provide some information about the cloud provider, the login used to connect to the instances and the desired instances.
By default, CLAP holds all of it information inside the ``~/.clap`` directory (``~`` stands for the user home directory). The minimal structure of ``~/.clap`` directory is shown bellow:

::

    ~/
    └── .clap/
        ├── configs/
        │   ├── instances.yaml
        │   ├── logins.yaml
        │   └── providers.yaml
        ├── groups/
        │   ├── groups/
        │   ├── group_vars/
        │   │   └── all.yml
        │   ├── main.yml
        │   └── roles/
        ├── modules/
        ├── private/
        └── storage/
            ├── clusters.d/
            └── platform.json


- The ``~/.clap/configs/providers.yaml`` `YAML <https://yaml.org/>`_ file inside the ``~/.clap/configs`` directory holds the information about the cloud provider and how to connect to it.

- The ``~/.clap/configs/logins.yaml`` file holds information about how to connect to an instance (e.g. login user, keyfile, etc)

- The ``~/.clap/configs/instances.yaml`` holds the information about the instances to launch, i.e. the instance templates.

- The ``groups`` directory store groups file and actions, used to perform action in several nodes. More detailed information about groups and actions will be presented at :doc:`groups section <groups>`

- The ``modules`` directory store module files, used to extend clap CLI application via the     troubleshooting. More detailed information about modules will be presented at :doc:`modules section <modules>`

- The ``private`` stores keys and passwords files used to connect to the cloud provider and to the instance itself. Every key/secret files needed in the configuration sections must be placed inside this directory

- The ``storage`` directory store metadata information used by ``clap`` (this directory may also contain sensitive information)

To launch an instance and use the CLAP capabilities, you will first need to configure an instance template.


# (3 steps= Cloud, Login, Instance) For CLAP, instance templates must be defined in the ``instances.yaml`` file.

In the following sections, it will be shown how to configure the above files used to launch instances and all the valid information that can be used in it.

=============================
Cloud provider configuration
=============================

The ``~/.clap/configs/providers.yaml`` file defines all properties needed to connect to a specific cloud provider.
An example ``providers.yaml`` file is shown bellow (in YAML format).

::

    aws-east-1-config:                              # Name of the provider config (Provider ID)
        provider: aws                               # Provider (currently only aws)
        access_keyfile: ec2_access_key.pub          # Name of the file in the ~/.clap/private/ directory containing the AWS access key ID
        secret_access_keyfile: ec2_access_key.pem   # Name of the file in the ~/.clap/private directory containing the AWS Secret Access Key (access ID)
        url: https://ec2.us-east-1.amazonaws.com    # URL of the EC2 endpoint (usually something like this one...)
        region: us-east-1                           # The availability zone you want to use

    my-config2:
        provider: aws
        ...

The YAML dictionary keys are the name of the provider configuration (also called provider ID, ``aws-east-1-config`` and ``my-config2`` in this example) and the values are the specific information about that configuration.
You can define as many provider configurations as you want just adding a new provider ID and the values for it. Note that each provider ID must be unique.
Other sections will refer to a provider configuration by its provider ID.
The valid values for a provider configuration are:

..  list-table:: Valid provider configuration key and values
    :header-rows: 1

    *   - **Name**
        - **Values/Type**
        - **Description**

    *   - **provider**
        - 'aws'
        - Name of the cloud provider to be used

    *   - **access_keyfile**
        - <filename>
        - Name of the file containing the AWS access key ID. The file must be at ``~/.clap/private`` (see below)

    *   - **secret_access_keyfile**
        - <filename>
        - Name of the file containing the AWS Secret Access Key (access ID). The file must be at ``~/.clap/private`` (see below)

    *   - **url**
        - <string>
        - URL of the EC2 endpoint (usually something like ``https://ec2.us-east-1.amazonaws.com``)

    *   - **region**
        - <string>
        - The availability zone you want to use (e.g. ``us-east-1``)


Access keys consist of two parts: an access key ID (for example, ``AKIAIOSFODNN7EXAMPLE``) and a secret access key (for example, ``wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY``).
These keys are **required** and is used to connect to the aws provider via third-party applications. (See the `AWS Access Keys documentation <https://docs.aws.amazon.com/general/latest/gr/aws-sec-cred-types.html#access-keys-and-secret-access-keys>`_ for more information).

For CLAP, all keys must be stored at ``~/.clap/private/`` directory with 400 permission (use the ``chmod 400`` command to set the read-only permission).
So you must place your access key ID string inside a file in the ``~/.clap/private/`` (e.g, copy and paste access key ID in a file and save at ``~/.clap/private/ec2_access_key.pub``) and the same for the secret access key.

Once the files are in the ``~/.clap/private/`` directory, the values of the ``access_keyfile`` and ``secret_access_keyfile`` keys in your provider configuration must only contain the filename, not the whole path. (e.g. **only** the file name: ``ec2_access_key.pub`` and not ``~/.clap/private/ec2_access_key.pub``)


=============================
Login provider configuration
=============================

The login contains information on how to access the instances started on the cloud via SSH. So, the section holds information about the userto perform login, the SSH keyfile to log in the machine and others.
The ``~/.clap/configs/logins.yaml`` file must be populated with desired information.
An example ``logins.yaml`` file is shown bellow (in YAML format).

::

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


The YAML dictionary keys are the name of the login configuration (also called login ID, ``ubuntu-login`` and ``example-centos`` in this example) and the values are the specific information about that configuration.
You can define as many login configurations as you want just adding a new login ID and the values for it. Note that each login ID must be unique.
Other sections will refer to a login configuration by its provider ID.
The valid values for a login configuration are:


..  list-table:: Valid login configuration key and values
    :header-rows: 1

    *   - **Name**
        - **Values/Type**
        - **Description**

    *   - **user**
        - <string>
        - Name of the user used to perform SSH into the virtual machine

    *   - **keypair_name**
        - <string>
        - Name of the keypair to use on the cloud provider (see more below)

    *   - **keypair_public_file**
        - <filename>
        - Name of the file in the ``~/.clap/private`` directory containing the RSA/DSA public key corresponding to the private key file

    *   - **keypair_private_file**
        - <filename>
        - Name of the file in the ``~/.clap/private`` directory containing a valid SSH private key to be used to connect to the virtual machine

    *   - **sudo**
        - <boolean>
        - True if the sudo user can execute commands as root by running the sudo command

    *   - **sudo_user (optional)**
        - <string>
        - Optional login name of the super user (default is root)

The keypair is used to login to the machine without password (and perform SSH). For AWS users, the keypair can be generated in the menu: ``EC2 --> Network & Security --> Key Pairs``.
A keypair can be created using the ``create key pair`` button providing an unique keypair name (this name is used in the ``keypair_name`` field of the login configuration).
When a keypair is created, a private key file is generated to download. This is the **private key file** (used to login to the instances).

For CLAP, all key files must be placed in the ``~/.clap/private/`` directory with 400 permission.
In the **keypair_private_file** login configuration field, the name of the private key file inside the ``~/.clap/private/`` must be inserted (e.g. **only** the file name: ``key_us_east_1.pem.pem`` and not ``~/.clap/private/key_us_east_1.pem.pem``)

Having the private key, the public key can be obtained with the command ``ssh-keygen -y -f /path_to_key_pair/my-key-pair.pem`` (where ``my-key_pair.pem`` is the private key file. See `AWS Keypair Documentation <https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-key-pairs.html#retrieving-the-public-key>`_ for more details).
The generated public key must be saved to a file and placed at ``~/.clap/private/`` directory with 400 permission. So, in the ``keypair_public_file`` field of the login configuration, the name of the public key file must be inserted.

=================================
Instance templates configuration
=================================

To start virtual machines in a cloud, you must first setup some instance templates in the ``~/.clap/configs/instances.yaml`` file.
The template contains information about the virtual machine to start, including the flavor (instance type, e.g. t2.micro on EC2 provider), security group information, AMI used, the disk size and others.
The instance template references the provider configuration and login configuration by its ID.

To create a new instance template you can edit the ``~/.clap/configs/instances.yaml`` file.
An example of ``instances.yaml`` is shown bellow.

::

    ubuntu-instance-aws                     # Name of the instance template (instance template ID)
        provider: aws-east-1-config         # Provider configuration ID
        login: ubuntu-login                 # Login configuration ID
        flavor: t2.medium                   # The VM "size" to use. Different cloud providers call it differently: could be "instance type", "instance size" or "flavor".
        image_id: ami-07d0cf3af28718ef8     # Disk image ID to use in the VM. Amazon EC2 uses IDs like ami-123456
        security_group: xxx-secgroup        # (OPTIONAL) Name of security group to use when starting the instance
        boot_disk_size: 10                  # (OPTIONAL) Size of the instance’s root filesystem volume, in Gibibytes (GiB)
        boot_disk_device: /dev/sda1         # (OPTIONAL) Device name of the instance’s root file system in the block device mapping
        boot_disk_type: gp2                 # (OPTIONAL) Root filesystem volume storage type, one of gp2 (general purpose SSD), io1 (provisioned IOPS SSD), or standard (the default).
        placement_group: XXX                # (OPTIONAL) Placement group to enable low-latency networking between compute nodes
        image_userdata: '...'               # (OPTIONAL) Shell script to be executed (as root) when the machine starts.
        network_ids:                        # (OPTIONAL) List of network or subnet IDs the nodes will be connected to
            - eni-0c7b58d5d506d94af
            - network-example-2

    instance-t2small-us-east-1:
        provider: aws-east-1-config
        ...


The YAML dictionary keys are the name of the instance templates (also called instance template ID, ``ubuntu-instance-aws`` and ``instance-t2small-us-east-1`` in this example) and the values are the specific information about that instance template.
You can define as many instance templates configurations as you want just adding a new instance template ID and the values for it. Note that each instance template ID must be unique.
Commands will use the instance template ID to launch instances based on this information.
The valid values for the instance templates are:

..  list-table:: Valid instance template key and values
    :header-rows: 1

    *   - **Name**
        - **Values/Type**
        - **Description**

    *   - **provider**
        - <string>
        - The ID of the provider configuration to be used for this instance. The ID must match the provider ID at ``providers.yaml``

    *   - **login**
        - <string>
        - The ID of the login configuration to be used for this instance. The ID must match the login ID at ``logins.yaml``

    *   - **flavor**
        - <string>
        - The provider instance type to use (e.g. t2.micro, c5.large, etc)

    *   - **image_id**
        - <string>
        - Disk image ID to use in the VM (basically the OS to be used). Amazon EC2 uses IDs like ``ami-123456``. Note that the image_id is dependent of the provider region and a error may be raised if an invalid ami is specified

    *   - **security_group (optional)**
        - <string>
        - Name of security group to use when starting the instance. The default security group is ``default``

    *   - **boot_disk_size (optional)**
        - <string>
        - Size of the instance’s root filesystem volume, in Gibibytes (GiB)

    *   - **boot_disk_device (optional)**
        - <string>
        - Device name of the instance’s root file system in the block device mapping. For AWS, see `block device mapping docs <http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/block-device-mapping-concepts.html>`_ for more information

    *   - **boot_disk_type (optional)**
        - <string>
        - Root filesystem volume storage type, one of gp2 (general purpose SSD), io1 (provisioned IOPS SSD), or standard (default). See `Root filesystem volume storage type <http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/EBSVolumeTypes.html>`_ for more information

    *   - **placement_group (optional)**
        - <string>
        - Placement group to enable low-latency networking between compute nodes. See `placement groups <https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/placement-groups.html>`_ for more information

    *   - **image_userdata (optional)**
        - <string>
        - Shell script to be executed (as root) when the machine starts. This shell script is executed before CLAP even gets a chance to connect to the VM.

    *   - **network_ids (optional)**
        - <List of strings>
        - List of network or subnet IDs the nodes of the cluster will be connected to


On Amazon EC2, the "default" security group only allows network communication among hosts in the group and does not allow SSH connections from the outside.
This will make ElastiCluster driver to fail as it cannot connect to the cluster nodes. You will need to add rules to the "default" security group (or create a new one and use that) such that the SSH connections from the network where you run CLAP are allowed.