import argparse

from typing import List

from clap.common.module import AbstractParser
from clap.common.utils import log, path_extend, float_time_to_string
from .module import *


class MpiParamountParser(AbstractParser):
    def add_parser(self, commands_parser: argparse._SubParsersAction):
        # cluster start commands 
        # start
        # paramount_subcom_parser = commands_parser.add_parser('cluster-from-nodes', help='Start a paramount cluster from the node list')
        #
        # paramount_subcom_parser.add_argument('nodes', action='store', nargs='+',
        #         help='List with the id of the nodes: node-01, node-02...')
        #
        # paramount_subcom_parser.set_defaults(func=self.start_paramount_cluster)
        #

        ## Start paramount cluster from instance
        paramount_subcom_parser = commands_parser.add_parser('cluster-from-instances', help='Given an instance type(defined in .clap/config/instances.yaml) and a number \
           this command will create a number of nodes matching the instance and add them to a new paramount cluster. If the optional command '
                                                                                            ' --coord is set then the coordinator will be set to this specific type, else (default) a random node is selected as a coordinator" \
                                                                                                ')

        paramount_subcom_parser.add_argument('--desc', action='store', nargs='?',
                                             help='List with the instance:number separeted by spaces (type-a:10 type-b:15 ...')

        paramount_subcom_parser.add_argument('nodes', action='store', metavar='node_type:num', nargs='+',
                                             help='Nodes to be initialized of the form instance:number ')

        paramount_subcom_parser.add_argument('--coord', action='store', nargs='?',
                                             help='A string containing a type (defined in .clap/config/instances.yaml to be'
                                                  'set as a coordinator')

        paramount_subcom_parser.set_defaults(func=self.start_paramount_cluster)

        ## Listing paramount clusters
        paramount_subcom_parser = commands_parser.add_parser('list', help='List started mpi-paramount clusters')

        paramount_subcom_parser.set_defaults(func=self.list_paramount_command)

        ## Setup cluster
        paramount_subcom_parser = commands_parser.add_parser('setup', help='Given an instance type(defined in instance.yml) and a number \
            this command will create a number of nodes matching the instance and add them to a new paramount cluster. \
                ')

        paramount_subcom_parser.add_argument('id', metavar='ID', action='store',
                                             help='Mpi-paramount cluster id')

        paramount_subcom_parser.add_argument('--mount_ip', action='store', nargs='?',
                                             help='Mount ip address')

        paramount_subcom_parser.add_argument('--skip-mpi', action='store_true',
                                             help='Flag to skip mpi related package installation ')

        paramount_subcom_parser.add_argument('--no_instance_key', action='store_true',
                                             help='Flag indicating to not use the instance key (in .clap/configs/instance.yml ')

        paramount_subcom_parser.set_defaults(func=self.setup_cluster)

        ## Start a job
        paramount_subcom_parser = commands_parser.add_parser('start-job', help='Start a new job at the desired cluster \
                  ')

        paramount_subcom_parser.add_argument('id', metavar='ID', action='store',
                                             help='Mpi-paramount cluster id')

        paramount_subcom_parser.add_argument('--job_name', action='store', nargs='?',
                                             help='Optional job name')

        paramount_subcom_parser.set_defaults(func=self.new_job_handler)

        ## Listing jobs
        paramount_subcom_parser = commands_parser.add_parser('job-list', help='List started jobs')

        paramount_subcom_parser.set_defaults(func=self.list_jobs_handler)

        ## push files
        paramount_subcom_parser = commands_parser.add_parser('push-files', help='Push files to job a directory \
                  ')

        paramount_subcom_parser.add_argument('id', metavar='ID', action='store',
                                             help='Job id')

        paramount_subcom_parser.add_argument('src', action='store',
                                             help='Source folder')

        paramount_subcom_parser.set_defaults(func=self.push_files_handler)

        ## compile
        paramount_subcom_parser = commands_parser.add_parser('compile-script',
                                                             help='Compile a job, if no sub_path is specified the script'
                                                                  ' will be executed in the job root, otherwise it will be acessed in a subdirectory'
                                                                  'specified in the sub argument \
                         ')

        paramount_subcom_parser.add_argument('id', metavar='ID', action='store',
                                             help='Job id')

        paramount_subcom_parser.add_argument('script', action='store',
                                             help='Compiling script to be executed')

        paramount_subcom_parser.add_argument('--sub_path', action='store', nargs='?',
                                             help='Subdirectory inside job folder where the script should be executed, if left' \
                                                  'unspecified it will execute in the job root')

        paramount_subcom_parser.set_defaults(func=self.compile_script_handler)

        # Running script
        paramount_subcom_parser = commands_parser.add_parser('run-script',
                                                             help='Run a job, if no sub_path is specified the script'
                                                                  ' will be executed in the job root, otherwise it will be acessed in a subdirectory'
                                                                  'specified in the sub argument \
                         ')

        paramount_subcom_parser.add_argument('id', metavar='ID', action='store',
                                             help='Job id')

        paramount_subcom_parser.add_argument('script', action='store',
                                             help='Script that specifies how to run the application')

        paramount_subcom_parser.add_argument('--sub_path', action='store', nargs='?',
                                             help='Subdirectory inside job folder where the script should be executed, if left ' \
                                                  'unspecified it will execute in the job root')
        paramount_subcom_parser.add_argument('--exec_desr', action='store', nargs='?',
                                             help='Description of this specific execution (problem size, algorithm used...)')

        paramount_subcom_parser.set_defaults(func=self.run_script_handler)

        # Generate host
        paramount_subcom_parser = commands_parser.add_parser('generate-hosts',
                                                             help='Generate a hostfile containing ' \
                                                                  'all nodes from the paramount clustster')

        paramount_subcom_parser.add_argument('id', metavar='ID', action='store',
                                             help='Job id')



        paramount_subcom_parser.add_argument('--sub_path', action='store', nargs='?',
                                             help='Subdirectory inside job folder where the script should be executed, if left ' \
                                                  'unspecified it will execute in the job root')

        paramount_subcom_parser.add_argument('--file_name', action='store', nargs='?',
                                             help='What name should the file be, defaults to \'host\'')

        paramount_subcom_parser.add_argument('--mpich_style', action='store_true',
                                             help='What name should the file be, defaults to \'host\'')

        paramount_subcom_parser.set_defaults(func=self.generate_host_handler)

        # Fetch paramount  info
        paramount_subcom_parser = commands_parser.add_parser('fetch-paramount',
                                                             help='Fetch the paramount info')

        paramount_subcom_parser.add_argument('id', metavar='ID', action='store',
                                             help='Job id')

        paramount_subcom_parser.add_argument('dest', action='store',
                                             help='The directory where the logs should be saved')

        paramount_subcom_parser.set_defaults(func=self.fetch_paramount_handler)

        # Install script

        paramount_subcom_parser = commands_parser.add_parser('install-script',
                                                             help='Install a script in every node')

        paramount_subcom_parser.add_argument('id', metavar='ID', action='store',
                                             help='Job id')

        paramount_subcom_parser.add_argument('script', action='store',
                                             help='Installation script')

        paramount_subcom_parser.add_argument('--file', action='store', nargs='?',
                                             help='Files (if any) that should be passed to execute the script')

        paramount_subcom_parser.add_argument('--subpath', action='store', nargs='?',
                                             help='Subdirectory inside job folder where the script should be executed, if left ' \
                                                  'unspecified it will execute in the job root')

        paramount_subcom_parser.set_defaults(func=self.install_script_handler)

        # Run command

        paramount_subcom_parser = commands_parser.add_parser('run-command',
                                                             help='Install a script in every node')

        paramount_subcom_parser.add_argument('id', metavar='ID', action='store',
                                             help='Cluster id')

        paramount_subcom_parser.add_argument('command', action='store',
                                             help='Simple quote delimitated command')

        paramount_subcom_parser.set_defaults(func=self.run_command_handler)

        # Add nodes to existing mpi-paramount cluster

        paramount_subcom_parser = commands_parser.add_parser('add-new-nodes',
                                                             help='Given instance:number tuple this command will'
                                                                  'start these instances then add to the given mpc '
                                                                  'and perform a setup operation in a way that these nodes '
                                                                  'can be successfully added to the cluster ')

        paramount_subcom_parser.add_argument('id', metavar='ID', action='store',
                                             help='Cluster id')

        paramount_subcom_parser.add_argument('--coord', action='store',
                                             help='If set one of (or the only) node will be selected as a coordinator')

        paramount_subcom_parser.add_argument('nodes', action='store', metavar='node_type:num', nargs='+',
                                             help='Nodes to be initialized of the form instance:number ')

        paramount_subcom_parser.set_defaults(func=self.add_new_node_handler)




        paramount_subcom_parser = commands_parser.add_parser('remove-coord',
                                                             help='Given instance:number tuple this command will'
                                                                  'start these instances then add to the given mpc '
                                                                  'and perform a setup operation in a way that these nodes '
                                                                  'can be successfully added to the cluster ')

        paramount_subcom_parser.add_argument('id', metavar='ID', action='store',
                                             help='Cluster id')


        paramount_subcom_parser.set_defaults(func=self.remove_coord_handler)


    def start_paramount_cluster(self, namespace: argparse.Namespace):
        # TODO: decidi começar pela start em que cria as intancias,
        #  pois é compativel com o modulo do otavio
        _nodes = namespace.nodes
        _desc = namespace.desc
        _coord = namespace.coord


        for _nodeTemplate in _nodes:
            _splitted = _nodeTemplate.split(':')
            if _splitted.__len__() != 2:
                raise Exception("Plese insert in the type:number format")
            try:
                val = int(_splitted[1])
            except ValueError as e:
                log.error(e)
                log.error("The size must be a list o integers")


        _paramount_cluster = create_paramount(nodes=_nodes, descr=_desc, coord=_coord)
        print("MPI-Paramount cluster created: \n")
        print(_paramount_cluster)
        return

    def list_paramount_command(self, namespace: argparse.Namespace):
        _clusters = list_paramount_clusters()
        print("Current mpi-paramount clusters are: \n")
        for _cluster in _clusters:
            print('* ' + str(_cluster))
        return

    def setup_cluster(self, namespace: argparse.Namespace):
        # TODO: Validate input?
        setup_paramount_cluster(paramount_id=namespace.id,
                                mount_ip=namespace.mount_ip,
                                skip_mpi=namespace.skip_mpi,
                                no_instance_key=namespace.no_instance_key)
        return

    def new_job_handler(self, namespace: argparse.Namespace):
        new_job_from_cluster(namespace.id, job_name=namespace.job_name)

    def list_jobs_handler(self, namespace: argparse.Namespace):
        _jobs = list_jobs()
        print("Current mpi-paramount clusters are: \n")
        for _job in _jobs:
            print('* ' + str(_job))
        return

    def push_files_handler(self, namespace: argparse.Namespace):
        _job_id = namespace.id
        _src = namespace.src
        push_files(job_id=_job_id, src=_src)

    def compile_script_handler(self, namespace: argparse.Namespace):
        _job_id = namespace.id
        _script_path = namespace.script
        _subpath = namespace.sub_path
        compile_script(job_id=_job_id, script=_script_path, subpath=_subpath)

    def run_script_handler(self, namespace: argparse.Namespace):
        _job_id = namespace.id
        _script_path = namespace.script
        _subpath = namespace.sub_path
        _exec_descr = namespace.exec_desr
        run_script(job_id=_job_id, script=_script_path, subpath=_subpath, exec_descr=_exec_descr)

    def generate_host_handler(self, namespace: argparse.Namespace):
        _job_id = namespace.id
        _file_name = namespace.file_name
        _subpath = namespace.sub_path
        _mpich_style = namespace.mpich_style
        generate_hosts(job_id=_job_id, _file_name=_file_name, subpath=_subpath, mpich_style=_mpich_style)

    def fetch_paramount_handler(self, namespace: argparse.Namespace):
        _job_id = namespace.id
        _dest = namespace.dest
        fetch_job_paramount(job_id=_job_id, dest=_dest)

    def install_script_handler(self, namespace: argparse.Namespace):

        _job_id = namespace.id
        _script = namespace.script
        _file = namespace.file
        _subpath = namespace.subpath

        install_script(job_id=_job_id, script=_script, additionalFile=_file, subpath=_subpath)

    def run_command_handler(self, namespace: argparse.Namespace):
        _mpc_id = namespace.id
        _command = namespace.command

        run_command(mpc_id=_mpc_id, command=_command)

    def add_new_node_handler(self, namespace: argparse.Namespace):
        _mpc_id = namespace.id
        _coordinator = namespace.coord
        _nodes = namespace.nodes

        for _nodeTemplate in _nodes:
            _splitted = _nodeTemplate.split(':')
            if _splitted.__len__() != 2:
                raise Exception("Plese insert in the type:number format")
            try:
                val = int(_splitted[1])
            except ValueError as e:
                log.error(e)
                log.error("The size must be a list o integers")

        add_from_instances(paramount_id=_mpc_id, node_type=_nodes)

    def remove_coord_handler(self, namespace: argparse.Namespace):
        _mpc_id = namespace.id

        _newCoord = change_coordinator(_mpc_id)
        print("Coordinator successfully removed, new coordinator is `{}` ".format(_newCoord))
