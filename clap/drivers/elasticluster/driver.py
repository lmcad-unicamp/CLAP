import configparser
import json
import logging
import os.path
import platform
import shlex
import tempfile
from collections import defaultdict
from datetime import datetime
from subprocess import call
from time import time
from typing import Optional, List, Dict, Set, Tuple, Union, Any

import elasticluster.conf
import paramiko
import yaml
from elasticluster import Cluster
from elasticluster.cluster import Node
from elasticluster.providers.ansible_provider import AnsibleSetupProvider
from elasticluster.utils import get_num_processors, temporary_dir, parse_ip_address_and_port
from paramiko import SSHClient
from pkg_resources import resource_filename

from clap.common.cluster_repository import RepositoryOperations, ClusterInfo, NodeInfo
from clap.common.config import Defaults, ConfigReader
from clap.common.driver import AbstractInstanceInterface, Codes
from clap.common.utils import path_extend, log


# TODO remove absolute path from elasticluster config and use relative
# TODO invalid provider credentials --> Remove cluster...
# TODO update cluster config every time a new node is instantiated?


class ElasticCreator:
    @staticmethod
    def create_cluster_obj(cluster_name: str,
                           provider_config: dict,
                           login_config: dict,
                           instances: dict,
                           login_name: str,
                           provider_name: str,
                           storage_path: str = Defaults.elasticluster_storage_path,
                           storage_type: str = Defaults.DEFAULT_CONF_TYPE) -> Cluster:

        eclust_config = ElasticCreator.__to_elasticluster_config(cluster_name, instances, login_config,
                                                                 provider_config, login_name, provider_name)
        config = configparser.ConfigParser()
        config.update(eclust_config)

        with tempfile.TemporaryDirectory(suffix='.d') as directory:
            with open('{}/cluster.conf'.format(directory), 'w') as configfile:
                config.write(configfile)

            configfiles = elasticluster.conf._expand_config_file_list([directory[:-2]])
            raw_config = elasticluster.conf._read_config_files(configfiles)
            tree_config1 = elasticluster.conf._arrange_config_tree(raw_config)
            tree_config2 = elasticluster.conf._perform_key_renames(tree_config1)
            complete_config = elasticluster.conf._build_node_section(tree_config2)
            object_tree = elasticluster.conf._validate_and_convert(complete_config)
            deref_config = elasticluster.conf._dereference_config_tree(object_tree)
            final_config = elasticluster.conf._cross_validate_final_config(deref_config)
            creator = elasticluster.conf.Creator(final_config, storage_path=storage_path, storage_type=storage_type)
            cluster = creator.create_cluster("{}".format(cluster_name), cluster_name)
            cluster.repository.save_or_update(cluster)

            with open('{}/{}.conf'.format(storage_path, cluster_name), 'w') as configfile:
                config.write(configfile)

            with open('{}/init-conf-{}.json'.format(storage_path, cluster_name), 'w') as file:
                data = {'provider': provider_config, 'login': login_config, 'instances': instances}
                json.dump(data, file)

            return cluster

    @staticmethod
    def update_cluster_config(cluster_name: str,
                              provider_config: dict,
                              login_config: dict,
                              instances: dict,
                              login_name: str,
                              provider_name: str,
                              storage_path: str = Defaults.elasticluster_storage_path,
                              storage_type: str = Defaults.DEFAULT_CONF_TYPE):
        eclust_config = ElasticCreator.__to_elasticluster_config(cluster_name, instances, login_config, provider_config,
                                                                 login_name, provider_name)
        config = configparser.ConfigParser()
        config.update(eclust_config)
        with open('{}/{}.conf'.format(storage_path, cluster_name), 'w') as configfile:
            config.write(configfile)

        with open('{}/init-conf-{}.json'.format(storage_path, cluster_name), 'w') as file:
            data = {'provider': provider_config, 'login': login_config, 'instances': instances}
            json.dump(data, file)

    @staticmethod
    def upddate_cluster_node(cluster: Cluster, node: Node):
        for n in cluster.nodes[node.kind]:
            if n.name == node.name:
                cluster.nodes[node.kind].remove(n)

        cluster.nodes[node.kind].append(node)
        cluster.repository.save_or_update(cluster)


    @staticmethod
    def __to_elasticluster_config(cluster_name: str, instances: Dict[str, Any], login_configs: Dict[str, Any],
                                  provider_configs: Dict[str, Any], login_name: str, provider_name: str):
        # Transform to elasticluster config
        eclust_config = dict()
        cluster_section = "cluster/{}".format(cluster_name)
        cloud_section = "cloud/{}".format(cluster_name)
        login_section = "login/{}".format(cluster_name)
        setup_section = "setup/setup-{}".format(cluster_name)

        # --------------------- Parse AWS cloud ---------------------------
        if provider_configs['provider'] == 'aws':
            key_renames = {
                ('access_keyfile', 'ec2_access_key'),
                ('secret_access_keyfile', 'ec2_secret_key'),
                ('url', 'ec2_url'),
                ('region', 'ec2_region')
            }
            eclust_config[cloud_section] = {
                'provider': 'ec2_boto',
            }
            for key, val in key_renames:
                eclust_config[cloud_section][val] = provider_configs[key]

            eclust_config[cloud_section]['ec2_access_key'] = path_extend(
                Defaults.private_path, eclust_config[cloud_section]['ec2_access_key'])

            if not os.path.isfile(eclust_config[cloud_section]['ec2_access_key']):
                raise ValueError(
                    "Invalid access key file at `{}`".format(eclust_config[cloud_section]['ec2_access_key']))
            eclust_config[cloud_section]['ec2_access_key'] = open(
                eclust_config[cloud_section]['ec2_access_key']).read().strip()
            eclust_config[cloud_section]['ec2_secret_key'] = path_extend(
                Defaults.private_path, eclust_config[cloud_section]['ec2_secret_key'])
            if not os.path.isfile(eclust_config[cloud_section]['ec2_secret_key']):
                raise ValueError(
                    "Invalid secret key file at `{}`".format(eclust_config[cloud_section]['ec2_secret_key']))

            eclust_config[cloud_section]['ec2_secret_key'] = open(
                eclust_config[cloud_section]['ec2_secret_key']).read().strip()

            other_valid_provider_keys = ['vpc']
            for valid_key in other_valid_provider_keys:
                if valid_key in provider_configs:
                    eclust_config[cloud_section][valid_key] = provider_configs[valid_key]

        else:
            raise ValueError("Invalid provider `{}`".format(provider_configs['provider']))

        # -----------------------------------------------------------------
        # --------------------- Parse Login -------------------------------
        key_renames = {
            ('user', 'image_user'),
            ('keypair_name', 'user_key_name'),
            ('keypair_public_file', 'user_key_public'),
            ('keypair_private_file', 'user_key_private'),
            ('sudo', 'image_sudo'),
            ('sudo_user', 'image_user_sudo')
        }
        eclust_config[login_section] = {
            val: login_configs[key] for key, val in key_renames
        }
        # Update private key files
        eclust_config[login_section]['user_key_public'] = path_extend(
            Defaults.private_path, eclust_config[login_section]['user_key_public'])
        if not os.path.isfile(eclust_config[login_section]['user_key_public']):
            raise ValueError("Invalid public key file at `{}`".format(eclust_config[login_section]['user_key_public']))
        eclust_config[login_section]['user_key_private'] = path_extend(
            Defaults.private_path, eclust_config[login_section]['user_key_private'])
        if not os.path.isfile(eclust_config[login_section]['user_key_private']):
            raise ValueError(
                "Invalid private key file at `{}`".format(eclust_config[login_section]['user_key_private']))

        other_valid_login_keys = []
        for valid_key in other_valid_login_keys:
            if valid_key in login_configs:
                eclust_config[login_section][valid_key] = login_configs[valid_key]

        # ---------------------- Nodes Section ----------------------------
        invalid_nodes = []
        for node, node_config in instances.items():
            if node_config['provider'] != provider_name:
                invalid_nodes.append(node)
                continue

            if node_config['login'] != login_name:
                invalid_nodes.append(node)
                continue

            node_section = "cluster/{}/{}".format(cluster_name, node)
            eclust_config[node_section] = {
                'login': cluster_name
            }

            # This populates all the node keys
            for name, config in node_config.items():
                if name in ('login', 'provider'):
                    pass
                eclust_config[node_section][name] = config

        for node in invalid_nodes:
            instances.pop(node)

        # Cluster Section

        eclust_config[cluster_section] = {
            "{}_nodes".format(node): 0 for node in list(instances.keys())
        }
        eclust_config[cluster_section].update({
            'cloud': "{}".format(cluster_name),
            'login': "{}".format(cluster_name),
            'setup': "setup-{}".format(cluster_name)
        })
        # Setup Section
        eclust_config[setup_section] = {
            "{}_groups".format(node): 'default' for node in list(instances.keys())
        }
        eclust_config[setup_section].update({
            'provider': 'ansible',
            'slow_but_safer': False,
        })
        eclust_config[setup_section].update({"ansible_python_interpreter": "/usr/bin/python3"})
        return eclust_config

    @staticmethod
    def get_all_cluster_objs(storage_path: str = Defaults.elasticluster_storage_path,
                             storage_type: str = 'json'):
        paths = [storage_path[:-2] if storage_path.endswith('.d') else storage_path]
        configfiles = elasticluster.conf._expand_config_file_list(paths)
        raw_config = elasticluster.conf._read_config_files(configfiles)
        tree_config1 = elasticluster.conf._arrange_config_tree(raw_config)
        tree_config2 = elasticluster.conf._perform_key_renames(tree_config1)
        complete_config = elasticluster.conf._build_node_section(tree_config2)
        object_tree = elasticluster.conf._validate_and_convert(complete_config)
        deref_config = elasticluster.conf._dereference_config_tree(object_tree)
        final_config = elasticluster.conf._cross_validate_final_config(deref_config)
        creator = elasticluster.conf.Creator(final_config, storage_path=storage_path, storage_type=storage_type)
        objs = creator.create_repository().get_all()
        return objs

    @staticmethod
    def get_cluster_obj(cluster_name: str, storage_path: str = Defaults.elasticluster_storage_path,
                        storage_type: str = 'json') -> Cluster:
        paths = [storage_path[:-2] if storage_path.endswith('.d') else storage_path]
        configfiles = elasticluster.conf._expand_config_file_list(paths)
        if not configfiles:
            raise Exception("Invalid elasticluster cluster file at `{}` for cluster `{}`".format(
                storage_path, cluster_name))
        raw_config = elasticluster.conf._read_config_files(configfiles)
        tree_config1 = elasticluster.conf._arrange_config_tree(raw_config)
        tree_config2 = elasticluster.conf._perform_key_renames(tree_config1)
        complete_config = elasticluster.conf._build_node_section(tree_config2)
        object_tree = elasticluster.conf._validate_and_convert(complete_config)
        deref_config = elasticluster.conf._dereference_config_tree(object_tree)
        final_config = elasticluster.conf._cross_validate_final_config(deref_config)
        creator = elasticluster.conf.Creator(final_config, storage_path=storage_path, storage_type=storage_type)
        return creator.load_cluster(cluster_name)

    @staticmethod
    def exists_cluster(cluster_name: str, storage_path: str = Defaults.elasticluster_storage_path,
                       storage_type: str = 'json') -> bool:
        try:
            if ElasticCreator.get_cluster_obj(cluster_name, storage_path, storage_type) is not None:
                return True
        except Exception:
            pass

        return False

    @staticmethod
    def get_node_from_cluster(cluster_name: str, node_name: str) -> Node:
        cluster = ElasticCreator.get_cluster_obj(cluster_name)
        if not cluster:
            raise Exception("Invalid elasticluster cluster with name `{}`".format(cluster_name))
        return cluster.get_node_by_name(node_name)

    @staticmethod
    def get_nodes_from_cluster(cluster_name: str, nodes: List[str]) -> List[Node]:
        cluster = ElasticCreator.get_cluster_obj(cluster_name)
        if not cluster:
            raise Exception("Invalid elasticluster cluster with name `{}`".format(cluster_name))
        return [cluster.get_node_by_name(node_name) for node_name in nodes]

    @staticmethod
    def get_final_config(eclasticluster_config_file: str):
        raw_config = elasticluster.conf._read_config_files([eclasticluster_config_file])
        tree_config1 = elasticluster.conf._arrange_config_tree(raw_config)
        tree_config2 = elasticluster.conf._perform_key_renames(tree_config1)
        complete_config = elasticluster.conf._build_node_section(tree_config2)
        object_tree = elasticluster.conf._validate_and_convert(complete_config)
        deref_config = elasticluster.conf._dereference_config_tree(object_tree)
        final_config = elasticluster.conf._cross_validate_final_config(deref_config)
        return final_config


