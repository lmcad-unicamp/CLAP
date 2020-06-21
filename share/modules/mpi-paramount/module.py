import jinja2

from .repository import *
from clap.common.factory import PlatformFactory
from clap.common.utils import tmpdir, path_extend
from jinja2 import Template


def list_paramount_clusters():
    repository = ParamountClusterRepositoryOperations()
    return repository.list_paramount_clusters()


def create_paramount(nodes: List[str], descr = None) -> int:

    repository = ParamountClusterRepositoryOperations()
    cluster_module = PlatformFactory.get_module_interface().get_module('cluster')  
    #Argumento loader indica a pasta, no caso o lugar coincide com onde o src code está
    # isto é os.path.abspath(__file__) retorna o endereço absoluto e os.path.dirname pega o diretorio
    jinjaenv = jinja2.Environment(loader=jinja2.FileSystemLoader(os.path.dirname(os.path.abspath(__file__))), 
        trim_blocks=True, lstrip_blocks=True)
    template = jinjaenv.get_template("mpi-paramount-cluster.j2")


    with tmpdir() as dir:
        filename = path_extend(dir, 'mpi-paramount-cluster.yml')
        with open(filename, 'w') as f:
            f.write(rendered_template)
        #cluster, nodes, is_setup = cluster_module.cluster_create([filename], cluster_name='paramount-cluster')

    # Pega o módulo group. Este módulo é responsável por adicionar, remover e executar ações em grupo. As funções disponíveis estão em [2]
    #repository.new_paramount_cluster()
    return 0