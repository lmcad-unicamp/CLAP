import json
import os.path
import time
from io import StringIO
from typing import List, Dict

from libspits import SimpleEndpoint, messaging
from paramiko import SSHClient

from clap.common.config import Defaults
from clap.common.factory import PlatformFactory
from clap.common.platform import MultiInstanceAPI
from clap.common.utils import log
from .repository import SpitsProcessInfo, SpitsRepositoryOperations, SpitsJobInfo

repository_name = os.path.join(Defaults.storage_path, 'spits_db.json')
connection_timeout = 30
handshake_timeout = 15


def __validate_playbook(playbook_path: str) -> str:
    playbook_path = os.path.expanduser(os.path.expandvars(playbook_path))
    if not os.path.isfile(playbook_path):
        raise OSError("Invalid playbook at `{}`".format(playbook_path))
    return playbook_path


def __register_installation(node_ids: List[str]):
    return SpitsRepositoryOperations(repository_name).register_installed(node_ids)


def __check_installed(node_ids: List[str]):
    return SpitsRepositoryOperations(repository_name).check_installed(node_ids)


def __deregister_installation(node_ids: List[str]):
    return SpitsRepositoryOperations(repository_name).deregister_installation(node_ids)


def spits_install(node_ids: List[str], spits_src: str):
    playbook = __validate_playbook(os.path.join(Defaults.share_playbooks, 'spits', 'spits_install.yml'))
    installeds = PlatformFactory.get_instance_api().execute_playbook_in_nodes(node_ids, playbook, spits_src=spits_src)
    __register_installation([node_id for node_id, installed in installeds.items() if installed])
    return installeds


def spits_check(node_ids: List[str]):
    return __check_installed(node_ids)


def spits_uninstall(node_ids: List[str], *args, **kwargs):
    playbook = __validate_playbook(os.path.join(Defaults.share_playbooks, 'spits', 'spits_uninstall.yml'))
    uninstalleds = PlatformFactory.get_instance_api().execute_playbook_in_nodes(node_ids, playbook, *args, **kwargs)
    __deregister_installation([node_id for node_id, uninstalled in uninstalleds.items() if uninstalled])
    return uninstalleds


def __perform_job_handshake(process: SpitsProcessInfo) -> SimpleEndpoint:
    """Create a new Endpoint to the connect to process and perform the handshake with jobid and start communication

    :return: A SimpleEndpoint to connect to the process
    :rtype: SimpleEndpoint
    """
    if not process.host_addr:
        raise Exception("Invalid host address (`{}`) to perform handshake with jobid: {}".format(
            process.host_addr, process.job_id))

    if process.port <= 0:
        raise Exception("Invalid host port (`{}`) to perform handshake with jobid: {}".format(
            process.port, process.job_id))

    try:
        endpoint = SimpleEndpoint(process.host_addr, process.port)
        endpoint.Open(connection_timeout)
        log.debug("Connected to `{}:{}`".format(endpoint.address, endpoint.port))
    except Exception as err:
        log.error("Impossible connect to `{}:{}`: {}".format(process.host_addr, process.port, err))
        raise

    try:
        # Job HandShake
        endpoint.WriteString(process.job_id)
        jobid = endpoint.ReadString(handshake_timeout).strip()
        if process.job_id != jobid:
            endpoint.Close()
            raise Exception("Job ID mismatch from local process info ('{}') and received response ('{}')".format(
                process.job_id, jobid))
        log.info("Job handshake for job '{}' was successful".format(process.job_id))
        return endpoint
    except Exception as err:
        endpoint.Close()
        raise Exception("Error performing job handshake for job '{}' in process `{}`: {}".format(
            process.job_id, process.process_id, err))


