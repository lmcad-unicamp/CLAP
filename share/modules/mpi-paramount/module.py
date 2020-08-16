import jinja2
import json
from .repository import *
from .conf import Info
from typing import List, Dict
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
    '''
    Method that sets up the cluster. Not only the cluster is configured with the parameters
    but the "settings" are saved in the cluster variable, such that when adding a new node
    or exchanging the coordinator the settings used in this method will be used (example
    the same mount_ip will be used)
    :param paramount_id:
    :param mount_ip:
    :param skip_mpi:
    :param no_instance_key:
    :return:
    '''
    repository = ParamountClusterRepositoryOperations()
    cluster_module = PlatformFactory.get_module_interface().get_module('cluster')

    _cluster= repository.get_paramount_data(paramount_id)
    _cluster= next(iter(repository.get_paramount_data(paramount_id)))

    extra = {}



    #Folder in the shared filesystem where this cluster operates ($PATH not evaluated, fixed later)
    _mount_point_partition=  Info.MOUNT_POINT_ROOT + _cluster.paramount_id
    extra.update({'mount_ip':mount_ip})
    extra.update({'nodes_group_name': _cluster.paramount_id })

    _cluster.mount_ip = mount_ip

    if skip_mpi:
        extra.update({'skip_mpi':'True'})
        _cluster.skip_mpi = skip_mpi

    if no_instance_key:
        extra.update({'use_instance_key':'False'})
        _cluster.no_instance_key = no_instance_key




    #Teste: adicionando o coordinator
    cluster_module.cluster_group_add(cluster_id=_cluster.cluster_id,
                                     group_name='mpi/coordinator',
                                     node_ids=[_cluster.coordinator],
                                     extra_args= extra,
                                     re_add_to_group=True
                                     )


    if _cluster.slaves.__len__() > 0:
        cluster_module.cluster_group_add(cluster_id=_cluster.cluster_id,
                                         group_name='mpi/slave',
                                         node_ids=_cluster.slaves,
                                         extra_args=extra,
                                         re_add_to_group=True
                                         )

    if _cluster.mount_point_partition is None:
        with tmpdir() as dir:
            filename = path_extend(dir, 'mpi-paramount-cluster.yml')

            extra = {}
            extra.update({'dest': filename})

            cluster_module.perform_group_action(cluster_id= _cluster.cluster_id,
                                            group_name= 'mpi',
                                            action_name= 'get-infos',
                                            node_ids= [_cluster.coordinator],
                                            extra_args= extra)

            with open(filename, 'r') as f:

                _data = json.loads(f.read())
                _home= _data['ansible_env.HOME']
                _mount_point_partition = _home + _mount_point_partition

        _cluster.mount_point_partition = _mount_point_partition


    _cluster.isSetup = True
    ######TODO: fazer update do objeto cluster
    repository.update_paramount(_cluster)

    if debug:
        _cluster = repository.get_paramount_data(paramount_id)
        _cluster = next(iter(repository.get_paramount_data(paramount_id)))
        print("New mount_point_partition (After updating) is {}".format(_cluster.mount_point_partition))


    pass




# def add_nodes_to_mpc_cluster__(paramount_id, node_group_map: Dict[str, str]):
#     '''
#
#     For internal use.
#     :param paramount_id: The mpc id
#     :param node_group_map:  node-xx:group
#     :return:
#     '''
#
#
#     repository = ParamountClusterRepositoryOperations()
#     cluster_module = PlatformFactory.get_module_interface().get_module('cluster')
#
#     _cluster= repository.get_paramount_data(paramount_id)
#     _cluster= next(iter(repository.get_paramount_data(paramount_id)))
#
#





def create_paramount(nodes: List[str], descr = None, coord = None) -> int:


    _type, _sizeSlaves =nodes[0].split(':')
    cluster_module = PlatformFactory.get_module_interface().get_module('cluster')
    #Argumento loader indica a pasta, no caso o lugar coincide com onde o src code está
    # isto é os.path.abspath(__file__) retorna o endereço absoluto e os.path.dirname pega o diretorio
    jinjaenv = jinja2.Environment(loader=jinja2.FileSystemLoader(os.path.dirname(os.path.abspath(__file__))),
        trim_blocks=True, lstrip_blocks=True)
    template = jinjaenv.get_template("mpi-paramount-cluster.j2")

    #Neste caso coord e um dos slaves, aleatoriamente selecionado
    if coord is None:
        node_type_coord = _type
        _sizeSlaves = int(_sizeSlaves) -1 #Um sera o coord

    else:
        node_type_coord = coord

    rendered_template = template.render({'node_type_coord': node_type_coord, 'node_type': _type, 'node_count': int(_sizeSlaves)})

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



