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

    _cluster= validate_and_get_cluster(paramount_id)

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
    repository.update_paramount(_cluster)

    if debug:
        _cluster = validate_and_get_cluster(paramount_id)
        print("New mount_point_partition (After updating) is {}".format(_cluster.mount_point_partition))


    pass








def create_paramount(nodes: List[str], descr = None, coord = None):
    '''
    Method that creates the paramount cluster. Basically it passes the info to the jinja template, after some
    parsing, and then calls a write operation on the repository
    :param nodes: The list of nodes
    :param descr: Description of the cluster. Defaults to None
    :param coord:  Type of the coordinator. Defaults to a randomly chosen node.
    :return:
    '''

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


    _paramount_cluster = repository.new_paramount_cluster(cluster_id=cluster.cluster_id, slaves=_slaves, \
                                                          coordinator= _coordinator, descr=descr, status= 1)
    # Pega o módulo group. Este módulo é responsável por adicionar, remover e executar ações em grupo. As funções disponíveis estão em [2]
    #repository.new_paramount_cluster()
    print("MPI-Paramount cluster created: \n")
    print(_paramount_cluster)
    return



def new_job_from_cluster( paramount_id, job_name=None):
    '''
       Given a paramount cluster id, a job is created on it.
       :param paramount_id: The paramount cluster id.
       :param job_name: Description of the job. Defaults to None

       :return:
       '''

    repositoryParamount = ParamountClusterRepositoryOperations()
    _cluster= validate_and_get_cluster(paramount_id)

    validate_cluster_setup(_cluster)

    repositoryJob = JobDataRepositoryOperations()

    _job = repositoryJob.new_job(cluster_obj= _cluster, absolute_path_mount=_cluster.mount_point_partition, job_name=job_name)

    #Update the object
    _cluster.jobs.append(_job.jobId)

    repositoryParamount.update_paramount(_cluster)


def push_files(job_id, src, from_coord, subpath=None):
    cluster_module = PlatformFactory.get_module_interface().get_module('cluster')

    _job =  validate_and_get_job(job_id)
    _mpcObj = validate_and_get_cluster(_job.paramount_id)

    _dest = _job.absolutePath

    if subpath is not None:
        _dest = _dest  +'/' + subpath



    extra = {}
    extra.update({'execution_dir':_dest})
    extra.update({'src_dir':src})

    if not from_coord:
        cluster_module.perform_group_action(cluster_id= _mpcObj.cluster_id,
                                        group_name= 'mpi',
                                        action_name= 'sync',
                                        node_ids= [_mpcObj.coordinator],
                                        extra_args= extra)

    else:
        cluster_module.perform_group_action(cluster_id=_mpcObj.cluster_id,
                                            group_name='mpi',
                                            action_name='sync-remote',
                                            node_ids=[_mpcObj.coordinator],
                                            extra_args=extra)

def terminate_cluster(mpc_id, _remove_data_from_sfs=False):
    _mpcObj = validate_and_get_cluster(mpc_id)
    node_module = PlatformFactory.get_module_interface().get_module('node')
    repository = ParamountClusterRepositoryOperations()


    _mount_point_partition = _mpcObj.mount_point_partition

    extra ={}
    _all_nodes = [_mpcObj.coordinator] + _mpcObj.slaves
    extra.update({'cluster_folder': _mount_point_partition})
    if _remove_data_from_sfs:
        extra.update({'remove_data_from_sfs':'True'})
    cluster_module = PlatformFactory.get_module_interface().get_module('cluster')
    cluster_module.perform_group_action(cluster_id=_mpcObj.cluster_id,
                                        group_name='mpi',
                                        action_name='mpi-terminate',
                                        node_ids=[_mpcObj.coordinator],
                                        extra_args=extra)

    # extra ={}
    # extra.update({'mount_point': _mount_point_partition})
    #
    # cluster_module.perform_group_action(cluster_id=_mpcObj.cluster_id,
    #                                     group_name='ec2-efs',
    #                                     action_name='unmount',
    #                                     node_ids=_all_nodes,
    #                                     extra_args=extra)

    node_module.stop_nodes(_all_nodes)
    _mpcObj.change_state(Mcluster_states.MCLUSTER_TERMINATED)
    repository.update_paramount(_mpcObj)

    return



