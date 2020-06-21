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


        create_paramount(nodes=_nodes,descr=_desc)
        return