class AnsibleSetupProviderWrapper(AnsibleSetupProvider):
    def __init__(self, ansible_provider: AnsibleSetupProvider,
                 kind_groups_map: Dict[str, List[str]],
                 kind_key_value_vars: Dict[str, Dict[str, str]],
                 node_name_id_map: Dict[str, str]):
        self.__dict__.update(ansible_provider.__dict__)
        self.groups = kind_groups_map
        self.environment = kind_key_value_vars
        self.node_name_id_map = node_name_id_map

    def run_playbook(self, cluster: Cluster, nodes: List[Node], playbook: str,
                     extra_args=tuple()) -> Dict[str, bool]:
        run_id = (
            'elasticluster.{name}.{date}.{pid}@{host}'
                .format(
                name=cluster.name,
                date=datetime.now().isoformat(),
                pid=os.getpid(),
                host=platform.node(),
            )
        )
        inventory_path = self.build_inventory(cluster, nodes)
        if inventory_path is None:
            # no inventory file has been created: this can only happen
            # if no nodes have been started nor can be reached
            raise Exception("No nodes in the inventory!")
        assert os.path.exists(inventory_path), (
            "inventory file `{inventory_path}` does not exist"
                .format(inventory_path=inventory_path))

        # build list of directories to search for roles/include files
        ansible_roles_dirs = [
            # include Ansible default first ...
            '/etc/ansible/roles',
        ]
        for root_path in [
            # ... then ElastiCluster's built-in defaults
            resource_filename('elasticluster', 'share/playbooks'),
            # ... then wherever the playbook is
            os.path.dirname(playbook),
        ]:
            for path in [
                root_path,
                os.path.join(root_path, 'roles'),
            ]:
                if path not in ansible_roles_dirs and os.path.exists(path):
                    ansible_roles_dirs.append(path)

        # Use env vars to configure Ansible;
        # see all values in https://github.com/ansible/ansible/blob/devel/lib/ansible/constants.py
        #
        # Ansible does not merge keys in configuration files: rather
        # it uses the first configuration file found.  However,
        # environment variables can be used to selectively override
        # parts of the config; according to [1]: "they are mostly
        # considered to be a legacy system as compared to the config
        # file, but are equally valid."
        #
        # [1]: http://docs.ansible.com/ansible/intro_configuration.html#environmental-configuration
        #
        # Provide default values for important configuration variables...
        ansible_env = {
            'ANSIBLE_FORKS': ('%d' % 4 * get_num_processors()),
            'ANSIBLE_HOST_KEY_CHECKING': 'no',
            'ANSIBLE_RETRY_FILES_ENABLED': 'no',
            'ANSIBLE_ROLES_PATH': ':'.join(reversed(ansible_roles_dirs)),
            'ANSIBLE_SSH_PIPELINING': 'yes',
            'ANSIBLE_TIMEOUT': '120',
        }
        try:
            import ara
            ara_location = os.path.dirname(ara.__file__)
            ansible_env['ANSIBLE_CALLBACK_PLUGINS'] = (
                '{ara_location}/plugins/callbacks'
                    .format(ara_location=ara_location))
            ansible_env['ANSIBLE_ACTION_PLUGINS'] = (
                '{ara_location}/plugins/actions'
                    .format(ara_location=ara_location))
            ansible_env['ANSIBLE_LIBRARY'] = (
                '{ara_location}/plugins/modules'
                    .format(ara_location=ara_location))
            ara_dir = os.getcwd()
            ansible_env['ARA_DIR'] = ara_dir
            ansible_env['ARA_DATABASE'] = (
                'sqlite:///{ara_dir}/{run_id}.ara.sqlite'
                    .format(ara_dir=ara_dir, run_id=run_id))
            ansible_env['ARA_LOG_CONFIG'] = (
                '{run_id}.ara.yml'
                    .format(ara_dir=ara_dir, run_id=run_id))
            ansible_env['ARA_LOG_FILE'] = (
                '{run_id}.ara.log'
                    .format(ara_dir=ara_dir, run_id=run_id))
            ansible_env['ARA_LOG_LEVEL'] = 'DEBUG'
            ansible_env['ARA_PLAYBOOK_PER_PAGE'] = '0'
            ansible_env['ARA_RESULT_PER_PAGE'] = '0'
        except ImportError:
            log.info(
                "Could not import module `ara`:"
                " no detailed information about the playbook will be recorded.")
        # ...override them with key/values set in the config file(s)
        for k, v in self.extra_conf.items():
            if k.startswith('ansible_'):
                ansible_env[k.upper()] = str(v)
        # ...finally allow the environment have the final word
        ansible_env.update(os.environ)
        # however, this is needed for correct detection of success/failure...
        ansible_env['ANSIBLE_ANY_ERRORS_FATAL'] = 'yes'
        # ...and this might be needed to connect (see issue #567)
        if cluster.ssh_proxy_command:
            ansible_env['ANSIBLE_SSH_ARGS'] = (
                    ansible_env.get('ANSIBLE_SSH_ARGS', '')
                    + (" -o ProxyCommand='{proxy_command}'"
                       # NOTE: in contrast to `Node.connect()`, we must
                       # *not* expand %-escapes in the SSH proxy command:
                       # it will be done by the `ssh` client
                       .format(proxy_command=cluster.ssh_proxy_command)))

        # report on calling environment
        # if __debug__:
        #     elasticluster.log.debug(
        #         "Calling `ansible-playbook` with the following environment:")
        #     for var, value in sorted(ansible_env.items()):
        #         # sanity check. Do not print password content....
        #         if "password" in var.lower() or "secret" in var.lower():
        #             elasticluster.log.debug("- %s=******", var)
        #         else:
        #             elasticluster.log.debug("- %s=%r", var, value)

        log.debug("Using playbook file %s.", playbook)

        # build `ansible-playbook` command-line
        cmd = shlex.split(self.extra_conf.get('ansible_command', 'ansible-playbook'))
        cmd += [
            ('--private-key=' + cluster.user_key_private),
            os.path.realpath(playbook),
            ('--inventory=' + inventory_path),
        ]

        if self._sudo:
            cmd.extend([
                # force all plays to use `sudo` (even if not marked as such)
                '--become',
                # desired sudo-to user
                ('--become-user=' + self._sudo_user),
            ])

        # determine Ansible verbosity as a function of ElastiCluster's
        # log level (we cannot read `ElastiCluster().params.verbose`
        # here, still we can access the log configuration since it's
        # global).
        verbosity = int((logging.WARNING - log.getEffectiveLevel()) / 10)
        if verbosity > 0:
            cmd.append('-' + ('v' * verbosity))  # e.g., `-vv`

        # append any additional arguments provided by users in config file
        ansible_extra_args = self.extra_conf.get('ansible_extra_args', None)
        if ansible_extra_args:
            cmd += shlex.split(ansible_extra_args)

        # finally, append any additional arguments provided on command-line
        for arg in extra_args:
            # XXX: since we are going to change working directory,
            # make sure that anything that looks like a path to an
            # existing file is made absolute before appending to
            # Ansible's command line.  (Yes, this is a ugly hack.)
            if os.path.exists(arg):
                arg = os.path.abspath(arg)
            cmd.append('-e {}'.format(arg))

        with temporary_dir():
            # adjust execution environment, for the part that needs a
            # the current directory path
            cmd += [
                '-e', ('@' + self._write_extra_vars(cluster))
            ]
            # run it!
            cmdline = ' '.join(cmd)
            log.debug(
                "Running Ansible command `%s` ...", cmdline)
            rc = call(cmd, env=ansible_env, bufsize=1, close_fds=True)
            # check outcome
            ok = False  # pessimistic default
            if rc != 0:
                log.error(
                    "Command `%s` failed with exit code %d.", cmdline, rc)
                raise Exception('Command `{}` failed with exit code {}'.format(cmdline, rc))
            else:
                # even if Ansible exited with return code 0, the
                # playbook might still have failed -- so explicitly
                # check for a "done" report showing that each node run
                # the playbook until the very last task
                cluster_hosts = set(node_id for node_id in list(self.node_name_id_map.values()))
                done_hosts = set()
                for node_id in cluster_hosts:
                    try:
                        with open(node_id + '.log') as stream:
                            status = stream.read().strip()
                        if status == 'done':
                            done_hosts.add(node_id)
                    except (OSError, IOError):
                        # no status file for host, do not add it to
                        # `done_hosts`
                        pass

                ok_hosts = {
                    host: (True if host in done_hosts else False)
                    for host in cluster_hosts
                }

                if done_hosts == cluster_hosts:
                    # success!
                    ok = True
                elif len(done_hosts) == 0:
                    # total failure
                    log.error("No host reported successfully running the setup playbook!")
                else:
                    # partial failure
                    log.error(
                        "The following nodes did not report"
                        " successful termination of the setup playbook:"
                        " %s", (', '.join(cluster_hosts - done_hosts)))
        if ok:
            log.info("Nodes correctly configured!")
            # return True
        else:
            log.warning(
                "Nodes have likely *not* been configured correctly.")
            # return False
        return ok_hosts

    def build_inventory(self, cluster: Cluster, nodes: List[Node]):
        inventory_data = defaultdict(list)

        for node in nodes:
            if node.preferred_ip is None:
                log.warning(
                    "Ignoring node `{0}`: No IP address."
                        .format(node.name))
                continue
            if node.kind not in self.groups:
                # FIXME: should this raise a `ConfigurationError` instead?
                log.warning(
                    "Ignoring node `{0}`:"
                    " Node kind `{1}` not defined in cluster!".format(node.name, node.kind))
                continue

            extra_vars = ['ansible_user={}'.format(node.image_user)]

            ip_addr, port = parse_ip_address_and_port(node.preferred_ip)
            if port != 22:
                extra_vars.append('ansible_port=%s' % port)

            # write additional `ansible_*` variables to inventory;
            # `ansible_python_interpreter` gets special treatment
            # since we need to tell script `install-py2.sh` that
            # it should create a wrapper script for running `eatmydata python`
            extra_conf = self.extra_conf.copy()
            ansible_python_interpreter = extra_conf.pop(
                'ansible_python_interpreter', '/usr/bin/python')
            extra_vars.append('ansible_python_interpreter={python}{eatmydata}'
                .format(
                python=ansible_python_interpreter,
                eatmydata=('+eatmydata' if self.use_eatmydata else '')))
            # abuse Python's %r fomat to provide quotes around the
            # value, and \-escape any embedded quote chars
            extra_vars.extend('%s=%r' % (k, str(v)) for k, v in
                              extra_conf.items()
                              if k.startswith('ansible_'))

            if node.kind in self.environment:
                # abuse Python's %r fomat to provide quotes around the
                # value, and \-escape any embedded quote chars
                extra_vars.extend('%s=%r' % (k, str(v)) for k, v in
                                  self.environment[node.kind].items())

            for group in self.groups[node.kind]:
                inventory_data[group].append(
                    (self.node_name_id_map[node.name], ip_addr, ' '.join(extra_vars)))

        if not inventory_data:
            log.info("No inventory file was created.")
            return None

        # create a temporary file to pass to ansible, since the
        # api is not stable yet...
        if self._storage_path_tmp:
            if not self._storage_path:
                self._storage_path = tempfile.mkdtemp()
            elasticluster.log.warning(
                "Writing inventory file to tmp dir `%s`", self._storage_path)

        inventory_path = os.path.join(
            self._storage_path, (cluster.name + '.inventory'))
        log.debug("Writing Ansible inventory to file `%s` ...", inventory_path)
        with open(inventory_path, 'w+') as inventory_file:
            for section, hosts in inventory_data.items():
                # Ansible throws an error "argument of type 'NoneType' is not
                # iterable" if a section is empty, so ensure we have something
                # to write in there
                if hosts:
                    inventory_file.write("\n[" + section + "]\n")
                    for host in hosts:
                        hostline = "{0} ansible_host={1} {2}\n".format(*host)
                        inventory_file.write(hostline)
        return inventory_path

    def _write_extra_vars(self, cluster, filename='extra_vars.yml'):
        # build dict of "extra vars"
        # XXX: we should not repeat here names of attributes that
        # should not be exported... it would be better to use a simple
        # naming convention (e.g., omit whatever starts with `_`)

        extra_vars = cluster.to_vars_dict()
        extra_vars.update(extra_vars.pop('extra', {}))
        extra_vars['cloud'] = cluster.cloud_provider.to_vars_dict()
        nodes = extra_vars.pop('nodes')
        extra_vars['nodes'] = {}
        for kind, instances in nodes.items():
            for node in instances:
                if node.name in self.node_name_id_map:
                    node_vars = node.to_vars_dict()
                    node_vars.update(node_vars.pop('extra', {}))
                    extra_vars['nodes'][self.node_name_id_map[node.name]] = node_vars
        extra_vars['output_dir'] = os.getcwd()
        # save it to a YAML file
        log.debug("Writing extra vars %r to file %s", extra_vars, filename)
        with open(filename, 'w') as output:
            # ensure output file is not readable to other users,
            # as it may contain passwords
            os.fchmod(output.fileno(), 0o600)
            # dump variables in YAML format for Ansible to read
            yaml.dump({'elasticluster': extra_vars }, output)
        return filename