def __query_job_status(job_id: str, remote_exec_path: str, ssh: SSHClient):
    """ Query the status of a running job in a node. The status runs the spits-job-status and cat the resulting string.

    :param job_id: ID of the job the perform the query
    :type job_id: str
    :param remote_exec_path: Path with spits scripts to run
    :type remote_exec_path: str
    :param ssh: Connected SSH Client with the node to execute commands
    :type ssh: SSHClient
    :return: The job status dictionary containing:
    - finished: 0 if job was not terminated 1 otherwise
    - nodes:
        - manager: 'jobmanager' or 'taskmanager'
        - type: 'node'
        - address: IP Address of the node
        - port: Port of the node
        - pid: PID of the process in node
    :rtype: dict
    """
    query_command = "{}/bin/spits-job-status {}".format(remote_exec_path, job_id)

    try:
        _, stdout, stderr = ssh.exec_command(query_command)
        stdout = StringIO(stdout.read().decode('utf-8'))

        line = str(stdout.readline()).strip()
        if not line.startswith("Job: {}".format(job_id)):
            raise ValueError("Error querying status from job `{}`".format(job_id))

        jobstatus = dict(jobid=job_id)
        jobstatus['finished'] = stdout.readline().split(':')[1].strip()

        if jobstatus['finished'] != 1:
            stdout.readline()
            lines = [line.strip() for line in stdout.readlines()]
            nodes = [lines[i:i + 6] for i in range(0, len(lines), 6)]
            jobstatus['nodes'] = [(dict(manager=node[1].split(':')[1].strip(),
                                        type=node[2].split(':')[1].strip(),
                                        address=node[3].split(':')[1].strip(),
                                        port=int(node[4].split(':')[1].strip()),
                                        pid=int(node[5].split(':')[1].strip()))) for node in nodes]
        ssh.close()
        return jobstatus
    except Exception as err:
        log.error("Error querying job status: {}".format(err))
        ssh.close()
        return {}


def __is_process_alive(process: SpitsProcessInfo) -> bool:
    """ Establishes a connection to the process and send a heartbeat (to query if it is alive)

    :param process: Process to query information
    :type process: SpitsProcessInfo

    :return: True if heartbeat is successed (node is alive) false otherwise
    :rtype: bool
    """
    try:
        endpoint = __perform_job_handshake(process)
    except Exception as err:
        log.error("Error querying if process `{}` is alive: {}".format(process.process_id, err))
        return False

    try:
        endpoint.WriteInt64(messaging.msg_send_heart)
    except Exception as err:
        endpoint.Close()
        log.error("Error querying if process `{}` is alive: {}".format(process.process_id, err))
        return False
    finally:
        endpoint.Close()
        return True


def __bind_process_ports(job: SpitsJobInfo, processes: List[SpitsProcessInfo], instance_api: MultiInstanceAPI):
    nodes = set(p.node_id for p in processes)
    nodes_proc_map = {
        node_id: [p for p in processes if p.node_id == node_id]
        for node_id in nodes
    }

    jm_processes = [p for p in processes if p.manager_type == SpitsProcessInfo.SPITS_JM]
    tm_processes = [p for p in processes if p.manager_type == SpitsProcessInfo.SPITS_TM]

    sshs = instance_api.get_connection_to_nodes(list(nodes))
    binded_nodes = []

    for node_id, proc_list in nodes_proc_map.items():
        if sshs[node_id] is None:
            log.error("Problems establishing connection to `{}`. Check if the node is alive and reachable".format(
                node_id))
            continue

        status = __query_job_status(job.job_id, '${HOME}/spits/', sshs[node_id])

        if not status:
            log.error("Error querying job status for node `{}`".format(node_id))
            continue

        if status['finished'] != 1:
            # Not binded processes
            jm_node_proc = [p for p in jm_processes if p.node_id == node_id and p.port == 0]
            tm_node_proc = [p for p in tm_processes if p.node_id == node_id and p.port == 0]
            jm_running_nodes = [p for p in status['nodes'] if p['manager'] == SpitsProcessInfo.SPITS_JM]
            tm_running_nodes = [p for p in status['nodes'] if p['manager'] == SpitsProcessInfo.SPITS_TM]

            for jm_node in jm_node_proc:
                try:
                    running = jm_running_nodes.pop()
                    jm_node.port = running['port']
                    jm_node.pid = running['pid']
                    jm_node.status = 'binded'
                    binded_nodes.append(jm_node)
                except Exception as err:
                    log.error("Some JM processes may not be running anymore! {}".format(err))
                    continue

            for tm_node in tm_node_proc:
                try:
                    running = tm_running_nodes.pop()
                    tm_node.port = running['port']
                    tm_node.pid = running['pid']
                    tm_node.status = 'binded'
                    binded_nodes.append(tm_node)

                except Exception as err:
                    log.error("Some TM processes may not be running anymore! {}".format(err))
                    continue

    return binded_nodes