def new_job_from_cluster( paramount_id, job_name=None):
    repositoryParamount = ParamountClusterRepositoryOperations()
    _cluster= next(iter(repositoryParamount.get_paramount_data(paramount_id)))

    repositoryJob = JobDataRepositoryOperations()

    _job = repositoryJob.new_job(cluster_obj= _cluster, absolute_path_mount=_cluster.mount_point_partition, job_name=job_name)

    #Update the object
    _cluster.jobs.append(_job.jobId)

    repositoryParamount.update_paramount(_cluster)


def push_files(job_id, src):
    repositoryParamount = ParamountClusterRepositoryOperations()
    repositoryJobs = JobDataRepositoryOperations()
    cluster_module = PlatformFactory.get_module_interface().get_module('cluster')

    _job =  next(iter(repositoryJobs.get_job_data(job_id)))
    _mpcObj =  next(iter(repositoryParamount.get_paramount_data(_job.paramount_id)))

    _dest = _job.absolutePath


    extra = {}
    extra.update({'execution_dir':_dest})
    extra.update({'src_dir':src})

    cluster_module.perform_group_action(cluster_id= _mpcObj.cluster_id,
                                        group_name= 'mpi',
                                        action_name= 'sync',
                                        node_ids= [_mpcObj.coordinator],
                                        extra_args= extra)


def compile_script(job_id, script, subpath):
    repositoryParamount = ParamountClusterRepositoryOperations()
    repositoryJobs = JobDataRepositoryOperations()
    cluster_module = PlatformFactory.get_module_interface().get_module('cluster')

    _job =  next(iter(repositoryJobs.get_job_data(job_id)))
    _mpcObj =  next(iter(repositoryParamount.get_paramount_data(_job.paramount_id)))

    _path = _job.absolutePath
    if  subpath is not  None:
        _path = _path + '/' + subpath


    extra = {}
    extra.update({'compile_script': script})
    extra.update({'execution_dir': _path})

    cluster_module.perform_group_action(cluster_id= _mpcObj.cluster_id,
                                        group_name= 'mpi',
                                        action_name= 'compile',
                                        node_ids= [_mpcObj.coordinator],
                                        extra_args= extra,
                                        )




def run_script(job_id, script, subpath, exec_descr):
    repositoryParamount = ParamountClusterRepositoryOperations()
    repositoryJobs = JobDataRepositoryOperations()
    cluster_module = PlatformFactory.get_module_interface().get_module('cluster')

    _job =  next(iter(repositoryJobs.get_job_data(job_id)))
    _mpcObj =  next(iter(repositoryParamount.get_paramount_data(_job.paramount_id)))

    _path = _job.absolutePath
    if  subpath is not  None:
        _path = _path + '/' + subpath


    extra = {}
    extra.update({'run_script': script})
    extra.update({'execution_dir': _path})
    extra.update({'job_full_path': _job.absolutePath})

    if exec_descr is not None:
        extra.update({'exec_descr': _job.exec_descr})

    cluster_module.perform_group_action(cluster_id= _mpcObj.cluster_id,
                                        group_name= 'mpi',
                                        action_name= 'run-script',
                                        node_ids= [_mpcObj.coordinator],
                                        extra_args= extra)


def generate_hosts(job_id, _file_name, subpath):
    repositoryParamount = ParamountClusterRepositoryOperations()
    repositoryJobs = JobDataRepositoryOperations()
    cluster_module = PlatformFactory.get_module_interface().get_module('cluster')

    _job =  next(iter(repositoryJobs.get_job_data(job_id)))
    _mpcObj =  next(iter(repositoryParamount.get_paramount_data(_job.paramount_id)))

    _path = _job.absolutePath
    if  subpath is not  None:
        _path = _path + '/' + subpath


    extra = {}

    # Tem que ser assim, passar direto não funciona, pq se não for definido o ansible recebe 'None' e buga...
    if _file_name is not None:
        extra.update({'file_name': _file_name})
    extra.update({'execution_dir': _path})

    cluster_module.perform_group_action(cluster_id= _mpcObj.cluster_id,
                                        group_name= 'mpi',
                                        action_name= 'generate-hosts',
                                        extra_args= extra,
                                        )


