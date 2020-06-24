import jinja2

from .repository import *
from .conf import Info
from clap.common.factory import PlatformFactory
from clap.common.utils import tmpdir, path_extend
from jinja2 import Template


def list_paramount_clusters():
    repository = ParamountClusterRepositoryOperations()
    return repository.list_paramount_clusters()


def create_paramount(nodes: List[str], descr = None) -> int:


    _type, _size =nodes[0].split(':')
    cluster_module = PlatformFactory.get_module_interface().get_module('cluster')
    #Argumento loader indica a pasta, no caso o lugar coincide com onde o src code está
    # isto é os.path.abspath(__file__) retorna o endereço absoluto e os.path.dirname pega o diretorio
    jinjaenv = jinja2.Environment(loader=jinja2.FileSystemLoader(os.path.dirname(os.path.abspath(__file__))), 
        trim_blocks=True, lstrip_blocks=True)
    template = jinjaenv.get_template("mpi-paramount-cluster.j2")
    rendered_template = template.render({'node_type': _type, 'node_count': int(_size)})

    repository = ParamountClusterRepositoryOperations()

    with tmpdir() as dir:
        filename = path_extend(dir, 'mpi-paramount-cluster.yml')
        with open(filename, 'w') as f:
            f.write(rendered_template)
        cluster, nodes, is_setup = cluster_module.cluster_create([filename], cluster_name='mpi-paramount-cluster')

    _coordinator = list(filter(lambda x: x.tags['cluster_node_type'][0].split(':')[1] == Info.COORDINATOR, nodes))[0].node_id
    _slaves  =[ x.node_id for x  in list(filter(lambda x: x.tags['cluster_node_type'][0].split(':')[1] == Info.SLAVES, nodes)) ]


    _paramount_cluster = repository.new_paramount_cluster(cluster_id=cluster.cluster_id, slaves=_slaves, coordinator= _coordinator, descr=descr)
    # Pega o módulo group. Este módulo é responsável por adicionar, remover e executar ações em grupo. As funções disponíveis estão em [2]
    #repository.new_paramount_cluster()
    return _paramount_cluster