def pause_cluster(mpc_id):
    _mpcObj = validate_and_get_cluster(mpc_id)
    node_module = PlatformFactory.get_module_interface().get_module('node')
    repository = ParamountClusterRepositoryOperations()


    _mount_point_partition = _mpcObj.mount_point_partition

    _all_nodes = [_mpcObj.coordinator] + _mpcObj.slaves


    node_module.pause_nodes(_all_nodes)
    _mpcObj.change_state(Mcluster_states.MCLUSTER_PAUSED)
    repository.update_paramount(_mpcObj)

    return

def resume_cluster(mpc_id):
    _mpcObj = validate_and_get_cluster(mpc_id)
    node_module = PlatformFactory.get_module_interface().get_module('node')
    repository = ParamountClusterRepositoryOperations()


    _mount_point_partition = _mpcObj.mount_point_partition

    _all_nodes = [_mpcObj.coordinator] + _mpcObj.slaves


    node_module.resume_nodes(_all_nodes)
    _mpcObj.change_state(Mcluster_states.MCLUSTER_RUNNING)
    repository.update_paramount(_mpcObj)

    return


def compile_script(job_id, script, subpath):
    cluster_module = PlatformFactory.get_module_interface().get_module('cluster')

    _job =  validate_and_get_job(job_id)
    _mpcObj = validate_and_get_cluster(_job.paramount_id)

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
    repositoryJobs = JobDataRepositoryOperations()
    cluster_module = PlatformFactory.get_module_interface().get_module('cluster')

    _job =   validate_and_get_job(job_id)
    _mpcObj = validate_and_get_cluster(_job.paramount_id)

    _path = _job.absolutePath + '/'
    if  subpath is not  None:
        _path = _path + '/' + subpath


    extra = {}
    extra.update({'run_script': script})
    extra.update({'execution_dir': _path})
    extra.update({'job_full_path': _job.absolutePath})
    extra.update({'mcluster_dir': _mpcObj.mount_point_partition})

    if exec_descr is not None:
        extra.update({'exec_descr': exec_descr})

    cluster_module.perform_group_action(cluster_id= _mpcObj.cluster_id,
                                        group_name= 'mpi',
                                        action_name= 'run-script',
                                        node_ids= [_mpcObj.coordinator],
                                        extra_args= extra)


def generate_hosts(job_id, _file_name, subpath,mpich_style):
    repositoryJobs = JobDataRepositoryOperations()
    cluster_module = PlatformFactory.get_module_interface().get_module('cluster')

    _job =  validate_and_get_job(job_id)
    _mpcObj = validate_and_get_cluster(_job.paramount_id)

    _path = _job.absolutePath
    if  subpath is not  None:
        _path = _path + '/' + subpath


    extra = {}

    # Tem que ser assim, passar direto não funciona, pq se não for definido o ansible recebe 'None' e buga...
    if _file_name is not None:
        extra.update({'file_name': _file_name})

    if mpich_style:
        extra.update({'mpich_style': 'True'})


    extra.update({'execution_dir': _path})

    cluster_module.perform_group_action(cluster_id= _mpcObj.cluster_id,
                                        group_name= 'mpi',
                                        action_name= 'generate-hosts',
                                        extra_args= extra,
                                        )


def fetch_job_paramount(job_id, dest):
    cluster_module = PlatformFactory.get_module_interface().get_module('cluster')

    _job =  validate_and_get_job(job_id)
    _mpcObj = validate_and_get_cluster(_job.paramount_id)

    _path = _job.absolutePath + '/tasks/*'


    extra = {}
    extra.update({'src': _path})
    extra.update({'dest': dest})
    extra.update({'job_name': _job.jobId})

    cluster_module.perform_group_action(cluster_id=_mpcObj.cluster_id,
                                        group_name='mpi',
                                        action_name='fetch-job-info',
                                        extra_args=extra,
                                        )


