#! /usr/bin/python3

import os
import sys
import json
import yaml

from typing import Tuple, List

from libspits import SimpleEndpoint, messaging

connection_timeout= 15
handshake_timeout = 15


def __perform_job_handshake(job_id: str, host_addr: str, port: str) -> SimpleEndpoint:
    """Create a new Endpoint to the connect to process and perform the handshake with jobid and start communication
    :return: A SimpleEndpoint to connect to the process
    :rtype: SimpleEndpoint
    """
    if not host_addr:
        raise Exception("Invalid host address (`{}`) to perform handshake with jobid: {}".format(
            host_addr, job_id))

    if port <= 0:
        raise Exception("Invalid host port (`{}`) to perform handshake with jobid: {}".format(
            port, job_id))

    try:
        print("Connecting to {}:{}".format(host_addr, port))
        endpoint = SimpleEndpoint(host_addr, port)
        endpoint.Open(connection_timeout)
        print("Connected to `{}:{}`".format(endpoint.address, endpoint.port))
    except Exception as err:
        print("Impossible connect to `{}:{}`: {}".format(host_addr, port, err))
        raise

    try:
        # Job HandShake
        endpoint.WriteString(job_id)
        rec_jobid = endpoint.ReadString(handshake_timeout).strip()
        if job_id != rec_jobid:
            endpoint.Close()
            raise Exception("Job ID mismatch from local process info ('{}') and received response ('{}')".format(
                process.job_id, rec_jobid))
        print("Job handshake for job '{}' was successful".format(job_id))
        return endpoint
    except Exception as err:
        endpoint.Close()
        raise Exception("Error performing job handshake for job `{}`: {}".format(
            job_id, err))

def spits_worker_add(job_id: str, jm_process_tuple: Tuple[str, str], tm_processes: List[Tuple[str, str]]):
    try:
        endpoint = __perform_job_handshake(job_id, jm_process_tuple[0], jm_process_tuple[1])
    except Exception as err:
        print("Error performing handshake for job `{}`: {}".format(job_id, err))
        sys.exit(1)

    success_processes = []
    for tm_process in tm_processes:
        try:
            node = dict(host=tm_process[0], port=tm_process[1])
            node = json.dumps(node)
            endpoint.WriteInt64(messaging.msg_cd_nodes_append)
            endpoint.WriteString(node)
            ret = endpoint.ReadInt64(connection_timeout)
            endpoint.Close()
            print("TaskManager `{}:{}` was added sucessfuly to jobmanager `{}:{}`".format(
                tm_process[0], tm_process[1], jm_process_tuple[0], jm_process_tuple[1]))
            success_processes.append(tm_process)
        except Exception as err:
            endpoint.Close()
            print("Adding worker {}:{} node to jobmanager `{}:{}` list: {}".format(
                tm_process[0], tm_process[0], 
                jm_process_tuple[0], jm_process_tuple[1], err))
            sys.exit(1)

    return success_processes


with open(sys.argv[1], 'r') as f:
    doc = yaml.load(f, Loader=yaml.FullLoader)

jobid = doc['jobid']
jm_proc = next(iter([(node['ip'], node['port']) for node in doc['nodes'] if node['type'] == 'jobmanager']))
tm_procs = [(node['ip'], node['port']) for node in doc['nodes'] if node['type'] == 'taskmanager']
suc_processes = spits_worker_add(jobid, jm_proc, tm_procs)

sys.exit(0) 
