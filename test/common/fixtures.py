import tempfile
from typing import List

import pytest

from unittest import mock

from common.clap import NodeInfo, NodeRepositoryOperator
from common.schemas import ProviderConfig, InstanceDescriptor
from common.repository import SQLiteRepository
from common.utils import path_extend


def assertDictEqual(d1, d2, path='', key_not_existing='raise'):
    for k in d1.keys():
        if k not in d2:
            if key_not_existing == 'raise':
                assert False, f"{path} invalid key {k}"
            elif key_not_existing == 'pass':
                continue
            else:
                raise ValueError(f"Invalid not_existing parameter value `{key_not_existing}`")
        else:
            if type(d1[k]) is dict:
                new_path = f"{path}.{k}" if path else k
                assertDictEqual(d1[k], d2[k], new_path, key_not_existing)
            else:
                if d1[k] != d2[k]:
                    path = f"{path}.{k}" if path else k
                    assert False, f"Key: {path}.{k} has different values (actual: {d1[k]}, expected: {d2[k]})"


class FakeProviderConfig(ProviderConfig):
    pass


# @pytest.fixture(scope='function', ids=["nodes10"], params=[10])
# def nodes(request) -> List[NodeInfo]:
#     pass
#
#     return [NodeInfo(node_id=f"node-{i}", configuration=valid_instance_descriptor)
#             for i in range(0, request.param)]
#
#
# @pytest.fixture(scope='function')
# def repository():
#     with tempfile.TemporaryDirectory() as datadir:
#         repository_path = path_extend(datadir, 'test.db')
#         yield SQLiteRepository(repository_path=repository_path, commit_on_close=True)
#
#
# @pytest.fixture(scope='function')
# def node_repository(repository):
#     yield NodeRepositoryOperator(repository)
