# Ansible playbook describing the setup
actions = {
    'setup': ['update_sys.yml'],
    'reboot': ['reboot.yml'],
    'copy': ['simple-copy-to-remote.yml'],
    'fetch': ['simple-fetch-from-remote.yml'],
    'script': ['run-script.yml'],
    'command': ['run-command.yml']
}
