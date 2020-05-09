#!/usr/bin/env python3

import os
import sys

if len(sys.argv) != 3:
    print("Usage: {} nodes_path hostname".format(sys.argv[0]))
    sys.exit(1)
    
input_path = sys.argv[1]
hostname = sys.argv[2]

for filename in os.listdir(input_path):
    data = []    
    filepath = os.path.expandvars(os.path.expanduser(os.path.join(input_path, filename)))
    with open(filepath, 'r') as f:
        for l in f.readlines():
            if not l.startswith('node '):
                data.append(l)
                continue
            port = l.split(' ')[1].split(':')[-1]
            data.append('node {}:{}'.format(hostname, port))
    with open(filepath, 'w') as f:
        f.writelines(data)

sys.exit(0)
