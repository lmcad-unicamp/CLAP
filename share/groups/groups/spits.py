playbook = 'roles/spits.yml'

actions = ['setup', 'job-create', 'start-jm', 'start-tm', 'job-status', 'job-add-worker']
hosts = ['jobmanager', 'taskmanager']
