import argparse


from typing import List

from clap.common.module import AbstractParser
from clap.common.utils import log, path_extend, float_time_to_string
from .module import *



class MpiParamountParser(AbstractParser):
    def add_parser(self, commands_parser: argparse._SubParsersAction):
        # cluster start commands 
        # start
        paramount_subcom_parser = commands_parser.add_parser('cluster-from-nodes', help='Start a paramount cluster from the node list')
 
        paramount_subcom_parser.add_argument('nodes', action='store', nargs='+',
                help='List with the id of the nodes: node-01, node-02...')
       
        paramount_subcom_parser.set_defaults(func=self.start_paramount_cluster)




        ## Start paramount cluster from instance
        paramount_subcom_parser = commands_parser.add_parser('cluster-from-instances', help='Given an instance type(defined in instance.yml) and a number \
           this command will create a number of nodes matching the instance and add them to a new paramount cluster. \
               ')

        paramount_subcom_parser.add_argument('--desc', action='store', nargs='?',
                help='List with the instance:number separeted by spaces (type-a:10 type-b:15 ...')        

        paramount_subcom_parser.add_argument('nodes', action='store', metavar='node_type:num', nargs='+',
                help='Nodes to be initialized of the form instance:number ')
       

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
        paramount_subcom_parser = commands_parser.add_parser('compile-script', help='Compile a job, if no sub_path is specified the script'
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


        #Running script
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

        paramount_subcom_parser.set_defaults(func=self.run_script_handler)


        #Generate host
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
        paramount_subcom_parser.set_defaults(func=self.generate_host_handler)




    def start_paramount_cluster(self, namespace: argparse.Namespace ):
        #TODO: decidi começar pela start em que cria as intancias,
        #  pois é compativel com o modulo do otavio
        _nodes = namespace.nodes
        _desc = namespace.desc

        for _nodeTemplate in _nodes:
            _splitted = _nodeTemplate.split(':')
            if _splitted.__len__() != 2:
                
                raise Exception("Plese insert in the type:number format")
            try:
                val = int(_splitted[1])
            except ValueError as e:
                log.error(e)
                log.error("The size must be a list o integers")


        _paramount_cluster = create_paramount(nodes=_nodes,descr=_desc)
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
        #TODO: Validate input?
        setup_paramount_cluster(paramount_id=namespace.id,
                                mount_ip=namespace.mount_ip,
                                skip_mpi=namespace.skip_mpi,
                                no_instance_key=namespace.no_instance_key)
        return

    def new_job_handler(self, namespace: argparse.Namespace):
        new_job_from_cluster(namespace.id, name= namespace.job_name)

    def list_jobs_handler(self, namespace: argparse.Namespace):
        _jobs = list_jobs()
        print("Current mpi-paramount clusters are: \n")
        for _job  in _jobs:
            print('* ' + str(_job))
        return


    def push_files_handler(self, namespace: argparse.Namespace):
        _job_id = namespace.id
        _src = namespace.src
        push_files(job_id=_job_id, src= _src)

    def compile_script_handler(self, namespace: argparse.Namespace):
        _job_id = namespace.id
        _script_path = namespace.script
        _subpath = namespace.sub_path
        compile_script(job_id=_job_id, script=_script_path, subpath=_subpath)


    def run_script_handler(self, namespace: argparse.Namespace):
        _job_id = namespace.id
        _script_path = namespace.script
        _subpath = namespace.sub_path
        run_script(job_id=_job_id, script=_script_path, subpath=_subpath)


    def generate_host_handler(self, namespace: argparse.Namespace):
        _job_id = namespace.id
        _file_name = namespace.file_name
        _subpath = namespace.sub_path
        generate_hosts(job_id=_job_id, _file_name=_file_name, subpath=_subpath)