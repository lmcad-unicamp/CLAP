from .repository import *
from clap.common.factory import PlatformFactory

def list_paramount_clusters():
    repository = ParamountClusterRepositoryOperations()
    return repository.list_paramount_clusters()


def create_paramount(nodes: List[str]) -> int:

    repository = ParamountClusterRepositoryOperations()
    cluster_module = PlatformFactory.get_module_interface().get_module('cluster')  
    # with tmpdir() as dir:
    #     filename = path_extend(dir, 'mpi-paramount-cluster.yml')
    #     with open(filename, 'w') as f:
    #         f.write(rendered_template)
    #     cluster, nodes, is_setup = cluster_module.cluster_create([filename], cluster_name='paramount-cluster')

    # # Pega o módulo group. Este módulo é responsável por adicionar, remover e executar ações em grupo. As funções disponíveis estão em [2]
    # repository.new_paramount_cluster()
    return 0