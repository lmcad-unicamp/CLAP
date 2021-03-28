from abc import ABC, abstractmethod
from dataclasses import field, dataclass, asdict
from typing import List, Optional, Dict

import marshmallow.validate

from marshmallow_dataclass import class_schema
from common.utils import yaml_load, get_logger, Serializable

logger = get_logger(__name__)


class InvalidConfiguration(Exception):
    pass


class InvalidProvider(InvalidConfiguration):
    pass


@dataclass
class ProviderConfig:
    provider_config_id: str
    provider: str
    region: str


@dataclass
class ProviderConfigLocal(ProviderConfig):
    pass


@dataclass
class ProviderConfigAWS(ProviderConfig):
    access_keyfile: str
    secret_access_keyfile: str
    vpc: str = None
    url: str = None


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
class InstanceConfig:
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
    price: Optional[float] = 0.0 #= field(default=0.0, metadata=dict(validate=lambda x: x>10, error_messages={'validator_failed': 'Must be greater than 10'}))
    network_ids: Optional[List[str]] = field(default_factory=list)
    timeout: Optional[int] = field(default=0, metadata=dict(validate=marshmallow.validate.Range(min=0)))


providers_map = {
    'aws': ProviderConfigAWS,
    'local': ProviderConfigLocal
}


def validate_provider_config(d: dict) -> ProviderConfig:
    provider_name = d['provider']
    try:
        return class_schema(providers_map[provider_name])().load(d)
    except KeyError:
        raise InvalidProvider(provider_name)


def validate_login_config(d: dict) -> LoginConfig:
    return class_schema(LoginConfig)().load(d)


def validate_instance_config(d: dict) -> InstanceConfig:
    return class_schema(InstanceConfig)().load(d)


@dataclass
class InstanceDescriptor(Serializable):
    provider: ProviderConfig
    login: LoginConfig
    instance: InstanceConfig

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
        return InstanceDescriptor(provider, login, instance)


class ConfigurationReader(ABC):
    @abstractmethod
    def get_provider_config(self, provider_id: str) -> ProviderConfig:
        pass

    @abstractmethod
    def get_all_providers_config(self) -> Dict[str, ProviderConfig]:
        pass

    @abstractmethod
    def get_login_config(self, login_id: str) -> LoginConfig:
        pass

    @abstractmethod
    def get_all_logins_config(self) -> Dict[str, LoginConfig]:
        pass

    @abstractmethod
    def get_instance_config(self, instance_id: str) -> InstanceConfig:
        pass

    @abstractmethod
    def get_all_instances_config(self) -> Dict[str, InstanceConfig]:
        pass

    @abstractmethod
    def get_instance_descriptor(self, instance_id: str) -> InstanceDescriptor:
        pass

    @abstractmethod
    def get_all_instances_descriptor(self) -> Dict[str, InstanceDescriptor]:
        pass


class YAMLConfigurationReader(ConfigurationReader):
    def __init__(self, providers_path: str, logins_path: str, instances_path: str):
        self.providers_path = providers_path
        self.logins_path = logins_path
        self.instances_path = instances_path
        self.providers_config = dict()
        self.logins_config = dict()
        self.instances_config = dict()
        self.instance_descriptors = dict()

        self.load_providers_config()
        self.load_logins_config()
        self.load_instances_config()

    def load_providers_config(self):
        for provider_config_id, provider_config in yaml_load(self.providers_path).items():
            try:
                provider_config['provider_config_id'] = provider_config_id
                self.providers_config[provider_config_id] = validate_provider_config(provider_config)
            except Exception as e:
                logger.error(f"Dropping provider configuration `{provider_config_id}`. {type(e).__name__}: {e}")

    def load_logins_config(self):
        for login_config_id, login_config in yaml_load(self.logins_path).items():
            try:
                login_config['login_config_id'] = login_config_id
                self.logins_config[login_config_id] = validate_login_config(login_config)
            except Exception as e:
                logger.error(f"Dropping login configuration `{login_config_id}`. {type(e).__name__}: {e}")

    def load_instances_config(self):
        for instance_config_id, instance_config in yaml_load(self.instances_path).items():
            try:
                if 'provider' not in instance_config:
                    raise KeyError(f"Missing provider field in instance configuration: `{instance_config_id}`")
                if 'login' not in instance_config:
                    raise KeyError(f"Missing login field in instance configuration: `{instance_config_id}`")
                if instance_config['provider'] not in self.providers_config:
                    raise KeyError(f"Invalid provider with id `{instance_config['provider']}` in `{instance_config_id}`")
                if instance_config['login'] not in self.logins_config:
                    raise KeyError(f"Invalid provider with id `{instance_config['provider']}` in `{instance_config_id}`")
                instance_config['instance_config_id'] = instance_config_id
                self.instances_config[instance_config_id] = validate_instance_config(instance_config)
                self.instance_descriptors[instance_config_id] = InstanceDescriptor(
                    self.providers_config[instance_config['provider']],
                    self.logins_config[instance_config['login']],
                    self.instances_config[instance_config_id]
                )
            except Exception as e:
                logger.error(f"Dropping instance configuration `{instance_config_id}`. {type(e).__name__}: {e}")

    def get_provider_config(self, provider_id: str) -> ProviderConfig:
        try:
            return self.providers_config[provider_id]
        except KeyError:
            raise InvalidConfiguration(provider_id)

    def get_all_providers_config(self) -> Dict[str, ProviderConfig]:
        return self.providers_config

    def get_login_config(self, login_id: str) -> LoginConfig:
        try:
            return self.logins_config[login_id]
        except KeyError:
            raise InvalidConfiguration(login_id)

    def get_all_logins_config(self) -> Dict[str, LoginConfig]:
        return self.logins_config

    def get_instance_config(self, instance_id: str) -> InstanceConfig:
        try:
            return self.instances_config[instance_id]
        except KeyError:
            raise InvalidConfiguration(instance_id)

    def get_all_instances_config(self) -> Dict[str, InstanceConfig]:
        return self.instances_config

    def get_instance_descriptor(self, instance_id: str) -> InstanceDescriptor:
        try:
            return self.instance_descriptors[instance_id]
        except KeyError:
            raise InvalidConfiguration(instance_id)

    def get_all_instances_descriptor(self) -> Dict[str, InstanceDescriptor]:
        return self.instance_descriptors
