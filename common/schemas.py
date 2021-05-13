import functools
from abc import ABC, abstractmethod
from dataclasses import field, dataclass, asdict, make_dataclass
from typing import List, Optional, Dict, Union

import marshmallow.validate

from marshmallow_dataclass import class_schema
from common.utils import yaml_load, get_logger, Serializable

logger = get_logger(__name__)


# Provider decorator

# Exceptions
class ConfigurationError(Exception):
    pass


class ProviderConfigError(ConfigurationError):
    def __init__(self, name: str):
        super().__init__(f'Invalid provider type: {name}')


class InvalidProvider(ConfigurationError):
    def __init__(self, name: str):
        super().__init__(f'Invalid provider configuration: {name}')


class InvalidLogin(ConfigurationError):
    def __init__(self, name: str):
        super().__init__(f'Invalid login configuration: {name}')


@dataclass
class ProviderConfigAWS:
    provider_config_id: str
    region: str
    access_keyfile: str
    secret_access_keyfile: str
    vpc: str = None
    url: str = None
    provider: str = 'aws'


@dataclass
class ProviderConfigLocal:
    provider_config_id: str
    provider: str = 'local'


@dataclass
class LoginConfig:
    login_config_id: str
    user: str
    ssh_port: int = 22
    keypair_name: str = None
    keypair_public_file: str = None
    keypair_private_file: str = None
    sudo: Optional[bool] = True
    sudo_user: Optional[str] = 'root'


@dataclass
class InstanceConfigAWS:
    instance_config_id: str
    provider: str
    login: str
    flavor: str
    image_id: str
    security_group: str = None
    boot_disk_size: int = None
    boot_disk_device: str = None
    boot_disk_type: str = None
    boot_disk_iops: str = None
    boot_disk_snapshot: str = None
    placement_group: str = None
    price: Optional[float] = field(default=0.0)
    network_ids: Optional[List[str]] = field(default_factory=list)
    timeout: Optional[int] = field(default=0, metadata=dict(validate=marshmallow.validate.Range(min=0)))


provider_handlers = {
    'aws': ProviderConfigAWS,
    'local': ProviderConfigLocal
}

_ProviderConfig = Union[ProviderConfigAWS, ProviderConfigLocal]
_LoginConfig = Union[LoginConfig]
_InstanceConfig = Union[InstanceConfigAWS]


def validate_provider_config(d: dict):
    provider_name = d.get('provider', None)
    if not provider_name:
        raise ConfigurationError("Missing provider key in a provider configuration")
    try:
        return class_schema(provider_handlers[provider_name])().load(d)
    except KeyError as e:
        raise InvalidProvider(provider_name) from e


def validate_login_config(d: dict) -> LoginConfig:
    return class_schema(LoginConfig)().load(d)


def validate_instance_config(d: dict) -> InstanceConfigAWS:
    return class_schema(InstanceConfigAWS)().load(d)


@dataclass
class InstanceInfo(Serializable):
    provider: _ProviderConfig
    login: _LoginConfig
    instance: _InstanceConfig

    def to_dict(self) -> dict:
        return dict(
            provider=asdict(self.provider),
            login=asdict(self.login),
            instance=asdict(self.instance)
        )

    @staticmethod
    def from_dict(d: dict):
        provider = validate_provider_config(d['provider'])
        login = validate_login_config(d['login'])
        instance = validate_instance_config(d['instance'])
        return InstanceInfo(provider, login, instance)


class ConfigurationDatabase(ABC):
    @abstractmethod
    def get_provider_config(self, provider_id: str) -> _ProviderConfig:
        pass

    @abstractmethod
    def get_all_providers_config(self) -> Dict[str, _ProviderConfig]:
        pass

    @abstractmethod
    def get_login_config(self, login_id: str) -> _LoginConfig:
        pass

    @abstractmethod
    def get_all_logins_config(self) -> Dict[str, _LoginConfig]:
        pass

    @abstractmethod
    def get_instance_config(self, instance_id: str) -> _InstanceConfig:
        pass

    @abstractmethod
    def get_all_instances_config(self) -> Dict[str, _InstanceConfig]:
        pass

    @abstractmethod
    def get_instance_info(self, instance_id: str) -> InstanceInfo:
        pass

    @abstractmethod
    def get_all_instances_info(self) -> Dict[str, InstanceInfo]:
        pass