def spits_job_create(job_id: str,  job_conf_path: str, node_ids: List[str]) -> SpitsJobInfo:
    playbook = __validate_playbook(os.path.join(
        Defaults.share_playbooks, 'spits', 'spits_job_create.yml'))

    if not __check_installed(node_ids):
        raise Exception("SPITS are not installed in all nodes")

    repository_operations = SpitsRepositoryOperations(repository_name)
    platform = PlatformFactory.get_instance_api()

    # Get job or create a new one
    try:
        job = repository_operations.get_job(job_id)
    except Exception:
        with open(job_conf_path, 'r') as fp:
            job = SpitsJobInfo(**json.load(fp))

    job.job_id = job_id

    log.info("Creating job `{}` based on `{}` in nodes `{}`".format(
        job.job_id, job.job_name, ', '.join(node_ids)))
    # Execute playbook in nodes with parameters passed. The key-value parameters are replaced in ansible file
    executed_nodes = platform.execute_playbook_in_nodes(
        node_ids,
        playbook,
        job_id="{}".format(job.job_id),
        job_name="{}".format(job.job_name),
        spits_binary_path="{}".format(job.spits_binary_path),
        spits_binary="{}".format(os.path.basename(job.spits_binary_path)),
        spits_args="{}".format(job.spits_binary_args)
    )

    # Get successfully executed nodes (nodes with status = True)
    nodes = [node for node, status in executed_nodes.items() if status]
    if len(nodes) == 0:
        raise Exception("It was unable to start job `{}` based on `{}`"
                        "in any node! Job discarded!".format(job.job_id, job.job_name))

    elif len(nodes) != len(executed_nodes):
        log.error("Only {} nodes reported success to create job `{}`"
                  "Nodes are: {}".format(len(nodes), job.job_id, ', '.join(nodes)))
    else:
        log.info("All nodes reported success creating job `{}`".format(job.job_id))

    # Append job to nodes
    job.nodes = list(set(job.nodes + nodes))
    repository_operations.save_or_update_job(job)

    return job


# TODO must remove spits entries when nodes does not exists anymore
def spits_job_list(job_ids: List[str] = None) -> List[SpitsJobInfo]:
    if not job_ids:
        return SpitsRepositoryOperations(repository_name).get_jobs()
    return SpitsRepositoryOperations(repository_name).get_jobs(job_ids)


def spits_job_status(job_id: str):
    repository = SpitsRepositoryOperations(repository_name)
    platform = PlatformFactory.get_instance_api()

    try:
        processes = repository.get_processes_by_job([job_id])
    except Exception as err:
        raise Exception("Invalid job `{}`: {}".format(job_id, err))

    try:
        jm_process = [process for process in processes if process.manager_type == process.SPITS_JM][0]
    except Exception as err:
        raise Exception("No job manager found for job `{}`: {}".format(job_id, err))

    ssh_client = platform.get_connection_to_nodes([jm_process.node_id])[jm_process.node_id]
    if not ssh_client:
        raise Exception("Problems establishing connection to `{}`. Check if the node is alive and reachable".format(
            jm_process.node_id))
    return __query_job_status(job_id, '${HOME}/spits/', ssh_client)


def spits_job_copy(job_id: str, dest: str):
    playbook = __validate_playbook(os.path.join(Defaults.share_playbooks, 'spits', 'spits_job_copy.yml'))
    repository = SpitsRepositoryOperations(repository_name)
    platform = PlatformFactory.get_instance_api()

    try:
        processes = repository.get_processes_by_job([job_id])
    except Exception as err:
        raise Exception("Invalid job `{}`: {}".format(job_id, err))

    try:
        jm_process = [process for process in processes if process.manager_type == process.SPITS_JM][0]
    except Exception as err:
        raise Exception("No job manager found for job `{}`: {}".format(job_id, err))

    return platform.execute_playbook_in_nodes([jm_process.node_id], playbook, job_id=job_id, destination=dest)[jm_process.node_id]


