from dataclasses import field, dataclass
from typing import List, Optional, Dict, Union

import dacite

from clap.utils import yaml_load, get_logger

logger = get_logger(__name__)


# --------------------    Exceptions    --------------------
class ConfigurationError(Exception):
    pass


class InvalidConfigurationError(ConfigurationError):
    def __init__(self, name: str):
        super().__init__(f"Invalid configuration named '{name}'")


# --------------------    Providers    --------------------
@dataclass
class ProviderConfigAWS:
    provider_config_id: str
    region: str
    access_keyfile: str
    secret_access_keyfile: str
    vpc: Optional[str]
    url: Optional[str]
    provider: str = 'aws'


@dataclass
class ProviderConfigLocal:
    provider_config_id: str
    provider: str = 'local'


# --------------------    Logins    --------------------
@dataclass
class LoginConfig:
    login_config_id: str
    user: str
    keypair_name: str
    keypair_public_file: str
    keypair_private_file: str
    ssh_port: Optional[int] = 22
    sudo: Optional[bool] = True
    sudo_user: Optional[str] = 'root'


# --------------------    Instances    --------------------
@dataclass
class InstanceConfigAWS:
    instance_config_id: str
    provider: str
    login: str
    flavor: str
    image_id: str
    security_group: Optional[str]
    boot_disk_size: Optional[int]
    boot_disk_device: Optional[str]
    boot_disk_type: Optional[str]
    boot_disk_iops: Optional[str]
    boot_disk_snapshot: Optional[str]
    placement_group: Optional[str]
    price: Optional[float]
    timeout: Optional[int]
    network_ids: Optional[List[str]] = field(default_factory=list)


# --------------------    Handlers and Generalizations    --------------------
provider_handlers = {
    'aws': ProviderConfigAWS,
    'local': ProviderConfigLocal
}

ProviderConfigs = Union[ProviderConfigAWS, ProviderConfigLocal]
LoginConfigs = Union[LoginConfig]
InstanceConfigs = Union[InstanceConfigAWS]


@dataclass
class InstanceInfo:
    provider: ProviderConfigs
    login: LoginConfigs
    instance: InstanceConfigs


class ConfigurationDatabase:
    def __init__(self, providers_file: str, logins_file: str,
                 instances_file: str, discard_invalids: bool = True,
                 load: bool = True):
        self.providers_file: str = providers_file
        self.logins_file: str = logins_file
        self.instances_file: str = instances_file
        self.providers_config: Dict[str, ProviderConfigs] = dict()
        self.logins_config: Dict[str, LoginConfigs] = dict()
        self.instances_config: Dict[str, InstanceConfigs] = dict()
        self.instance_descriptors: Dict[str, InstanceInfo] = dict()
        self._discard_invalids: bool = discard_invalids
        if load:
            self.load_all()

    def _load_provider_configs(self):
        @dataclass
        class _Provider:
            p: ProviderConfigs

        providers = yaml_load(self.providers_file)
        for pid, pconfig in providers.items():
            pconfig['provider_config_id'] = pid
            try:
                p = dacite.from_dict(_Provider, data={'p': pconfig}).p
                self.providers_config[pid] = p
            except dacite.DaciteError as e:
                if self._discard_invalids:
                    logger.error(f"Dropping provider configuration named '{pid}'. "
                                 f"{type(e).__name__}: {e}")
                else:
                    raise ConfigurationError from e

    def _load_login_configs(self):
        @dataclass
        class _Login:
            l: LoginConfigs

        logins = yaml_load(self.logins_file)
        for lid, lconfig in logins.items():
            lconfig['login_config_id'] = lid
            try:
                l = dacite.from_dict(_Login, data={'l': lconfig}).l
                self.logins_config[lid] = l
            except dacite.DaciteError as e:
                if self._discard_invalids:
                    logger.error(f"Dropping login configuration named '{lid}'. "
                                 f"{type(e).__name__}: {e}")
                else:
                    raise ConfigurationError from e

    def _load_instance_configs(self):
        @dataclass
        class _Instance:
            i: InstanceConfigs

        instances = yaml_load(self.instances_file)
        for iid, iconfig in instances.items():
            iconfig['instance_config_id'] = iid
            try:
                i = dacite.from_dict(_Instance, data={'i': iconfig}).i
                self.instances_config[iid] = i
            except dacite.DaciteError as e:
                if self._discard_invalids:
                    logger.error(f"Dropping instance configuration named '{iid}'. "
                                 f"{type(e).__name__}: {e}")
                else:
                    raise ConfigurationError from e

    def load_all(self):
        self._load_provider_configs()
        self._load_login_configs()
        self._load_instance_configs()
        for iid, iconfig in self.instances_config.items():
            if iconfig.provider not in self.providers_config:
                if self._discard_invalids:
                    logger.error(f"Discarding instance named {iid}. Invalid "
                                 f"provider configuration named {iconfig.provider}")
                    continue
                else:
                    raise ConfigurationError(
                        f"In instance named {iid}: Invalid provider "
                        f"configuration {iconfig.provider}")

            if iconfig.login not in self.logins_config:
                if self._discard_invalids:
                    logger.error(f"Discarding instance named {iid}. Invalid "
                                 f"login configuration named {iconfig.login}")
                    continue
                else:
                    raise ConfigurationError(
                        f"In instance named {iid}: Invalid login "
                        f"configuration {iconfig.login}")

            instance = InstanceInfo(
                provider=self.providers_config[iconfig.provider],
                login=self.logins_config[iconfig.login],
                instance=iconfig
            )
            self.instance_descriptors[iid] = instance

        logger.debug(f"Loaded {len(self.instance_descriptors)} instance descriptors: "
                     f"{', '.join(sorted(self.instance_descriptors.keys()))}")
