import pytest
import tempfile
import unittest

from unittest import mock
from marshmallow.exceptions import ValidationError
from common.configs import validate_provider_config, validate_login_config, validate_instance_config, \
    InstanceInfo, InvalidProvider, ProviderConfig
from .fixtures import assertDictEqual, FakeProviderConfig


@pytest.fixture(scope='module')
def provider_file_with_data():
    config_file = tempfile.NamedTemporaryFile('w+t')
    yield config_file.name


@pytest.fixture(scope='module')
def login_file_with_data():
    config_file = tempfile.NamedTemporaryFile('w+t')
    yield config_file.name


@pytest.fixture(scope='module')
def instances_file_with_data():
    config_file = tempfile.NamedTemporaryFile('w+t')
    yield config_file.name


@pytest.fixture(scope='module')
def valid_provider_config() -> dict:
    return {
        'provider_config_id': 'provider-1',
        'provider': 'fake',
        'region': 'region-1'
    }


@pytest.fixture(scope='module')
def valid_login_config() -> dict:
    return {
        'login_config_id': 'login-1',
        'user': 'root-user',
    }


@pytest.fixture(scope='module',
                ids=['with-net-id', 'with-timeout'],
                params=[{'network_ids': ['iface-1', 'iface-2']}, {'timeout': 10.0}])
def valid_instance_config(request) -> dict:
    d = {
        'instance_config_id': 'instance-0',
        'provider': 'provider-1',
        'login': 'login-1',
        'flavor': 'flavor-1',
        'image_id': 'image-xxx'
    }
    d.update(request.param)
    return d


@pytest.fixture(scope='module')
@mock.patch("common.schemas.providers_map", {'fake': FakeProviderConfig})
def valid_instance_descriptor(valid_provider_config, valid_login_config, valid_instance_config):
    d = {
        'provider': valid_provider_config,
        'login': valid_login_config,
        'instance': valid_instance_config
    }
    return InstanceInfo.from_dict(d)


def make_test_configuration_reader(config_class):
    class ConfigReader(unittest.TestCase):
        @pytest.fixture(scope='class')
        def config_reader(self, provider_file_with_data, login_file_with_data, instances_file_with_data):
            print(provider_file_with_data, login_file_with_data, instances_file_with_data)
            return config_class(provider_file_with_data, login_file_with_data, instances_file_with_data)

        def test_cloud_config(self, config_reader):
            assert True

    return ConfigReader


@mock.patch("common.schemas.providers_map", {'fake': FakeProviderConfig})
def test_provider_config_load_from_dict(valid_provider_config):
    provider = validate_provider_config(valid_provider_config)
    assertDictEqual(provider.__dict__, valid_provider_config)


@mock.patch("common.schemas.providers_map", {'fake': FakeProviderConfig})
def test_invalid_provider_config_load_from_dict(valid_provider_config):
    with pytest.raises(KeyError):
        validate_provider_config({})

    with pytest.raises(InvalidProvider):
        invalid_provider_config = valid_provider_config.copy()
        invalid_provider_config['provider'] = 'invalid-provider'
        validate_provider_config(invalid_provider_config)

    with pytest.raises(KeyError):
        invalid_provider_config = valid_provider_config.copy()
        invalid_provider_config.pop('provider')
        validate_provider_config(invalid_provider_config)


@mock.patch("common.schemas.providers_map", {'fake': FakeProviderConfig})
def test_validation_error_provider_config_load_from_dict(valid_provider_config):
    with pytest.raises(ValidationError):
        invalid_provider_config = valid_provider_config.copy()
        invalid_provider_config.pop('provider_config_id')
        validate_provider_config(invalid_provider_config)

    with pytest.raises(ValidationError):
        invalid_provider_config = valid_provider_config.copy()
        invalid_provider_config['provider_config_id'] = 10
        validate_provider_config(invalid_provider_config)


def test_login_config_load_from_dict(valid_login_config):
    login_config = validate_login_config(valid_login_config)
    assertDictEqual(login_config.__dict__, valid_login_config, key_not_existing='pass')


