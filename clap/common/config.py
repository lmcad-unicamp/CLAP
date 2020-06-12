import logging
import os
from clap.common.utils import path_extend, yaml_load


# Set CLAP_PATH to ~/.clap if it is not set as an environment variable
if 'CLAP_PATH' not in os.environ:
    os.environ['CLAP_PATH'] = path_extend('~', '.clap')

class Defaults:
    """ Default values used in CLAP system. This is a class is global and changes in its values affects all places that uses it
    """

    """ CLAP VERBOSITY LEVEL from 0 (less verbose) to 4 (more verbose) """
    verbosity = 0
    """ Log level for logging operations (based on logging package) """
    log_level = logging.INFO
    """ Default symbolic application name """
    app_name = 'CLAP'
    """ Default repository implementation used """
    REPOSITORY_TYPE = 'tinydb'
    """ Default driver implementation used """
    DRIVER_ID = 'ansible'
    """ Default repository type used """
    DEFAULT_CONF_TYPE = 'json'
    """ Path to configuration files """
    configs_path = path_extend('$CLAP_PATH', 'configs')
    """ Path to private files """
    private_path = path_extend('$CLAP_PATH', 'private')
    """ Path to storage, where metadata information is placed """
    storage_path = path_extend('$CLAP_PATH', 'storage')
    """ Path to groups directory """
    groups_path = path_extend('$CLAP_PATH', 'groups')
    """ Path to group's actions directory """
    actions_path = path_extend(groups_path, 'actions.d')
    """ Path to additional CLAP's modules directory """
    modules_path = path_extend('$CLAP_PATH', 'modules')
    """ Path to CLAP's modules metadata storage path """
    modules_data = path_extend(storage_path, 'modules')
    """ NOT USED """
    elasticluster_storage_path = path_extend(storage_path, 'clusters.d')
    """ Default path to provider configuration file """
    cloud_conf = path_extend(configs_path, 'providers.yaml')
    """ Default path to login configuration file """
    login_conf = path_extend(configs_path, 'logins.yaml')
    """ Default path to instances configuration file """
    instances_conf = path_extend(configs_path, 'instances.yaml')
    """ Default path to platform configuration file """
    PLATFORM_REPOSITORY = path_extend(storage_path, 'platform.'+DEFAULT_CONF_TYPE)


class ConfigReader:
    PROVIDERS_SCHEMA = {}
    LOGIN_SCHEMA = {}
    INSTANCE_SCHEMA = {}

    """ Class used to read and validate configurations from configuration files (provider, logins and instances)
    """
    def __init__(self, providers_file: str, logins_file: str, instances_file: str):
        self.provider_configs = yaml_load(providers_file)
        self.login_configs = yaml_load(logins_file)
        self.instance_configs = yaml_load(instances_file)

        self.__validate(self.PROVIDERS_SCHEMA, self.provider_configs)
        self.__validate(self.LOGIN_SCHEMA, self.login_configs)
        self.__validate(self.INSTANCE_SCHEMA, self.instance_configs)

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