# TODO Implement method job_stop
def spits_job_stop(job_id: str):
    playbook = __validate_playbook(os.path.join(Defaults.share_playbooks, 'spits', 'spits_job_stop.yml'))
    repository = SpitsRepositoryOperations(repository_name)
    platform = PlatformFactory.get_instance_api()

    try:
        job = repository.get_job(job_id)
        processes = repository.get_processes_by_job([job_id])
    except Exception as err:
        raise Exception("Invalid job `{}`: {}".format(job_id, err))

    nodes = list(set([process.node_id for process in processes]))
    executed_nodes = platform.execute_playbook_in_nodes(nodes, playbook, job_id=job_id)

    job_remove = True

    for node_id, executed in executed_nodes.items():
        if not executed:
            job_remove = False
            continue

        process_nodes = [p for p in processes if p.node_id == node_id]
        for p in process_nodes:
            repository.remove_process(p.process_id)
            log.info("Removing process `{}` attached to job `{}` in node `{}`".format(p.process_id, job_id, node_id))

        job.nodes.remove(node_id)
        log.info("Removed node `{}` for job `{}`".format(node_id, job_id))
        repository.save_or_update_job(job)

    if job_remove:
        repository.remove_job(job_id)
        log.info("Removed job `{}`".format(job_id))
        return True

    log.error("Not all processes are removed! Job `{}` still in db".format(job_id))
    return False



def spits_process_start_jm(jobid: str, node_ids: List[str]):
    playbook = __validate_playbook(os.path.join(
        Defaults.share_playbooks, 'spits', 'spits_jobmanager_start.yml'))

    if not __check_installed(node_ids):
        raise Exception("SPITS are not installed in all nodes")

    repository_operations = SpitsRepositoryOperations(repository_name)
    platform = PlatformFactory.get_instance_api()
    job = repository_operations.get_job(jobid)

    if not job:
        raise Exception("Invalid job with id `{}`".format(jobid))

    control = repository_operations.get_control_info()
    if not all(node in job.nodes for node in node_ids):
        raise Exception("Not all nodes have created job `{}`".format(job.job_id))

    executed_nodes = platform.execute_playbook_in_nodes(node_ids, playbook, job_id=job.job_id)

    ok_executed_nodes = [node for node, status in executed_nodes.items() if status]
    ips = {node.node_id: node.ip for node in platform.get_nodes(ok_executed_nodes)}

    if len(ok_executed_nodes) == 0:
        raise Exception("No nodes have returned success when starting a job manager for job `{}`".format(job.job_id))
    elif len(ok_executed_nodes) != len(executed_nodes):
        log.info("Only nodes {} reported success creating job managers".format(ok_executed_nodes))
    else:
        log.info("All nodes reported success when creating job managers")

    processes = []
    for node in ok_executed_nodes:
        process_id = "process-{}".format(control.process_idx)
        control.process_idx += 1

        process = SpitsProcessInfo(
            process_id=process_id,
            job_id=job.job_id,
            node_id=node,
            creation_time=time.time(),
            update_time=time.time(),
            host_addr=ips[node],
            port=0,
            status='unbinded',
            manager_type=SpitsProcessInfo.SPITS_JM,
            jm_args=job.jm_args
        )

        repository_operations.save_or_update_process(process)
        repository_operations.update_control_info(control)
        processes.append(process)

    binded_processes = __bind_process_ports(job, processes, platform)

    for binded_process in binded_processes:
        repository_operations.save_or_update_process(binded_process)

    if len(binded_processes) != len(processes):
        log.info("Some processes may not be running anymore. {} of {} were successfully binded".format(
                 len(binded_processes), len(processes)))

    for binded_process in binded_processes:
        if __is_process_alive(binded_process):
            binded_process.status = 'reachable'

        repository_operations.save_or_update_process(binded_process)

    return binded_processes


