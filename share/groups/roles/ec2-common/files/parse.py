#! /usr/bin/python3

import os
import sys
import yaml

output_file = os.path.expandvars(os.path.expanduser(sys.argv[2]))

jobstatus = dict()
job_values = []
job_id = None
finish = False

for f in os.listdir(sys.argv[1]):
    
    if f.endswith('.out'):
        ip = f[:-4]
        stdout = open(os.path.join(sys.argv[1], f), 'r')

        line = str(stdout.readline()).strip()
        if not line.startswith("Job:"):
            raise Exception("Error querying status. Not a valid output")
        job_id = line.split(":")[1].strip()
        
        jobstatus['jobid'] = job_id
        jobstatus['finished'] = stdout.readline().split(':')[1].strip()

        if jobstatus['finished'] != 1:
            stdout.readline()
            lines = [line.strip() for line in stdout.readlines()]
            nodes = [lines[i:i + 6] for i in range(0, len(lines), 6)]
            for node in nodes:
                if node[2].split(':')[1].strip() == 'jobmanager':
                    finish = False
                    break
                
            jobstatus['nodes'] = [(dict(manager=node[2].split(':')[1].strip(),
                                        type=node[1].split(':')[1].strip(),
                                        address=node[3].split(':')[1].strip(),
                                        port=int(node[4].split(':')[1].strip()),
                                        pid=int(node[5].split(':')[1].strip()))) 
                                        for node in nodes]
        else:
            finish = True
                                        
        for job in jobstatus['nodes']:
            job_values.append(dict(ip=ip, port=job['port'], pid=job['pid'], type=job['manager']))

jobstatus = dict()
jobstatus['jobid'] = job_id
jobstatus['finished'] = 1 if finish else 0
jobstatus['nodes'] = job_values

with open(output_file, 'w') as f:
    yaml.dump(jobstatus, f)
    
print(jobstatus)

sys.exit(0)