def fetch_job_paramount(job_id, dest):
    repositoryParamount = ParamountClusterRepositoryOperations()
    repositoryJobs = JobDataRepositoryOperations()
    cluster_module = PlatformFactory.get_module_interface().get_module('cluster')

    _job = next(iter(repositoryJobs.get_job_data(job_id)))
    _mpcObj = next(iter(repositoryParamount.get_paramount_data(_job.paramount_id)))

    _path = _job.absolutePath + '/.paramount-logs'


    extra = {}
    extra.update({'src': _path})
    extra.update({'dest': dest})
    extra.update({'job_name': _job.jobId})

    cluster_module.perform_group_action(cluster_id=_mpcObj.cluster_id,
                                        group_name='mpi',
                                        action_name='fetch-job-info',
                                        extra_args=extra,
                                        )


def install_script(job_id, script, additionalFile = None, subpath = None):
    repositoryParamount = ParamountClusterRepositoryOperations()
    repositoryJobs = JobDataRepositoryOperations()
    cluster_module = PlatformFactory.get_module_interface().get_module('cluster')

    _job = next(iter(repositoryJobs.get_job_data(job_id)))
    _mpcObj = next(iter(repositoryParamount.get_paramount_data(_job.paramount_id)))

    _path = _job.absolutePath

    if subpath is not None:
        _path = _path + subpath + '/'

    extra = {}
    extra.update({'execution_dir': _path})

    if additionalFile is not None:
        extra.update({'src_dir': additionalFile})
    extra.update({'install_script': script})

    cluster_module.perform_group_action(cluster_id=_mpcObj.cluster_id,
                                        group_name='mpi',
                                        action_name='install',
                                        extra_args=extra,
                                        )



def run_command(mpc_id, command):
    repositoryParamount = ParamountClusterRepositoryOperations()
    cluster_module = PlatformFactory.get_module_interface().get_module('cluster')

    _mpcObj = next(iter(repositoryParamount.get_paramount_data(mpc_id)))
    _nodes = [_mpcObj.coordinator] + _mpcObj.slaves


    cluster_module.run_command(node_ids=_nodes, command_string=command)


# Add new instances to a existing mpc, all nodes are added as slaves, if wanted  a node can be later promoted
# to coordinator with "change_coordinator". Although it will make an unnecessary addition as slave, it is worth
# to keep the modules simpler (each method has its own functionality) and therefore
# delegate coordinator exchange to another method

def add_from_instances(paramount_id, node_type: Dict[str, int]):
    #Creates nodes, add them to the cluster them call setup with saved cluster configuration

    repository = ParamountClusterRepositoryOperations()
    cluster_module = PlatformFactory.get_module_interface().get_module('cluster')

    _cluster = repository.get_paramount_data(paramount_id)
    _cluster = next(iter(repository.get_paramount_data(paramount_id)))
    node_type = {node_type[0].split(':')[0]:node_type[0].split(':')[1]}

    cluster, created_nodes = cluster_module.add_nodes_to_cluster(_cluster.cluster_id, node_types= node_type)

    # TODO: update paramount cluster to include these nodes (created nodes)
    _cluster.slaves = _cluster.slave.extend(created_nodes)

    log.info("The nodes '{}' have been added to mpc cluster of id: '{}".format(created_nodes, _cluster.paramount_id ))




    #call setup such that these nodes can be successfully integrated to the cluster (key passing, etc...)

    if _cluster.isSetup:
        setup_paramount_cluster(paramount_id=_cluster.paramount_id,
                                mount_ip= _cluster.mount_point_id,
                                skip_mpi= _cluster.skip_mpi,
                                no_instance_key= _cluster.no_instance_key
                                )


    return created_nodes