def elaticluster_start_nodes(cluster_name: str, instances_num: Dict[str, int], storage_path: str = Defaults.elasticluster_storage_path,
                             max_concurrent_requests: int = 0) -> Tuple[Cluster, Set[Node]]:
    cluster = ElasticCreator.get_cluster_obj(cluster_name)
    conf = ElasticCreator.get_final_config("{}/{}.conf".format(storage_path, cluster_name))['cluster'][cluster_name]
    # group_names = [group_name[len(cluster_name)+1:] for group_name in conf['nodes'].keys()]
    group_names = list(conf['nodes'].keys())
    node_objs = set()
    invalids = set()

    for node_type, num in instances_num.items():
        if node_type not in group_names:
            invalids.add(node_type)
            continue

        group_conf = conf['nodes'][node_type]
        for varname in ['image_user', 'image_userdata']:
            group_conf.setdefault(varname, conf['login'][varname])

        for i in range(num):
            group_conf.pop('num', 0)
            node_objs.add(cluster.add_node(node_type, **group_conf))

    if invalids:
        raise Exception("Error starting nodes. The some nodes are invalid: `{}`".format(', '.join(invalids)))

    log.info("Starting cluster nodes (timeout: {} seconds) ...".format(cluster.start_timeout))

    if max_concurrent_requests == 0:
        try:
            max_concurrent_requests = 4 * get_num_processors()
        except RuntimeError:
            log.warning(
                "Cannot determine number of processors!"
                " will start nodes sequentially...")
            max_concurrent_requests = 1

    if max_concurrent_requests > 1:
        node_objs = cluster._start_nodes_parallel(node_objs, max_concurrent_requests)
    else:
        node_objs = cluster._start_nodes_sequentially(node_objs)

    # checkpoint cluster state
    cluster.repository.save_or_update(cluster)

    return cluster, node_objs