def spits_process_start_tm(jobid: str, node_ids: List[str]):
    playbook = __validate_playbook(os.path.join(
        Defaults.share_playbooks, 'spits', 'spits_taskmanager_start.yml'))

    if not __check_installed(node_ids):
        raise Exception("SPITS are not installed in all nodes")

    repository_operations = SpitsRepositoryOperations(repository_name)
    platform = PlatformFactory.get_instance_api()
    job = repository_operations.get_job(jobid)

    if not job:
        raise Exception("Invalid job with id `{}`".format(jobid))

    control = repository_operations.get_control_info()
    if not all(node in job.nodes for node in node_ids):
        raise Exception("Not all nodes have created job `{}`".format(job.job_id))

    executed_nodes = platform.execute_playbook_in_nodes(node_ids, playbook, job_id=job.job_id)

    ok_executed_nodes = [node for node, status in executed_nodes.items() if status]
    ips = {node.node_id: node.ip for node in platform.get_nodes(ok_executed_nodes)}

    if len(ok_executed_nodes) == 0:
        raise Exception("No nodes have returned success when starting a task manager for job `{}`".format(job.job_id))
    elif len(ok_executed_nodes) != len(executed_nodes):
        log.info("Only nodes {} reported success creating task managers".format(ok_executed_nodes))
    else:
        log.info("All nodes reported success when creating task managers")

    processes = []
    for node in ok_executed_nodes:
        process_id = "process-{}".format(control.process_idx)
        control.process_idx += 1

        process = SpitsProcessInfo(
            process_id=process_id,
            job_id=job.job_id,
            node_id=node,
            creation_time=time.time(),
            update_time=time.time(),
            host_addr=ips[node],
            port=0,
            status='unbinded',
            manager_type=SpitsProcessInfo.SPITS_TM,
            jm_args=job.jm_args
        )

        repository_operations.save_or_update_process(process)
        repository_operations.update_control_info(control)
        processes.append(process)

    binded_processes = __bind_process_ports(job, processes, platform)

    for binded_process in binded_processes:
        repository_operations.save_or_update_process(binded_process)

    if len(binded_processes) != len(processes):
        log.info("Some processes may not be running anymore. {} of {} were successfully binded".format(
                 len(binded_processes), len(processes)))

    for binded_process in binded_processes:
        if __is_process_alive(binded_process):
            binded_process.status = 'reachable'

        repository_operations.save_or_update_process(binded_process)

    return binded_processes


def spits_process_terminate(process_id: str):
    """ Terminate the process

    :return: True on success, False otherwise
    :rtype: bool
    """
    repository_operations = SpitsRepositoryOperations(repository_name)
    process = repository_operations.get_process(process_id)

    try:
        endpoint = __perform_job_handshake(process)
    except Exception as err:
        log.error("Error terminating if process `{}`: {}".format(process.process_id, err))
        return False

    try:
        endpoint.WriteInt64(messaging.msg_terminate)
        endpoint.Close()
    except Exception as err:
        endpoint.Close()
        log.warning("Terminating process `{}`: {}".format(process.process_id, err))
        return False
    finally:
        endpoint.Close()

    # Send heartbeats to see if really terminated
    retries = 3
    for retries in range(0, retries):
        try:
            endpoint = __perform_job_handshake(process)
            endpoint.Close()
        except Exception:
            log.debug("Terminated process {}".format(process.process_id))
            repository_operations.remove_process(process_id)
            return True

    log.warning("The process `{}` still connectable ({} retries). "
                "Cannot know if it really shutdown!".format(process.process_id, retries))
    return True


def spits_process_list(process_ids=None) -> List[SpitsProcessInfo]:
    if not process_ids:
        return SpitsRepositoryOperations(repository_name).get_processes()

    process_ids = list(set(process_ids))
    processes = SpitsRepositoryOperations(repository_name).get_processes(process_ids)
    if len(process_ids) != len(processes):
        raise Exception("Invalid processes with ids: `{}`".format(', '.join(
            set(process_ids).difference([process.process_id for process in processes]))))

    return processes


def spits_processes_alive(process_ids: List[str]) -> Dict[str, bool]:
    return {p.process_id: __is_process_alive(p)
            for p in SpitsRepositoryOperations(repository_name).get_processes(process_ids)}


def spits_worker_list(process_id: str):
    """ Get the list of worker_list that the job manager is communicating

    :param process_id: ProcessID to query information
    :type process_id: str

    :return: Dictionary with the worker nodes
    :rtype: dict
    """
    repository = SpitsRepositoryOperations(repository_name)
    jm_process = repository.get_process(process_id)

    if jm_process.manager_type != SpitsProcessInfo.SPITS_JM:
        raise Exception("Can query the worker list only of job manager processes")

    try:
        endpoint = __perform_job_handshake(jm_process)
    except Exception as err:
        raise Exception("Error performing handshake for process `{}`: {}".format(process_id, err))

    try:
        endpoint.WriteInt64(messaging.msg_cd_nodes_list)
        worker_list = endpoint.ReadString(connection_timeout)
        endpoint.Close()
        return json.loads(worker_list)
    except Exception as err:
        endpoint.Close()
        raise Exception("Error querying worker_list list of process `{}`: {}".format(jm_process.process_id, err))


