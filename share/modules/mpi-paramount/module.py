import jinja2

from .repository import *
from .conf import Info
from .jobs import *
from clap.common.factory import PlatformFactory
from clap.common.utils import tmpdir, path_extend
from jinja2 import Template

debug = True


def list_paramount_clusters():
    repository = ParamountClusterRepositoryOperations()
    return repository.list_paramount_clusters()

def list_jobs():
    repository = JobDataRepositoryOperations()
    return repository.list_jobs()

def setup_paramount_cluster(paramount_id, mount_ip, skip_mpi, no_instance_key ):
    repository = ParamountClusterRepositoryOperations()
    cluster_module = PlatformFactory.get_module_interface().get_module('cluster')

    _cluster= repository.get_paramount_data(paramount_id)
    _cluster= next(iter(repository.get_paramount_data(paramount_id)))

    extra = {}

    #Folder in the shared filesystem where this cluster operates

    _mount_point_partition=  Info.MOUNT_POINT_ROOT + _cluster.paramount_id
    extra.update({'mount_ip':mount_ip})
    extra.update({'nodes_group_name': _cluster.paramount_id })

    if skip_mpi:
        extra.update({'skip_mpi':'True'})
    if no_instance_key:
        extra.update({'use_instance_key':'False'})


    #Teste: adicionando o coordinator
    cluster_module.cluster_group_add(cluster_id=_cluster.cluster_id,
                                     group_name='mpi/coordinator',
                                     node_ids=[_cluster.coordinator],
                                     extra_args= extra
                                     )


    if _cluster.slaves.__len__() > 0:
        cluster_module.cluster_group_add(cluster_id=_cluster.cluster_id,
                                         group_name='mpi/slave',
                                         node_ids=_cluster.slaves,
                                         extra_args=extra
                                         )

    _cluster.mount_point_partition = _mount_point_partition


    ######TODO: fazer update do objeto cluster
    repository.update_paramount(_cluster)

    if debug:
        _cluster = repository.get_paramount_data(paramount_id)
        _cluster = next(iter(repository.get_paramount_data(paramount_id)))
        print("New mount_point_partition (After updating) is {}".format(_cluster.mount_point_partition))


    pass

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


def new_job_from_cluster( paramount_id, name=None):
    repositoryParamount = ParamountClusterRepositoryOperations()
    _cluster= repositoryParamount.get_paramount_data(paramount_id)
    _cluster= next(iter(repositoryParamount.get_paramount_data(paramount_id)))

    repositoryJob = JobDataRepositoryOperations()

    _job = repositoryJob.new_job(cluster_obj= _cluster, absolute_path_mount=_cluster.mount_point_partition, name=name)

    #Update the object
    _cluster.jobs.append(_job.jobId)

    repositoryParamount.update_paramount(_cluster)