def elasticluster_check_starting_nodes(cluster: Cluster, node_objs: Set[Node]):
    not_started_nodes = cluster._check_starting_nodes(node_objs, cluster.start_timeout)
    # now that all nodes are up, checkpoint cluster state again
    cluster.repository.save_or_update(cluster)
    # Try to connect to each node to gather IP addresses and SSH host keys
    started_nodes = node_objs.difference(set(not_started_nodes))
    final_nodes = started_nodes.copy()
    if len(started_nodes) != len(node_objs):
        log.error("{} of {} nodes were not successfully started".format(
            len(not_started_nodes), len(node_objs)))
    if not started_nodes:
        return []
    log.info("Checking SSH connection to nodes (timeout: {} seconds) ...".format(cluster.start_timeout))
    final_nodes = final_nodes.difference(cluster._gather_node_ip_addresses(
        started_nodes, cluster.start_timeout, cluster.ssh_probe_timeout))
    # It's possible that the node.connect() call updated the
    # `preferred_ip` attribute, so, let's save the cluster again.
    cluster.repository.save_or_update(cluster)
    return list(final_nodes)


def elasticluster_stop_nodes(cluster_name: str, nodes: List[str], *args, **kwargs) -> None:
    wait = kwargs.get('wait', True)
    cluster = ElasticCreator.get_cluster_obj(cluster_name)
    for node in ElasticCreator.get_nodes_from_cluster(cluster_name, nodes):
        node.stop(wait)
        cluster.nodes[node.kind] = [n for n in cluster.nodes[node.kind] if n.name != node.name]
        cluster.repository.save_or_update(cluster)


