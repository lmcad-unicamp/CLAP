import logging
import os
from clap.common.utils import path_extend, yaml_load

if 'CLAP' not in os.environ:
    raise ValueError('CLAP environment variable is not set. Please set the CLAP variable in your system, '
                     'pointing directly to the clap root directory!')

if 'CLAP_PATH' not in os.environ:
    raise ValueError('CLAP_PATH environment variable is not set. Please set the CLAP_PATH variable in your system!')


class Defaults:
    verbosity = 0
    log_level = logging.INFO
    app_name = 'clap'
    REPOSITORY_TYPE = 'tinydb'
    DRIVER_ID = 'ansible'
    DEFAULT_CONF_TYPE = 'json'

    configs_path = path_extend('$CLAP_PATH', 'configs')
    private_path = path_extend('$CLAP_PATH', 'private')
    storage_path = path_extend('$CLAP_PATH', 'storage')
   # execution_playbook = path_extend('$CLAP_PATH', 'groups', 'main.yml')
    groups_path = path_extend('$CLAP_PATH', 'groups')
    modules_path = path_extend('$CLAP_PATH', 'modules')
    modules_data = path_extend(storage_path, 'modules')
    elasticluster_storage_path = path_extend(storage_path, 'clusters.d')

    cloud_conf = path_extend(configs_path, 'providers.yaml')
    login_conf = path_extend(configs_path, 'logins.yaml')
    instances_conf = path_extend(configs_path, 'instances.yaml')

    PLATFORM_REPOSITORY = path_extend(storage_path, 'platform.'+DEFAULT_CONF_TYPE)


PROVIDERS_SCHEMA = {}
LOGIN_SCHEMA = {}
INSTANCE_SCHEMA = {}


class ConfigReader:
    def __init__(self, providers_file: str, logins_file: str, instances_file: str):
        self.provider_configs = yaml_load(providers_file)
        self.login_configs = yaml_load(logins_file)
        self.instance_configs = yaml_load(instances_file)

        self.__validate(PROVIDERS_SCHEMA, self.provider_configs)
        self.__validate(LOGIN_SCHEMA, self.login_configs)
        self.__validate(INSTANCE_SCHEMA, self.instance_configs)

        self.__check_instances()

    def __validate(self, schema: dict, data: dict):
        pass

    def __check_instances(self):
        missing_providers = [name for name, config in self.instance_configs.items()
                          if config['provider'] not in list(self.provider_configs.keys())]
        if missing_providers:
            raise Exception("Invalid providers: {}".format(
                ', '.join(['`{}` for instance `{}`'.format(self.instance_configs[miss]['provider'], miss) for miss in
                           missing_providers])))

        missing_logins = [name for name, config in self.instance_configs.items()
                          if config['login'] not in list(self.login_configs.keys())]
        if missing_logins:
            raise Exception("Invalid login: {}".format(
                ', '.join(['`{}` for instance `{}`'.format(self.instance_configs[miss]['login'], miss) for miss in
                           missing_logins])))

    def get_instance(self, instance_name: str):
        return dict(self.instance_configs[instance_name])

    def get_instances(self):
        return dict(self.instance_configs)

    def get_provider(self, provider_name: str):
        return dict(self.provider_configs[provider_name])

    def get_providers(self, provider_name: str):
        return dict(self.provider_configs)

    def get_login(self, login_name: str):
        return dict(self.login_configs[login_name])

    def get_logins(self, login_name: str):
        return dict(self.login_configs[login_name])