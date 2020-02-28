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

1. Install requeriment packages
    > gcc g++ git libc6-dev libffi-dev libssl-dev python3-dev virtualenv python3 python3-pip

2. Clone CLAP repository
    > git clone https://github.com/lmcad-unicamp/CLAP.git clap  

3. Enter in clap directory with 
    > cd clap   

4. Set the install script to execute with `chmod` and run the script!
    > `chmod +x install.sh`    
    > `./install.sh`  

5. To use `clap`, you will need to activate the virtual-env. In the `clap` root directory run:
    > source clap-env/bin/activate   

6. Try `clap`, via the CLI interface:
    > clapp -vv --show-all-help   

7. In the CLAP folder, go to the folder `docs/build/html/` and open `index.html` (in browser) for more information of the configuration and usage

---