def elasticluster_pause_nodes(cluster_name: str, nodes: List[str]) -> None:
    cluster = ElasticCreator.get_cluster_obj(cluster_name)
    for node in ElasticCreator.get_nodes_from_cluster(cluster_name, nodes):
        node.pause()
        cluster.repository.save_or_update(cluster)


def elasticluster_get_connection_to_node(cluster_name: str, node_name: str, *args, **kwargs) -> paramiko.SSHClient:
    keyfile = kwargs.get('keyfile', None)
    timeout = kwargs.get('timeout', 10)
    node = ElasticCreator.get_node_from_cluster(cluster_name, node_name)
    return node.connect(keyfile, timeout)


class ElasticlusterInterface(AbstractInstanceInterface):
    __interface_id__ = 'elasticluster'

    def __init__(self, repository_operator: RepositoryOperations):
        super(ElasticlusterInterface, self).__init__(repository_operator)
        self.cluster_prefix = 'clap'
        self.node_prefix = 'node'

    def __get_updated_cluster(self, cluster_id: str) -> ClusterInfo:
        cluster_info = self.repository_operator.get_cluster(cluster_id)
        reader = ConfigReader(Defaults.cloud_conf, Defaults.login_conf, Defaults.instances_conf)
        provider = reader.get_provider(cluster_info.provider_id)
        login = reader.get_login(cluster_info.login_id)
        instances = reader.get_instances()
        cluster_id = "{}-{}-{}".format(self.cluster_prefix, cluster_info.provider_id, cluster_info.login_id)

        ElasticCreator.update_cluster_config(
            cluster_id, provider, login, instances, cluster_info.login_id, cluster_info.provider_id)

        cluster_info.provider_conf = provider
        cluster_info.login_conf = login
        self.repository_operator.write_cluster_info(cluster_info)

        return cluster_info

    def __get_or_create_cluster(self, cloud_conf: str, login_conf: str) -> ClusterInfo:
        reader = ConfigReader(Defaults.cloud_conf, Defaults.login_conf, Defaults.instances_conf)

        provider = reader.get_provider(cloud_conf)
        login = reader.get_login(login_conf)
        instances = reader.get_instances()
        cluster_id = "{}-{}-{}".format(self.cluster_prefix, cloud_conf, login_conf)

        # TODO If cluster is already created, verify if the config is the same....
        if ElasticCreator.exists_cluster(cluster_id):
            cluster = ElasticCreator.get_cluster_obj(cluster_id)
            ElasticCreator.update_cluster_config(cluster_id, provider, login, instances, login_conf, cloud_conf)
            return self.repository_operator.get_cluster(cluster_id)

        cluster_obj = ElasticCreator.create_cluster_obj(cluster_id, provider, login, instances, login_conf, cloud_conf)
        cluster_obj.repository.save_or_update(cluster_obj)

        # OK cluster was created, lets initialize nodes structures and
        # save the state information
        cluster_config = ClusterInfo(
            cluster_id=cluster_id,
            eclust_cluster_name=cluster_id,
            provider_id=cloud_conf,
            login_id=login_conf,
            provider_conf=provider,
            login_conf=login,
            driver_id=self.__interface_id__
        )

        self.repository_operator.write_cluster_info(cluster_config, create=True)
        return cluster_config

    def __stop_cluster(self, cluster_id: str, *args, **kwargs):
        log.debug("Stopping cluster `{}`".format(cluster_id))
        cluster_info = self.__get_updated_cluster(cluster_id)
        cluster_name = cluster_info.eclust_cluster_name

        force = kwargs.get('force', False)
        wait = kwargs.get('wait', False)
        delete_conf = kwargs.get('delete_conf', True)
        cluster = ElasticCreator.get_cluster_obj(cluster_name)
        cluster.stop(force, wait)

        if delete_conf:
            os.unlink("{}/{}.conf".format(Defaults.elasticluster_storage_path, cluster_name))
            os.unlink("{}/init-conf-{}.json".format(Defaults.elasticluster_storage_path, cluster_name))

        for node in self.repository_operator.get_nodes_from_cluster(cluster_id):
            self.repository_operator.remove_node(node.node_id)
        self.repository_operator.remove_cluster(cluster_id)
        log.debug("Cluster `{}` successfully stopped".format(cluster_id))

    def start_nodes(self, instances_num: Dict[str, int]) -> List[NodeInfo]:
        reader = ConfigReader(Defaults.cloud_conf, Defaults.login_conf, Defaults.instances_conf)
        instances = {i_name: i_conf for i_name, i_conf in reader.get_instances().items() if i_name in list(instances_num.keys())}

        if len(instances) != len(instances_num):
            raise Exception("Some instances are invalid: `{}`".format(', '.join(
                set(instances_num.keys()).difference(set(instances.keys())))))

        total_nodes = sum(instances_num.values())
        added_nodes = []
        reachable_nodes = []

        for i_name, i_conf in instances.items():
            provider_name = i_conf['provider']
            login_name = i_conf['login']
            node_info_map = {}

            cluster_info = self.__get_or_create_cluster(provider_name, login_name)
            cluster, started_nodes_objs = elaticluster_start_nodes(cluster_info.eclust_cluster_name, {i_name: instances_num[i_name]})
            control = self.repository_operator.read_platform_control_info()

            for node in started_nodes_objs:
                node_id = "{}-{}".format(self.node_prefix, control.node_idx)
                control.node_idx += 1

                node_info = NodeInfo(
                    node_id=node_id,
                    cluster_id=cluster_info.cluster_id,
                    eclust_node_name=node.name,
                    provider_id=cluster_info.provider_id,
                    login_id=cluster_info.login_id,
                    instance_type=i_name,
                    instance_conf=i_conf,
                    status=Codes.NODE_STATUS_INIT,
                    ip=None,
                    keypair=node.user_key_name,
                    key=node.user_key_private,
                    driver_id=self.__interface_id__,
                    tags={}
                )

                self.repository_operator.write_node_info(node_info, create=True)
                self.repository_operator.write_platform_control_info(control)
                added_nodes.append(node_info)
                node_info_map[node.name] = node_info

            try:
                final_nodes = elasticluster_check_starting_nodes(cluster, started_nodes_objs)
            except BaseException:
                node_ids_to_stop = [node_info_map[node.name].node_id for node in started_nodes_objs]
                log.error("Caught interrupt signal! Stopping nodes: `{}`".format(', '.join(node_ids_to_stop)))
                self.stop_nodes(node_ids_to_stop)
                raise Exception("Interrupted. Nodes that are not reachable were stopped.")

            for node in final_nodes:
                node_info = node_info_map[node.name]
                node_info.status = Codes.NODE_STATUS_REACHABLE
                node_info.ip = node.connection_ip()
                node_info.update_time = time()
                self.repository_operator.write_node_info(node_info)
                reachable_nodes.append(node_info)

        if len(added_nodes) != total_nodes:
            log.error("{} nodes were successfully started. {} nodes have failed...".format(
                len(added_nodes), total_nodes-len(added_nodes)))

        if len(reachable_nodes) != total_nodes:
            node_ids_to_stop = [node.node_id for node in added_nodes if node.node_id not in
                                [node.node_id for node in reachable_nodes]]
            self.stop_nodes(node_ids_to_stop)

            log.error("{} of {} nodes were successfully started, but are not reachable. These are stopped".format(
                total_nodes-len(reachable_nodes), total_nodes))

        return reachable_nodes

    def stop_nodes(self, node_ids: List[str]):
        for node_info in self.repository_operator.get_nodes(node_ids):
            log.info("Stopping node `{}`...".format(node_info.node_id))
            cluster_info = self.__get_updated_cluster(node_info.cluster_id)
            elasticluster_stop_nodes(cluster_info.eclust_cluster_name, [node_info.eclust_node_name])
            self.repository_operator.remove_node(node_info.node_id)
            log.debug("Node `{}` removed successfully".format(node_info.node_id))

            if len(self.repository_operator.get_nodes_from_cluster(cluster_info.cluster_id)) == 0:
                self.__stop_cluster(cluster_info.cluster_id)

    def pause_nodes(self, node_ids: List[str]):
        for node_info in self.repository_operator.get_nodes(node_ids):
            log.info("Pausing node `{}`...".format(node_info.node_id))
            cluster_info = self.__get_updated_cluster(node_info.cluster_id)
            elasticluster_pause_nodes(cluster_info.eclust_cluster_name, [node_info.eclust_node_name])
            node_info.status = Codes.NODE_STATUS_PAUSED
            node_info.update_time = time()
            self.repository_operator.write_node_info(node_info)

    def resume_nodes(self, node_ids: List[str]):
        raise NotImplementedError("Not implemented")

    def check_nodes_alive(self, node_ids: List[str]) -> Dict[str, bool]:
        checkeds = dict()
        for node in self.repository_operator.get_nodes(node_ids):
            first_ip = node.ip
            cluster_info = self.__get_updated_cluster(node.cluster_id)
            cluster_obj = ElasticCreator.get_cluster_obj(cluster_info.eclust_cluster_name)
            node_obj = ElasticCreator.get_node_from_cluster(cluster_info.eclust_cluster_name, node.eclust_node_name)

            if not node_obj.is_alive():
                checkeds[node.node_id] = False
                node.status = Codes.NODE_STATUS_UNREACHABLE
                node.update_time = time()
                self.repository_operator.write_node_info(node)
                continue

            client = node_obj.connect()
            node.status = Codes.NODE_STATUS_REACHABLE if client else Codes.NODE_STATUS_UNREACHABLE
            checkeds[node.node_id] = True if client else False
            node.ip = node_obj.connection_ip()
            node.update_time = time()

            self.repository_operator.write_node_info(node)
            ElasticCreator.upddate_cluster_node(cluster_obj, node_obj)

            if client:
                client.close()

            if node.ip != first_ip:
                log.info("Node `{}` ip has changed to `{}`".format(node.node_id, node.ip))

        return checkeds

    def get_connection_to_nodes(self, node_ids: List[str], *args, **kwargs) -> Dict[str, SSHClient]:
        connections = dict()
        for node in self.repository_operator.get_nodes(node_ids):
            cluster_info = self.__get_updated_cluster(node.cluster_id)
            connections[node.node_id] = elasticluster_get_connection_to_node(
                cluster_info.eclust_cluster_name, node.eclust_node_name, *args, **kwargs)

            node.status = Codes.NODE_STATUS_REACHABLE if connections[node.node_id] else Codes.NODE_STATUS_UNREACHABLE
            node.update_time = time()
            self.repository_operator.write_node_info(node)

        return connections

    def execute_playbook_in_nodes(self, playbook_path: str,
                                  group_hosts_map: Dict[str, List[str]],
                                  extra_args: Dict[str, str] = None,
                                  group_vars: Dict[str, Dict[str, str]] = None) -> Dict[str, bool]:
        node_ids = set([node_id for node_list in group_hosts_map.values() for node_id in node_list])
        nodes_info = self.repository_operator.get_nodes(list(node_ids))
        reverse_map = {node.eclust_node_name: node.node_id for node in nodes_info}
        cluster_ids = set([node.cluster_id for node in nodes_info])
        executed_nodes = dict()

        for cluster_id in cluster_ids:
            ecc_nodes = list()
            cluster_info = self.__get_updated_cluster(cluster_id)
            ecc_cluster = ElasticCreator.get_cluster_obj(cluster_name=cluster_info.eclust_cluster_name)

            host_set = {host for group, _hosts in group_hosts_map.items() for host in _hosts}
            nodeid_groups_map = {host: [group for group, _hosts in group_hosts_map.items() if host in _hosts] for host in host_set}
            for nodeid, groups, in nodeid_groups_map.items():
                node = ElasticCreator.get_node_from_cluster(cluster_id, self.repository_operator.get_node(nodeid).eclust_node_name)
                node.kind = nodeid
                ecc_nodes.append(node)

            group_vars = group_vars if group_vars else {}
            ecc_ansible_wrapper = AnsibleSetupProviderWrapper(ecc_cluster._setup_provider, nodeid_groups_map,
                                                              group_vars, reverse_map)
            ecc_extra_args = tuple(['{}="{}"'.format(k, v) for k, v in extra_args.items()]) if extra_args else {}

            executed_nodes.update(ecc_ansible_wrapper.run_playbook(
                ecc_cluster, ecc_nodes, playbook=playbook_path, extra_args=ecc_extra_args))

        return executed_nodes