class YAMLConfigurationDatabase(ConfigurationDatabase):
    def __init__(self, providers_file: str, logins_file: str, instances_file: str):
        self.providers_file = providers_file
        self.logins_file = logins_file
        self.instances_file = instances_file
        self.providers_config = dict()
        self.logins_config = dict()
        self.instances_config = dict()
        self.instance_descriptors = dict()
        self.load_providers_config()
        self.load_logins_config()
        self.load_instances_config()

    def load_providers_config(self):
        for provider_config_id, provider_config in yaml_load(self.providers_file).items():
            try:
                provider_config['provider_config_id'] = provider_config_id
                self.providers_config[provider_config_id] = validate_provider_config(provider_config)
            except Exception as e:
                logger.error(f"Dropping provider configuration `{provider_config_id}`. {type(e).__name__}: {e}")

    def load_logins_config(self):
        for login_config_id, login_config in yaml_load(self.logins_file).items():
            try:
                login_config['login_config_id'] = login_config_id
                self.logins_config[login_config_id] = validate_login_config(login_config)
            except Exception as e:
                logger.error(f"Dropping login configuration `{login_config_id}`. {type(e).__name__}: {e}")

    def load_instances_config(self):
        for instance_config_id, instance_config in yaml_load(self.instances_file).items():
            try:
                if 'provider' not in instance_config:
                    raise KeyError(f"Missing provider field in instance configuration: `{instance_config_id}`")
                if 'login' not in instance_config:
                    raise KeyError(f"Missing login field in instance configuration: `{instance_config_id}`")
                if instance_config['provider'] not in self.providers_config:
                    raise KeyError(
                        f"Invalid provider with id `{instance_config['provider']}` in `{instance_config_id}`")
                if instance_config['login'] not in self.logins_config:
                    raise KeyError(
                        f"Invalid provider with id `{instance_config['provider']}` in `{instance_config_id}`")
                instance_config['instance_config_id'] = instance_config_id
                self.instances_config[instance_config_id] = validate_instance_config(instance_config)
                self.instance_descriptors[instance_config_id] = InstanceInfo(
                    self.providers_config[instance_config['provider']],
                    self.logins_config[instance_config['login']],
                    self.instances_config[instance_config_id]
                )
            except Exception as e:
                logger.error(f"Dropping instance configuration `{instance_config_id}`. {type(e).__name__}: {e}")

    def get_provider_config(self, provider_id: str) -> _ProviderConfig:
        try:
            return self.providers_config[provider_id]
        except KeyError:
            raise ConfigurationError(provider_id)

    def get_all_providers_config(self) -> Dict[str, _ProviderConfig]:
        return self.providers_config

    def get_login_config(self, login_id: str) -> _LoginConfig:
        try:
            return self.logins_config[login_id]
        except KeyError:
            raise ConfigurationError(login_id)

    def get_all_logins_config(self) -> Dict[str, _LoginConfig]:
        return self.logins_config

    def get_instance_config(self, instance_id: str) -> _InstanceConfig:
        try:
            return self.instances_config[instance_id]
        except KeyError:
            raise ConfigurationError(instance_id)

    def get_all_instances_config(self) -> Dict[str, _InstanceConfig]:
        return self.instances_config

    def get_instance_info(self, instance_id: str) -> InstanceInfo:
        try:
            return self.instance_descriptors[instance_id]
        except KeyError:
            raise ConfigurationError(instance_id)

    def get_all_instances_info(self) -> Dict[str, InstanceInfo]:
        return self.instance_descriptors