def fetch_data_coord(mpc_id, src, dest):
    cluster_module = PlatformFactory.get_module_interface().get_module('cluster')

    _mpcObj = validate_and_get_cluster(mpc_id)



    extra = {}
    extra.update({'src': src})
    extra.update({'dest': dest})


    cluster_module.perform_group_action(cluster_id=_mpcObj.cluster_id,
                                        group_name='mpi',
                                        action_name='fetch-data-coord',
                                        extra_args=extra,
                                        )

def install_script(mpc_id, script, only_coord, additionalFile = None, path = None):
    cluster_module = PlatformFactory.get_module_interface().get_module('cluster')

    _mpcObj = validate_and_get_cluster(mpc_id)

    #_path = _job.absolutePath


    extra = {}

    if path:
        extra.update({'execution_dir': path})

    if additionalFile is not None:
        extra.update({'src_dir': additionalFile})
    extra.update({'install_script': script})

    _nodes = [_mpcObj.coordinator] + _mpcObj.slaves if not only_coord  else [_mpcObj.coordinator]

    cluster_module.perform_group_action(cluster_id=_mpcObj.cluster_id,
                                        group_name='mpi',
                                        action_name='install',
                                        extra_args=extra,
                                        node_ids=_nodes
                                        )



def run_command(mpc_id, command):
    cluster_module = PlatformFactory.get_module_interface().get_module('cluster')

    _mpcObj =  validate_and_get_cluster(mpc_id)
    _nodes = [_mpcObj.coordinator] + _mpcObj.slaves


    cluster_module.run_command(node_ids=_nodes, command_string=command)


# Add new instances to a existing mpc, all nodes are added as slaves, if wanted  a node can be later promoted
# to coordinator with "change_coordinator". Although it will make an unnecessary addition as slave, it is worth
# to keep the modules simpler (each method has its own functionality) and therefore
# delegate coordinator exchange to another method