def test_validation_error_login_config_load_from_dict(valid_login_config):
    with pytest.raises(ValidationError):
        invalid_login_config = valid_login_config.copy()
        invalid_login_config.pop('login_config_id')
        validate_login_config(invalid_login_config)

    with pytest.raises(ValidationError):
        invalid_login_config = valid_login_config.copy()
        invalid_login_config['login_config_id'] = 10
        validate_login_config(invalid_login_config)

    with pytest.raises(ValidationError):
        invalid_login_config = valid_login_config.copy()
        invalid_login_config['keypair_name'] = 10.0
        validate_login_config(invalid_login_config)

    with pytest.raises(ValidationError):
        invalid_login_config = valid_login_config.copy()
        invalid_login_config['sudo_user'] = 10
        validate_login_config(invalid_login_config)


def test_instance_config_load_from_dict(valid_instance_config):
    instance_config = validate_instance_config(valid_instance_config)
    assert instance_config.instance_config_id == valid_instance_config['instance_config_id']
    assert instance_config.provider == valid_instance_config['provider']
    assert instance_config.login == valid_instance_config['login']
    assert type(instance_config.network_ids) is list
    assert instance_config.price == 0.0


def test_validation_error_instance_config_load_from_dict(valid_instance_config):
    with pytest.raises(ValidationError):
        invalid_instance_config = valid_instance_config.copy()
        invalid_instance_config.pop('instance_config_id')
        validate_instance_config(invalid_instance_config)

    with pytest.raises(ValidationError):
        invalid_instance_config = valid_instance_config.copy()
        invalid_instance_config.pop('provider')
        validate_instance_config(invalid_instance_config)

    with pytest.raises(ValidationError):
        invalid_instance_config = valid_instance_config.copy()
        invalid_instance_config.pop('flavor')
        validate_instance_config(invalid_instance_config)

    with pytest.raises(ValidationError):
        invalid_instance_config = valid_instance_config.copy()
        invalid_instance_config.pop('flavor')
        validate_instance_config(invalid_instance_config)

    with pytest.raises(ValidationError):
        invalid_instance_config = valid_instance_config.copy()
        invalid_instance_config['timeout'] = 'a'
        validate_instance_config(invalid_instance_config)

    with pytest.raises(ValidationError):
        invalid_instance_config = valid_instance_config.copy()
        invalid_instance_config['instance_config_id'] = 10
        validate_instance_config(invalid_instance_config)

    with pytest.raises(ValidationError):
        invalid_instance_config = valid_instance_config.copy()
        invalid_instance_config['network_ids'] = {'xxx': 'yyy'}
        validate_instance_config(invalid_instance_config)

    with pytest.raises(ValidationError):
        invalid_instance_config = valid_instance_config.copy()
        invalid_instance_config['network_ids'] = None
        validate_instance_config(invalid_instance_config)


# @mock.patch("common.schemas.providers_map", {'fake': FakeProviderConfig})
# def test_instance_descriptor_load_from_dict(valid_instance_descriptor, valid_provider_config, valid_login_config, valid_instance_config):
#     instance = valid_instance_descriptor
#     assertDictEqual(instance.provider.__dict__, valid_provider_config, key_not_existing='pass')
#     assertDictEqual(instance.login.__dict__, valid_login_config, key_not_existing='pass')
#     assertDictEqual(instance.instance.__dict__, valid_instance_config, key_not_existing='pass')


@mock.patch("common.schemas.providers_map", {'fake': FakeProviderConfig})
def test_instance_descriptor_to_dict(valid_provider_config, valid_login_config, valid_instance_config):
    d = {
        'provider': valid_provider_config,
        'login': valid_login_config,
        'instance': valid_instance_config
    }
    instance = InstanceInfo.from_dict(d)
    instance_dict = instance.to_dict()
    assertDictEqual(instance_dict, d, key_not_existing='pass')

    instance = InstanceInfo.from_dict(instance_dict)
    assertDictEqual(instance.provider.__dict__, valid_provider_config, key_not_existing='pass')
    assertDictEqual(instance.login.__dict__, valid_login_config, key_not_existing='pass')
    assertDictEqual(instance.instance.__dict__, valid_instance_config, key_not_existing='pass')


if __name__ == "__main__":
    pytest.main(['-v', __file__])