# Given a mpc demote the current coordinator and exchange by a slave
def change_coordinator(mpc_id) -> str:

    '''
    To change a coordinator this module will:
    -Remove the coord from the cluster (it will not stop/terminate the node simply disassociate from the mpi-paramount cluster)
    -Change the cluster config file (in a way to make it consistent with the new node configuration)
    -Remove the newcoord from the group/role 'mpi/slave' (because cluster module does not implement it, a call from
    group module must be made)
    - Add the newcoord to the group mpi/coordinator
    :param mpc_id:
    :return:
    '''



    repositoryParamount = ParamountClusterRepositoryOperations()
    _cluster = next(iter(repositoryParamount.get_paramount_data(mpc_id)))
    tag_module = PlatformFactory.get_module_interface().get_module('tag')
    group_module = PlatformFactory.get_module_interface().get_module('group')
    cluster_module = PlatformFactory.get_module_interface().get_module('cluster')
    node_module = PlatformFactory.get_module_interface().get_module('node')

    if not _cluster.isSetup:
        raise Exception("Please set up the cluster first before changing the coordinator ")


    nodesList = node_module.list_nodes(cluster_module.get_nodes_from_cluster(_cluster.cluster_id) )
    _slaves  =[ x for x  in list(filter(lambda x: x.tags['cluster_node_type'][0].split(':')[1] == Info.SLAVES, nodesList)) ]
    _newCoord = _slaves[0]

        # raise Exception("Removing the only coordinator does not make sense! Just terminate the cluster ")

    jinjaenv = jinja2.Environment(loader=jinja2.FileSystemLoader(os.path.dirname(os.path.abspath(__file__))),
                                  trim_blocks=True, lstrip_blocks=True)


    template = jinjaenv.get_template("mpi-paramount-cluster.j2")
    rendered_template = template.render({'node_type_coord': _newCoord.instance_type, 'node_type': _newCoord.instance_type, 'node_count': len(_slaves) - 1})

    # TODO: checar se eh slave antes de prosseguir

    with tmpdir() as dir:
        filename = path_extend(dir, 'mpi-paramount-cluster.yml')
        with open(filename, 'w') as f:
            f.write(rendered_template)
        data = cluster_module.update_cluster_config([filename],cluster_id=_cluster.cluster_id )
        print('debug')





    extra = {}
    extra.update({'mount_ip': _cluster.mount_ip})
    extra.update({'nodes_group_name': _cluster.paramount_id})
    if _cluster.skip_mpi:
        extra.update({'skip_mpi': 'True'})

    if _cluster.no_instance_key:
        extra.update({'use_instance_key': 'False'})

    oldCoordinator = _cluster.coordinator


    # Removes the old coordinator -> remove_tags_from_nodes (from platform)
    _removed = tag_module.node_remove_tag(node_ids=[oldCoordinator],
                                          tags= 'clusters')
    _removed = tag_module.node_remove_tag(node_ids=[oldCoordinator],
                                          tags= 'cluster_node_type')
    #Done twice because node_remove_tag does not allow to pass list, only string

    _cluster.coordinator = None

    # Re-adds as a slave:
    # cluster_module.cluster_group_add(cluster_id=mpc_id.cluster_id,
    #                                  group_name='mpi/slave',
    #                                  node_ids=[oldCoordinator],
    #                                  re_add_to_group=True
    #                                  )
    #
    # _cluster.slaves = _cluster.slaves.append(oldCoordinator)

    # Removes the slave and add as the coordinator

    group_module.remove_group_from_node(node_ids=[_newCoord.node_id], group='mpi/slave')
    _cluster.slaves.remove(_newCoord.node_id)

    print("Adding the new coordinator to the mpi/coordinator group. The mpi/coordinator will be set up with the"
          "same configurations which the cluster was first set up (mount_ip, use instance key or not ...")

    # Re-adds as a coordinator:
    cluster_module.cluster_group_add(cluster_id=_cluster.cluster_id,
                                     group_name='mpi/coordinator',
                                     node_ids=[_newCoord.node_id],
                                     extra_args=extra,
                                     re_add_to_group=True
                                     )

    cluster_module.add_existing_nodes_to_cluster(cluster_id=_cluster.cluster_id, node_types={Info.COORDINATOR:[_newCoord.node_id]} )
    _cluster.coordinator = _newCoord.node_id

    #TODO: remover a tag de slave do novo coordinator
    repositoryParamount.update_paramount(_cluster)

    return _newCoord.node_id