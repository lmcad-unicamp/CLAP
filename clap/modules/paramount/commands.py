import argparse
import os
import yaml

from typing import List

from clap.common.module import AbstractParser
from clap.common.utils import log, path_extend, float_time_to_string
from .module import *
from .conf import ParamountClusterDefaults

class ClusterParser(AbstractParser):
    def add_parser(self, commands_parser: argparse._SubParsersAction):
        # cluster start commands 
        paramount_subcom_parser = commands_parser.add_parser('start', help='Start a paramount cluster')
        paramount_subcom_parser.add_argument('app_name', action='store', 
                help='Symbolic name of the application to run')
        paramount_subcom_parser.add_argument('node_type', action='store', 
                help='Type of the node to be created')
        paramount_subcom_parser.add_argument('sizes', action='store', nargs='+',
                help='List with the number of nodes to be executed...')
        paramount_subcom_parser.set_defaults(func=self.start_paramount_cluster)

        paramount_subcom_parser = commands_parser.add_parser('list', help='List paramount clusters created')
        paramount_subcom_parser.set_defaults(func=self.list_paramount_clusters)

        paramount_subcom_parser = commands_parser.add_parser('setup', help='Setup a paramount cluster')
        paramount_subcom_parser.add_argument('paramount_id', action='store', 
                help='ID of the paramount cluster to setup')
        paramount_subcom_parser.add_argument('--app-dir', action='store', 
                help='Directory of the application to copy (rsync convention)')
        paramount_subcom_parser.set_defaults(func=self.setup_paramount_cluster)
        paramount_subcom_parser.add_argument('--execution-dir', action='store', 
                help='Execution directory')

        paramount_subcom_parser = commands_parser.add_parser('run', help='Run paramount app in cluster')
        paramount_subcom_parser.add_argument('paramount_id', action='store', 
                help='ID of the paramount cluster to run')
        paramount_subcom_parser.add_argument('output_dir', action='store', 
                help='Final directory to put results on (localhost)')
        paramount_subcom_parser.add_argument('execute_scripts', action='store', nargs='+',
                help='Script used to execute an application')
        paramount_subcom_parser.add_argument('--install_script', action='store', 
                help='Script used to install')
        paramount_subcom_parser.add_argument('--compile_script', action='store', 
                help='Script used to compile')
        paramount_subcom_parser.set_defaults(func=self.run_paramount_cluster)

        # fetch

        # stop
        paramount_subcom_parser = commands_parser.add_parser('stop', help='Stop a paramount cluster')
        paramount_subcom_parser.add_argument('paramount_id', action='store', 
                help='ID of the paramount cluster to run')
        paramount_subcom_parser.set_defaults(func=self.stop_paramount_cluster)

    def start_paramount_cluster(self, namespace: argparse.Namespace):
        print(namespace)
        app_name = namespace.app_name
        node_type = namespace.node_type
        try:
            sizes = [int(value) for value in namespace.sizes]
        except ValueError as e:
            log.error(e)
            log.error("The size must be a list o integers")
            return 1
        paramount = create_paramount_cluster(app_name, node_type, sizes)
        print("Created paramount cluster: `{}` (cluster: `{}`)".format(paramount.paramount_id, paramount.cluster_id))
        return 0

    def list_paramount_clusters(self, namespace: argparse.Namespace):
        paramounts = list_paramount()        
        for paramount_info in paramounts:
            print('------- `{}` --------'.format(paramount_info.paramount_id))
            print(yaml.dump(paramount_info.__dict__, indent=4))

        print("Listed {} paramount cluster(s)".format(len(paramounts)))
        return 0

    def setup_paramount_cluster(self, namespace: argparse.Namespace):
        paramount_id = namespace.paramount_id
        app_dir = namespace.app_dir
        execution_dir = namespace.execution_dir
        setup_paramout_cluster(paramount_id, app_dir=app_dir, execution_dir=execution_dir)
        return 0

    def run_paramount_cluster(self, namespace: argparse.Namespace):
        paramount_id = namespace.paramount_id
        execute_scripts = namespace.execute_scripts
        install_script = namespace.install_script
        compile_script = namespace.compile_script
        output_dir = namespace.output_dir

        run_paramount(
            paramount_id=paramount_id, 
            output_result_dir=output_dir, 
            install_script=install_script, 
            compile_script=compile_script,
            execute_scripts=execute_scripts)
        return 0

    def stop_paramount_cluster(self, namespace: argparse.Namespace):
        paramount_id = namespace.paramount_id
        paramount = stop_paramount_cluster(paramount_id)
        print("Paramount `{}` was stopped (cluster: `{}`)".format(paramount_id, paramount.cluster_id))
        return 0