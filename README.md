# :clap: CLAP :clap:
CLoud Application Platform provides a interface to manage, interact and deploy HPC applications hosted in different cloud provieders.
CLAP is based in the [elasticluster](https://github.com/elasticluster/elasticluster) project, a tool that allows automated setup of compute clusters
(MPI, Spark/Hadoop, etc) and their management. CLAP extend the project by allowing a simplified interface to interact with the compute nodes.
Some of the features are:
* YAML-Style configuration files to define nodes, logins and cloud configurations
* User-friendly interface to create, setup, manage, interact and stop multiple computing nodes on different cloud providers at the same time
* Group system to easily perform actions in different heterogeneous nodes via [Ansible](https://ansible.com/) playbooks
* Easy-to-use python API

---

## Installation
1. Clone the repository with 
> git clone https://github.com/lmcad-unicamp/CLAP.git clap  

2. Enter in clap directory with 
> cd clap   

3. Set the install script to execute with `chmod` and run the script!
> `chmod +x install.sh`    
> `./install.sh`  

4. To use `clap`, you will need to activate the virtual-env. In the `clap` root directory run:
> source clap-env/bin/activate   

5. Try `clap`, via the CLI interface:
> clapp -vv --show-all-help   

---

## Basic configuration setup
In order to create compute nodes and interact with them, you will need create configurations about the cloud provider, the login and the desired instances. 
By default, CLAP holds all of it information inside the `~/.clap` directory and the `providers.yaml`, `logins.yaml` and `instances.yaml` files inside the `~/.clap/configs/` directory provide configurations about the cloud provider, the login and the instance templates, in the [YAML](https://yaml.org/) file format, respectively.

### Cloud provider configuration

Let's setup a computing node in the AWS cloud:

The cloud section defines all properties needed to connect to a specific cloud provider. To create a new cloud configuration edit the `~/.clap/configs/providers.yaml` file appending a new item as bellow. Replace some fields with your desired information:
>   
    aws-east-1-config:                              # Name of the provider config (provider ID) 
        provider: aws                               # Provider (currently only aws)
        access_keyfile: ec2_access_key.pub          # Name of the file in the ~/.clap/private/ directory containing the AWS access key ID 
        secret_access_keyfile: ec2_access_key.pem   # Name of the file in the ~/.clap/private directory containing the AWS Secret Access Key (access ID)
        url: https://ec2.us-east-1.amazonaws.com    # URL of the EC2 endpoint (usually something like this one...) 
        region: us-east-1                           # The availability zone you want to use

Note that key files must be in `~/.clap/private/` directory with `400` permission (use the `chmod 400` command to set the read-only permission). So several cloud configurations can be added just appending a new item in the file (with different provider ID). The key file must only contain the key string.

### Login configuration

The login contains information on how to access the instances started on the cloud. To create a new login configuration edit the `~/.clap/configs/logins.yaml` file appending a new item as bellow. Replace some fields with your desired information:
>   
    ubuntu-login:                                       # Name of the login config (login ID)
        user: ubuntu                                    # Login name used to SSH into the virtual machine
        keypair_name: key_us_east_1                     # Name of the keypair to use on the cloud provider
        keypair_public_file: key_us_east_1.pub          # Name of the file in the ~/.clap/private directory containing the RSA/DSA public key corresponding to the private key file
        keypair_private_file: key_us_east_1.pem         # Name of the file in the ~/.clap/private directory containing a valid SSH private key to be used to connect to the virtual machine. 
        sudo: true                                      # True if the sudo_user can execute commands as root by running the sudo command
        sudo_user: root                                 # Optional login name of the super user (default is root)

For AWS users, the public `user_key_public` can be obtained with the command `ssh-keygen -y -f /path_to_key_pair/my-key-pair.pem` (where `my-key_pair.pem` is the private SSH key. See [AWS Keypair Documentation](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-key-pairs.html#retrieving-the-public-key) for more details). So several login configurations can be added just appending a new item in the file (with different login ID). 


### Instances templates configuration

To start computing nodes, you must first setup some instance templates. The template contains information about the VM to start, including the flavor (instance type, e.g. t2.micro on EC2 provider), security group information, AMI used, the disk size and others. To create a new instance template edit the `~/.clap/configs/instances.yaml` file appending a new item as bellow. Replace some fields with your desired information:

>   
    ubuntu-instance-aws                     # Name of the instance template (instance ID)
        provider: aws-east-1-config         # Cloud configuration name (provider ID)
        login: ubuntu-login                 # Login configuration name (login ID)  
        flavor: t2.medium                   # The VM "size" to use. Different cloud providers call it differently: could be "instance type", "instance size" or "flavor".
        image_id: ami-07d0cf3af28718ef8     # Disk image ID to use in the VM. Amazon EC2 uses IDs like ami-123456
        security_group: xxx-secgroup        # (OPTIONAL) Name of security group to use when starting the instance
        # boot_disk_size: 10                # (OPTIONAL) Size of the instance’s root filesystem volume, in Gibibytes (GiB)                  
        # boot_disk_device: /dev/sda1       # (OPTIONAL) Device name of the instance’s root file system in the block device mapping
        # boot_disk_type: gp2               # (OPTIONAL) Root filesystem volume storage type, one of gp2 (general purpose SSD), io1 (provisioned IOPS SSD), or standard (the default).
        # placement_group: XXX              # (OPTIONAL) Placement group to enable low-latency networking between compute nodes
        # image_userdata: '...'             # (OPTIONAL) Shell script to be executed (as root) when the machine starts.
        # network_ids:                      # (OPTIONAL) List of network or subnet IDs the nodes of the cluster will be connected to
        # - network example id 1
        # - network example id 2
---
**NOTE**

* On Amazon EC2, the "default" security group only allows network communication among hosts in the group and does not allow SSH connections from the outside. This will make ElastiCluster fail as it cannot connect to the cluster nodes (see, e.g., issue [#490](https://github.com/gc3-uzh-ch/elasticluster/issues/490))). You will need to add rules to the "default" security group (or create a new one and use that) such that the SSH connections from the network where you run CLAP are allowed.

* See [block device mapping docs](http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/block-device-mapping-concepts.html) for more information if you are using the `boot_disk_device` key in the configuration.

* See [Root filesystem volume storage type](http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/EBSVolumeTypes.html) for more information if you are using the `boot_disk_type` key in the configuration.

* See [placement groups](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/placement-groups.html) for more information if you are using the `placement_group` key in the configuration.

* The `image_user_data` key in the configuration execute a shell script before CLAP even gets a chance to connect to the VM.

---

---
## Working with nodes

CLAP has several commands, you can use
> clapp -v --show-all   

command to get information about all available commands. Alternatively you can use `--help` in each command to see the features. The `-v` parameter can always be used, increasing he verbosity level of CLAP. `-vv` allows showing DEBUG messages.


To list the nodes in the system, you can use the command:
> clapp node list

To instantiate one node based on a instance configuration defined in the `instances.yaml` file, you can use the command:
> clapp -v node start ubuntu-instance-aws

Where the `ubuntu-instance-aws` is the instance ID defined in the `instances.yaml` file. To launch more than one machine with the same instance ID, you can put the desired number after the instance ID preceded by an `:`, such as:
> clapp -v node start ubuntu-instance-aws:4

The above command instantiates 4 `ubuntu-instance-aws` machines in a row! Once instantiate, CLAP will try to login (via SSH) with the login information provided. The machine is considered instantiated when the SSH connection is performed successfully. Machines instantiated that cannot perform SSH in a timeout (600 seconds) are automatically stopped.

You can also instantiate different machines in a row using the same command, but appending more instance IDs to it:
> clapp -v node start ubuntu-instance-aws:2 example-instance-aws:2

The above command instantiates 2 `ubuntu-instance-aws` machines and 2 `example-instance-aws` machines in a row! 

---
**Note**
 
 If the message below appears, don't worry, just ignore it.
> [ERROR] Thread-XXX: Apparently, Amazon does not compute the RSA key fingerprint as we do! We cannot check if the uploaded keypair is correct!
---
 
If everything went well after starting nodes, it can be listed with the command:
> clapp node list

Getting a similar example output:
> *  Node(id=\`node-0\`, instance_type=\`type-b\`, status=\`reachable\`, provider_id: \`aws-config-1\`, connection_ip=\`54.89.130.104\`, groups=\`\`, update_time=\`2020-02-09 12:16:05.814441\`)


Or more detailed information about a node can be obtained with the command:
> clapp -v node show node-0

where `node-0` must be replaced by the id of the instantiated node (shown with the `node list` command).

---
**Note**
 
**For now**, nodes with no connection ip (shown with the `node list` command as `None`) should be stopped, as no successfully SSH connection was performed by CLAP.

---

You can check if the nodes are alive with the command:
> clapp node alive node-0 ...


And the `stop` command (as bellow) can be used to **terminate** an running instance (in AWS, stop/resume instance is not supported yet, the nodes are terminated with this command)
> clapp -v node stop node-0


Finally, you can execute a Ansible playbook in nodes, using the `node playbook` command or execute a direct ssh command with `node execute` command. Also you can obtain a shell (via SSH) to the node with the `node connect` command.

---

## Working with groups

CLAP provides a simple way to execute commands in several nodes in a row using the concept of groups powered by [Ansible playbooks](https://docs.ansible.com/ansible/latest/user_guide/playbooks.html). Playbooks can be used to manage configurations of and deployments to remote machines.

### CLAP group files
By default CLAP groups are stored in the `~/.clap/groups/` directory, where each subdirectory inside this one represent a single group. Inside each group directory there must be one `__init__.py` file, describing the actions that can be performed with nodes of this group. An example of this `__init__.py` file have the following format (a python dictionary):

>    
    actions = {
        'setup': ['example-setup.yml'],                     # For 'setup' action, execute the example-setup.yml Ansible playbook
        'copy-files': ['copy-files.yml'],                   # For 'copy-files' action, execute the copy-files.yml Ansible playbook
        'action-x': ['x1.yml', 'x2.yml']                    # For 'action-x' action, execute the 'x1.yml' and the 'x2.yml' Ansible playbook in the nodes
    }
    
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


## CLAP API

See example notebooks and documentation

## CLAP Modules

See modules

## Troubleshooting

* The error below may occur when instance is not accessible via SSH. You can wait to instance become up or stop it.
> MainThread: AttributeError: 'NoneType' object has no attribute 'get_transport'

* For now, nodes with no connection ip (shown with the `node list` command with ip as `None`) should be stopped, as no successfully SSH connection was performed by CLAP.

* For AWS provider, stop/resume instances is not supported yet. You may wish to create a snapshot

* Hosts in ansible commands are not suported **yet**. For now, use **hosts: all** and put different roles in different playbooks

* The `node connect` command uses an old tty API and commands may be slow **yet**.

* Regular expressions to select nodes are not suported **yet**

* CLAP is not portable yet. For now, configurations stills depends on local information