def add_from_instances(paramount_id, node_type: Dict[str, int]):
    #Creates nodes, add them to the cluster them call setup with saved cluster configuration

    cluster_module = PlatformFactory.get_module_interface().get_module('cluster')

    _cluster = validate_and_get_cluster(paramount_id)
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
def change_coordinator(mpc_id, new_coord_inst= None) -> str:

    '''
    Changes the coordinator. If new_coord_inst is unspecified (for a remove-coord call) then a slave is selected
    to be promoted as a coordinator. Else, a node from this specified type will be created and inserted as a coordinator
    :param mpc_id:

    :return:
    '''



    repositoryParamount = ParamountClusterRepositoryOperations()
    _cluster = _cluster = validate_and_get_cluster(mpc_id)
    tag_module = PlatformFactory.get_module_interface().get_module('tag')
    group_module = PlatformFactory.get_module_interface().get_module('group')
    cluster_module = PlatformFactory.get_module_interface().get_module('cluster')
    node_module = PlatformFactory.get_module_interface().get_module('node')



    validate_cluster_setup(_cluster)


    nodesList = node_module.list_nodes(cluster_module.get_nodes_from_cluster(_cluster.cluster_id) )
    _slaves = [x for x in
               list(filter(lambda x: x.tags['cluster_node_type'][0].split(':')[1] == Info.SLAVES, nodesList))]

    _slaveSize = len(_slaves)

    if new_coord_inst is None and _slaveSize == 0:
        raise ValueError("Cannot remove the single coordinator, there is no slaves nodes to promote! ")

    _slaveType = next(iter(_slaves)).instance_type if _slaveSize > 0 else None


    if new_coord_inst is None:



        #In this case the coord is picked from the slaves
        _newCoord = _slaves[0]
        #slave size invariant kept
        _slaveSize = _slaveSize -1

        group_module.remove_group_from_node(node_ids=[_newCoord.node_id], group='mpi/slave')
        _cluster.slaves.remove(_newCoord.node_id)



    else:
        #TODO criar coord
        created_node = node_module.start_nodes({new_coord_inst:1})
        _newCoord = next(iter(created_node))


        # raise Exception("Removing the only coordinator does not make sense! Just terminate the cluster ")

    jinjaenv = jinja2.Environment(loader=jinja2.FileSystemLoader(os.path.dirname(os.path.abspath(__file__))),
                                  trim_blocks=True, lstrip_blocks=True)


    # template is such that if node_count is zero then node_type needs not to be specified (this whole part is not rendered)
    template = jinjaenv.get_template("mpi-paramount-cluster.j2")
    rendered_template = template.render({'node_type_coord': _newCoord.instance_type, 'node_type': _slaveType, 'node_count': _slaveSize})

    # TODO: checar se eh slave antes de prosseguir

    with tmpdir() as dir:
        filename = path_extend(dir, 'mpi-paramount-cluster.yml')
        with open(filename, 'w') as f:
            f.write(rendered_template)
        data = cluster_module.update_cluster_config([filename],cluster_id=_cluster.cluster_id )




    oldCoordinator = _cluster.coordinator


    # Removes the old coordinator -> remove_tags_from_nodes (from platform)
    _removed = tag_module.node_remove_tag(node_ids=[oldCoordinator],
                                          tags= 'clusters')
    _removed = tag_module.node_remove_tag(node_ids=[oldCoordinator],
                                          tags= 'cluster_node_type')
    #Done twice because node_remove_tag does not allow to pass list, only string
    node_module.stop_nodes([oldCoordinator])

    _cluster.coordinator = None



    # Removes the slave and add as the coordinator


    #print("Adding the new coordinator to the mpi/coordinator group. No setup will be done")

    extra = {}
    extra.update({'mount_ip': _cluster.mount_ip})
    extra.update({'nodes_group_name': _cluster.paramount_id})
    if _cluster.skip_mpi:
        extra.update({'skip_mpi': 'True'})

    if _cluster.no_instance_key:
        extra.update({'use_instance_key': 'False'})


    #If no new node is to be added as coordinator, that is a slave should be promoted as coord, do not run setup (node is already setup)
    if new_coord_inst is None:
        extra.update({'no_setup': 'True'})



    cluster_module.add_existing_nodes_to_cluster(cluster_id=_cluster.cluster_id, node_types={Info.COORDINATOR:[_newCoord.node_id]} )


    # Re-adds as a coordinator:
    cluster_module.cluster_group_add(cluster_id=_cluster.cluster_id,
                                     group_name='mpi/coordinator',
                                     node_ids=[_newCoord.node_id],
                                     extra_args=extra,
                                     re_add_to_group=True
                                     )

    _cluster.coordinator = _newCoord.node_id

    #TODO: remover a tag de slave do novo coordinator
    repositoryParamount.update_paramount(_cluster)

    return _newCoord.node_id



def run_playbook(mpc_id, playbook_file, only_coord=False):
    cluster_module = PlatformFactory.get_module_interface().get_module('cluster')

    _mpcObj = validate_and_get_cluster(mpc_id)
    _nodes = [_mpcObj.coordinator] + _mpcObj.slaves if not only_coord  else [_mpcObj.coordinator]


    cluster_module.execute_playbook(cluster_id= _mpcObj.cluster_id,
                                    playbook_path= playbook_file,
                                    node_ids=_nodes)


def validate_and_get_cluster(mpc_id) -> ParamountClusterData:

    _mpc_id = mpc_id
    repositoryParamount = ParamountClusterRepositoryOperations()

    if mpc_id == Info.LAST_PARAMOUNT:
        _mpc_id = Info.CLUSTER_PREFIX + str(repositoryParamount.get_newest_paramount_id())


    try:
        return next(iter(repositoryParamount.get_paramount_data(_mpc_id)))

    except:
        raise Exception("There is no paramount cluster of id '{}' in the database".format(_mpc_id))


def validate_and_get_job(job_id) -> JobData:

    _job_id = job_id
    repositoryJob = JobDataRepositoryOperations()

    if job_id == Info.LAST_JOB:
        _job_id = Info.JOB_PREFIX + str(repositoryJob.get_newest_paramount_job_id())


    try:
        return next(iter(repositoryJob.get_job_data(_job_id)))

    except:
        raise Exception("There is no job of id '{}' in the database".format(_job_id))

def validate_cluster_setup(cluster_obj):
    if not cluster_obj.isSetup :
        raise Exception("Paramount Cluster `{}´  is not setup, be sure to setup properly the cluster".format(cluster_obj.paramount_id))
