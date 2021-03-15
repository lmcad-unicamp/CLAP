import argparse

from typing import List

from clap.common.module import AbstractParser
from clap.common.utils import log, path_extend, float_time_to_string
from .module import *


class MpiParamountParser(AbstractParser):
    def add_parser(self, commands_parser: argparse._SubParsersAction):
        # cluster start commands 


        ## Start paramount cluster from instance
        paramount_subcom_parser = commands_parser.add_parser('create-mcluster', help='Given an instance type(defined in .clap/config/instances.yaml) and a number \
           this command will create a number of nodes matching the instance and add them to a new Mcluster. If the optional command '
                                                                                            ' --coord is set then the coordinator will be set to this specific type, else (default) a random node is selected as a coordinator" \
                                                                                                ')

        paramount_subcom_parser.add_argument('--desc', action='store', nargs='?',
                                             help='Nickname for this cluster')

        paramount_subcom_parser.add_argument('nodes', action='store', metavar='node_type:num', nargs='+',
                                             help='Nodes to be initialized of the form instance:number ')

        paramount_subcom_parser.add_argument('--coord', action='store', nargs='?',
                                             help='A string containing a type (defined in .clap/config/instances.yaml to be '
                                                  'set as a coordinator')

        paramount_subcom_parser.set_defaults(func=self.start_paramount_cluster)

        ## Listing paramount clusters
        paramount_subcom_parser = commands_parser.add_parser('list-mclusters', help='List started clap-mpi clusters')

        paramount_subcom_parser.set_defaults(func=self.list_paramount_command)

        ## Setup cluster
        paramount_subcom_parser = commands_parser.add_parser('setup', help='Given an instance type(defined in instance.yml) and a number \
            this command will create a number of nodes matching the instance and add them to a new Mcluster. \
                ')

        paramount_subcom_parser.add_argument('id', metavar='MCLUSTERID', action='store',
                                             help='Mcluster id, or \'{}\' if the last one created (highest ID) should'
                                                  'be used'.format(Info.LAST_PARAMOUNT))

        paramount_subcom_parser.add_argument('--mount_ip', action='store', nargs='?',
                                             help='Mount ip address')

        paramount_subcom_parser.add_argument('--skip_mpi', action='store_true',
                                             help='Flag to skip mpi related package installation ')

        paramount_subcom_parser.add_argument('--no_instance_key', action='store_true',
                                             help='Flag indicating to not use the instance key (in .clap/configs/instance.yml ')

        paramount_subcom_parser.set_defaults(func=self.setup_cluster)

        ## Start a job
        paramount_subcom_parser = commands_parser.add_parser('create-job', help='Creates a new job at the desired cluster \
                  ')

        paramount_subcom_parser.add_argument('id', metavar='MCLUSTERID', action='store',
                                             help='Mclusterluster id, or \'{}\' if the last one created (highest ID) should '
                                                  'be used'.format(Info.LAST_PARAMOUNT))

        paramount_subcom_parser.add_argument('--job_name', action='store', nargs='?',
                                             help='Optional job description. ')

        paramount_subcom_parser.set_defaults(func=self.new_job_handler)

        ## Pull files from coord #TODO: refactor to get job specific?
        paramount_subcom_parser = commands_parser.add_parser('fetch-data-coord', help='Fetch data from coord \
                       ')

        paramount_subcom_parser.add_argument('id', metavar='MCLUSTERID', action='store',
                                             help='Mcluster  id, or \'{}\' if the last one created (highest ID) should '
                                                  'be used'.format(Info.LAST_PARAMOUNT))

        paramount_subcom_parser.add_argument('src', action='store',
                                             help='src (on coord)')
        paramount_subcom_parser.add_argument('dest', action='store',
                                             help='dest (on localhost)')

        paramount_subcom_parser.set_defaults(func=self.fetch_data_coord_handler)

        ## Listing jobs
        paramount_subcom_parser = commands_parser.add_parser('list-jobs', help='List started jobs')

        paramount_subcom_parser.set_defaults(func=self.list_jobs_handler)

        ## push files
        paramount_subcom_parser = commands_parser.add_parser('push-job-files', help='Push files to job a directory \
                  ')

        paramount_subcom_parser.add_argument('id', metavar='JOBID', action='store',
                                             help='Job id or \'{}\' if the last one created (highest ID) should'
                                                  'be used'.format(Info.LAST_JOB))

        paramount_subcom_parser.add_argument('src', action='store',
                                             help='Source folder')

        paramount_subcom_parser.add_argument('--sub_path', action='store', nargs='?',
                                             help='Subdirectory inside job folder where the script should be executed, if left' \
                                                  'unspecified it will execute in the job root')
        paramount_subcom_parser.add_argument('--from_coord', action='store_true',
                                             help='Flag that indicates the the coordinator already has the files'
                                                  'somewhere  in the system, and therefore these files'
                                                  'should be pushed from the coordinator to the job folder in the file'
                                                  'system')

        paramount_subcom_parser.set_defaults(func=self.push_files_handler)

        ## compile
        paramount_subcom_parser = commands_parser.add_parser('setup-job',
                                                             help='Used to setup the job (example: compiling the application) ')

        paramount_subcom_parser.add_argument('id', metavar='JOBID', action='store',
                                             help='Job id, or \'{}\' if the last one created (highest ID) should'
                                                  'be used'.format(Info.LAST_JOB))

        paramount_subcom_parser.add_argument('script_path', action='store',
                                             help='Script path which will be used to setup the job')

        paramount_subcom_parser.add_argument('--sub_path', action='store', nargs='?',
                                             help='Subdirectory inside job folder where the script should be executed, if left' \
                                                  'unspecified it will execute in the job root')

        paramount_subcom_parser.set_defaults(func=self.compile_script_handler)

        # Running script
        paramount_subcom_parser = commands_parser.add_parser('run-job-task',
                                                             help='Run a job\'s task, if no sub_path is specified the script'
                                                                  ' will be executed in the job root, otherwise it will be acessed in a subdirectory'
                                                                  'specified in the sub argument \
                         ')

        paramount_subcom_parser.add_argument('id', metavar='JOBID', action='store',
                                             help='Job id, or \'{}\' if the last one created (highest ID) should'
                                                  'be used'.format(Info.LAST_JOB))

        paramount_subcom_parser.add_argument('script_path', action='store',
                                             help='Script that specifies how to run the application')

        paramount_subcom_parser.add_argument('--sub_path', action='store', nargs='?',
                                             help='Subdirectory inside job folder where the script should be executed, if left ' \
                                                  'unspecified it will execute in the job root')
        paramount_subcom_parser.add_argument('--exec_desr', action='store', nargs='?',
                                             help='Description of this specific execution (problem size, algorithm used...)')

        paramount_subcom_parser.set_defaults(func=self.run_script_handler)

        # Generate host
        paramount_subcom_parser = commands_parser.add_parser('gen-job-hostfile',
                                                             help='Generate a hostfile containing ' \
                                                                  'all nodes from the mcluster')

        paramount_subcom_parser.add_argument('id', metavar='JOBID', action='store',
                                             help='Job id, or \'{}\' if the last one created (highest ID) should'
                                                  'be used'.format(Info.LAST_JOB))


        paramount_subcom_parser.add_argument('--sub_path', action='store', nargs='?',
                                             help='Subdirectory inside job folder where the script should be executed, if left ' \
                                                  'unspecified it will execute in the job root')

        paramount_subcom_parser.add_argument('--file_name', action='store', nargs='?',
                                             help='What name should the file be, defaults to \'host\'')

        paramount_subcom_parser.add_argument('--mpich_style', action='store_true',
                                             help='If the hostfile should be written in a mpich style way')

        paramount_subcom_parser.set_defaults(func=self.generate_host_handler)

        # Fetch paramount  info
        paramount_subcom_parser = commands_parser.add_parser('fetch-tasks-results',
                                                             help='Fetch the tasks\' results ')

        paramount_subcom_parser.add_argument('id', metavar='JOBID', action='store',
                                             help='Job id, or \'{}\' if the last one created (highest ID) should'
                                                  'be used'.format(Info.LAST_JOB))

        paramount_subcom_parser.add_argument('dest', action='store',
                                             help='The directory where the logs should be saved')

        paramount_subcom_parser.set_defaults(func=self.fetch_tasks_handler)

        # Install script

        paramount_subcom_parser = commands_parser.add_parser('run-script',
                                                             help='Runs a script on every node (or only on the coordinator, if wanted')

        paramount_subcom_parser.add_argument('id', metavar='MCLUSTERID', action='store',
                                             help='Mpc on which the script  should be run, or \'{}\' if the last one created (highest ID) should'
                                                  'be used'.format(Info.LAST_PARAMOUNT))

        paramount_subcom_parser.add_argument('script_path', action='store',
                                             help='The full directory where the script resides on the localhost (your machine)')

        paramount_subcom_parser.add_argument('--only_coord', action='store_true',
                                             help='If the script should be executed only in the coord')

        paramount_subcom_parser.add_argument('--file', action='store', nargs='?',
                                             help='Files (if any) that should be passed to execute the script')

        paramount_subcom_parser.add_argument('--path', action='store', nargs='?',
                                             help='Subdirectory inside job folder where the script should be executed, if left ' \
                                                  'unspecified it will execute in the job root')

        paramount_subcom_parser.set_defaults(func=self.install_script_handler)

        # Run command

        paramount_subcom_parser = commands_parser.add_parser('run-command',
                                                             help='Runs the shell command passed as string in every node')

        paramount_subcom_parser.add_argument('id', metavar='MCLUSTERID', action='store',
                                             help='Mcluster ID, or \'{}\' if the last one created (highest ID) should'
                                                  'be used'.format(Info.LAST_PARAMOUNT))

        paramount_subcom_parser.add_argument('command', action='store',
                                             help='Simple quote delimitated command')

        paramount_subcom_parser.add_argument('--only_coord', action='store_true',
                                             help='If the command should be executed only in the coord')

        paramount_subcom_parser.set_defaults(func=self.run_command_handler)

        # Add nodes to existing clap-mpi cluster

        # paramount_subcom_parser = commands_parser.add_parser('add-new-nodes',
        #                                                      help='Given instance:number tuple this command will'
        #                                                           'start these instances then add to the given mpc '
        #                                                           'and perform a setup operation in a way that these nodes '
        #                                                           'can be successfully added to the cluster ')
        #
        # paramount_subcom_parser.add_argument('id', metavar='ID', action='store',
        #                                      help='Paramount cluster  ID, or \'{}\' if the last one created (highest ID) should'
        #                                           'be used'.format(Info.LAST_PARAMOUNT))
        #
        # paramount_subcom_parser.add_argument('--coord', action='store',
        #                                      help='If set one of (or the only) node will be selected as a coordinator')
        #
        # paramount_subcom_parser.add_argument('nodes', action='store', metavar='node_type:num', nargs='+',
        #                                      help='Nodes to be initialized of the form instance:number ')
        #
        # paramount_subcom_parser.set_defaults(func=self.add_new_node_handler)




        paramount_subcom_parser = commands_parser.add_parser('remove-coord',
                                                             help='Removes the current coord, adding a new coord (if the user '
                                                                  'desires) or simply promoves a slave as coordinator (default) ')

        paramount_subcom_parser.add_argument('id', metavar='MCLUSTERID', action='store',
                                             help='Mcluster ID, or \'{}\' if the last one created (highest ID) should'
                                                  'be used'.format(Info.LAST_PARAMOUNT))

        paramount_subcom_parser.add_argument('--add_coord', metavar='NEW_COORD_TYPE', action='store', nargs='?',
                                             help='Subdirectory inside job folder where the script should be executed, if left ' \
                                                  'unspecified it will execute in the job root')

        paramount_subcom_parser.set_defaults(func=self.remove_coord_handler)





        paramount_subcom_parser = commands_parser.add_parser('run-playbook',
                                                             help='Runs the playbook in the paramount cluster.'
                                                                  'If --only_coord evoker, executes only in the  coordinator node'
                                                                  ' ')

        paramount_subcom_parser.add_argument('id', metavar='MCLUSTERID', action='store',
                                             help='Mcluster ID, or \'{}\' if the last one created (highest ID) should'
                                                  'be used'.format(Info.LAST_PARAMOUNT))

        paramount_subcom_parser.add_argument('--file', action='store', nargs='?',
                                             help='Files (if any) that should be passed to execute the playbook')

        paramount_subcom_parser.add_argument('--only_coord', action='store_true',
                                             help='If Installation script should be executed only in the coord')

        paramount_subcom_parser.set_defaults(func=self.run_playbook_handler)

        paramount_subcom_parser = commands_parser.add_parser('destroy-mcluster',
                                                             help='Terminates the mpc. Effectively cleaning up the volume'\
                                                                  'from the data created and shutting down all nodes')

        paramount_subcom_parser.add_argument('id', metavar='MCLUSTERID', action='store',
                                             help='Mcluster id, or \'{}\' if the last one created (highest ID) should'
                                                  'be used'.format(Info.LAST_PARAMOUNT))
        paramount_subcom_parser.set_defaults(func=self.terminate_handler)


        paramount_subcom_parser = commands_parser.add_parser('pause-cluster',
                                                             help='Pauses the cluster')

        paramount_subcom_parser.add_argument('id', metavar='MCLUSTERID', action='store',
                                             help='Mcluster id, or \'{}\' if the last one created (highest ID) should'
                                                  'be used'.format(Info.LAST_PARAMOUNT))
        paramount_subcom_parser.set_defaults(func=self.pause_handler)


        paramount_subcom_parser = commands_parser.add_parser('resume-cluster',
                                                             help='Resumes the cluster')

        paramount_subcom_parser.add_argument('id', metavar='MCLUSTERID', action='store',
                                             help='Mcluster id, or \'{}\' if the last one created (highest ID) should'
                                                  'be used'.format(Info.LAST_PARAMOUNT))
        paramount_subcom_parser.set_defaults(func=self.resume_handler)

    def start_paramount_cluster(self, namespace: argparse.Namespace):

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

        return

    def terminate_handler(self, namespace: argparse.Namespace):
        _mpc_id = namespace.id

        terminate_cluster(_mpc_id)
        return

    def pause_handler(self, namespace: argparse.Namespace):
        _mpc_id = namespace.id

        pause_cluster(_mpc_id)
        return


    def resume_handler(self, namespace: argparse.Namespace):
        _mpc_id = namespace.id

        resume_cluster(_mpc_id)
        return

    def list_paramount_command(self, namespace: argparse.Namespace ):
        _clusters = list_paramount_clusters()
        print("Active mclusters are: \n")
        for _cluster in _clusters:
            if _cluster.status != Mcluster_states.MCLUSTER_TERMINATED.value:
                print('* ' + str(_cluster))
        return

    def setup_cluster(self, namespace: argparse.Namespace):
        # TODO: Validate input?
        setup_paramount_cluster(paramount_id=namespace.id,
                                mount_ip=namespace.mount_ip,
                                skip_mpi=namespace.skip_mpi,
                                no_instance_key=namespace.no_instance_key)
        return



    def fetch_data_coord_handler(self, namespace: argparse.Namespace):
        fetch_data_coord(namespace.id, namespace.src, namespace.dest)


    def new_job_handler(self, namespace: argparse.Namespace):
        new_job_from_cluster(namespace.id, job_name=namespace.job_name)

    def list_jobs_handler(self, namespace: argparse.Namespace):
        _jobs = list_jobs()
        print("Current clap-mpi clusters are: \n")
        for _job in _jobs:
            print('* ' + str(_job))
        return

    def push_files_handler(self, namespace: argparse.Namespace):
        _job_id = namespace.id
        _src = namespace.src
        _from_coord = namespace.from_coord
        _subpath = namespace.sub_path

        push_files(job_id=_job_id, src=_src, from_coord=_from_coord, subpath=_subpath)

    def compile_script_handler(self, namespace: argparse.Namespace):
        _job_id = namespace.id
        _script_path = namespace.script_path
        _subpath = namespace.sub_path
        compile_script(job_id=_job_id, script=_script_path, subpath=_subpath)

    def run_script_handler(self, namespace: argparse.Namespace):
        _job_id = namespace.id
        _script_path = namespace.script_path
        _subpath = namespace.sub_path
        _exec_descr = namespace.exec_desr
        run_script(job_id=_job_id, script=_script_path, subpath=_subpath, exec_descr=_exec_descr)

    def generate_host_handler(self, namespace: argparse.Namespace):
        _job_id = namespace.id
        _file_name = namespace.file_name
        _subpath = namespace.sub_path
        _mpich_style = namespace.mpich_style
        generate_hosts(job_id=_job_id, _file_name=_file_name, subpath=_subpath, mpich_style=_mpich_style)

    def fetch_tasks_handler(self, namespace: argparse.Namespace):
        _job_id = namespace.id
        _dest = namespace.dest
        fetch_job_paramount(job_id=_job_id, dest=_dest)

    def install_script_handler(self, namespace: argparse.Namespace):

        _mpc_id = namespace.id
        _script = namespace.script_path
        _file = namespace.file
        _path = namespace.path
        _only_coord= namespace.only_coord

        install_script(mpc_id=_mpc_id, script=_script, additionalFile=_file, path=_path, only_coord=_only_coord)

    def run_command_handler(self, namespace: argparse.Namespace):
        _mpc_id = namespace.id
        _command = namespace.command
        _only_coord = namespace.only_coord

        run_command(mpc_id=_mpc_id, command=_command, only_coord=_only_coord)

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
        _new_coord= namespace.add_coord

        _newCoord = change_coordinator(_mpc_id, _new_coord)
        print("Coordinator successfully removed, new coordinator is `{}` ".format(_newCoord))


    # def add_coord_handler(self, namespace: argparse.Namespace):
    #     _mpc_id = namespace.id
    #     _new_coord= namespace.type
    #
    #     _newCoord = change_coordinator(_mpc_id, _new_coord)
    #     print("Coordinator successfully removed, new coordinator is `{}` ".format(_newCoord))


    def run_playbook_handler(self, namespace: argparse.Namespace):
        _mpc_id = namespace.id
        _file = namespace.file
        _oc= namespace.only_coord
        run_playbook(mpc_id=_mpc_id, playbook_file=_file, only_coord=_oc)