def spits_worker_add(process_id: str, tm_process_ids: List[str]):
    repository = SpitsRepositoryOperations(repository_name)
    jm_process = repository.get_process(process_id)
    tm_processes = repository.get_processes(tm_process_ids)

    try:
        endpoint = __perform_job_handshake(jm_process)
    except Exception as err:
        raise Exception("Error performing handshake for process `{}`: {}".format(process_id, err))

    success_processes = []
    for tm_process in tm_processes:
        try:
            node = dict(host=tm_process.host_addr, port=tm_process.port)
            node = json.dumps(node)
            endpoint.WriteInt64(messaging.msg_cd_nodes_append)
            endpoint.WriteString(node)
            ret = endpoint.ReadInt64(connection_timeout)
            endpoint.Close()
            log.info("Process `{}` ({}:{}) was added sucessfuly to process {}".format(
                tm_process.process_id, tm_process.host_addr, tm_process.port, jm_process.process_id))
            success_processes.append(tm_process.process_id)
        except Exception as err:
            endpoint.Close()
            log.error("Adding worker {}:{} node to process `{}` list: {}".format(
                tm_process.host_addr, tm_process.port, jm_process.process_id, err))

    return success_processes


# TODO: Review method
def spits_worker_remove(process_id: str, tm_process_ids: List[str]):
    repository = SpitsRepositoryOperations(repository_name)
    jm_process = repository.get_process(process_id)
    tm_processes = repository.get_processes(tm_process_ids)

    try:
        endpoint = __perform_job_handshake(jm_process)
    except Exception as err:
        raise Exception("Error performing handshake for process `{}`: {}".format(process_id, err))

    for tm_process in tm_processes:
        try:
            node = dict(host=tm_process.host_addr, port=tm_process.port)
            node = json.dumps(node)
            endpoint.WriteInt64(messaging.msg_cd_nodes_remove)
            endpoint.WriteString(node)
            ret = endpoint.ReadInt64(connection_timeout)
            print("RET VAL = {}".format(ret))
            endpoint.Close()
            log.info("Process `{}` ({}:{}) removed sucessfuly from process {}".format(
                tm_process.process_id, tm_process.host_addr, tm_process.port, jm_process.process_id))

        except Exception as err:
            endpoint.Close()
            log.error("Error removing worker {}:{} node from process `{}` list: {}".format(
                tm_process.host_addr, tm_process.port, jm_process.process_id, err))

    return


def spits_metrics_list(process_id: str):
    """ Query the list of metrics of the underlying process

    :param process_id: Id of the process to query information
    :type process_id: str

    :return: Dictionary with the metrics list
    :rtype: dict
    """
    repository = SpitsRepositoryOperations(repository_name)
    process = repository.get_process(process_id)

    try:
        endpoint = __perform_job_handshake(process)
    except Exception as err:
        raise Exception("Querying metrics list from process `{}`: {}".format(process.process_id, err))

    try:
        endpoint.WriteInt64(messaging.msg_cd_query_metrics_list)
        metrics_list = endpoint.ReadString(connection_timeout)
        if not metrics_list:
            endpoint.Close()
            raise Exception("Querying metrics list for process `{}`: "
                            "Received empty string".format(process.process_id))
        return json.loads(metrics_list)
    except Exception:
        raise


def spits_metrics_values(process_id: str, metrics: List[str]):
    repository = SpitsRepositoryOperations(repository_name)
    process = repository.get_process(process_id)

    try:
        endpoint = __perform_job_handshake(process)
    except Exception as err:
        raise Exception("Querying metrics values from process `{}`: {}".format(process.process_id, err))

    try:
        metrics_list = dict(metrics=[{"name": metric} for metric in metrics])
        metrics_list = json.dumps(metrics_list)
        endpoint.WriteInt64(messaging.msg_cd_query_metrics_last_values)
        endpoint.WriteString(metrics_list)
        metrics_last_values = endpoint.ReadString(connection_timeout)
        if not metrics_last_values:
            endpoint.Close()
            raise Exception("Querying metrics list for process `{}`: "
                            "Received empty string".format(process.process_id))
        endpoint.Close()
        return json.loads(metrics_last_values)

    except Exception:
        raise
