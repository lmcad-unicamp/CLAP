import pytest

from typing import List

from common.node import NodeRepositoryController, NodeStatus, NodeDescriptor
from .fixtures import *


class TestNodeInfo:
    @mock.patch("common.schemas.providers_map", {'fake': FakeProviderConfig})
    def test_nodes_dict(self, nodes: List[NodeDescriptor]):
        for node in nodes:
            node.extra = {'value': {'a': {'b': 'c'}}}
            node_dict = node.to_dict()
            new_node = NodeDescriptor.from_dict(node_dict)
            new_node.configuration = new_node.configuration.to_dict()
            assertDictEqual(new_node.__dict__, node_dict)

    def test_roles(self, nodes: List[NodeDescriptor]):
        node = nodes[0]
        node.add_role('role1')
        node.add_role('role2')
        node.add_role('role3')
        node.add_role('role1')
        assert node.has_role('role1')
        assert node.has_role('role2')
        assert node.has_role('role3')
        assert not node.has_role('role4')
        assert len(node.roles) == 3
        node.remove_role('role1')
        assert not node.has_role('role1')
        assert len(node.roles) == 2
        node.remove_role('role1')
        assert not node.has_role('role1')
        assert len(node.roles) == 2
        assert node.has_role('role2')
        node.remove_role('role1')
        node.remove_role('role2')
        node.remove_role('role3')
        assert not node.has_role('role')
        assert len(node.roles) == 0

    def test_tags(self, nodes: List[NodeDescriptor]):
        node = nodes[0]
        node.add_tag('tag1', 'value1')
        node.add_tag('tag1', 'value2')
        assert node.has_tag('tag1')
        assert node.has_tag('tag1', 'value1')
        assert node.has_tag('tag1', 'value2')
        assert not node.has_tag('tag1', 'value3')
        assert not node.has_tag('tag2', 'value3')
        assert not node.has_tag('tag2')
        node.add_tag('tag2', 'value1')
        node.add_tag('tag2', 'value2')
        node.add_tag('tag3', 'value1')
        node.add_tag('tag4', 'value1')
        node.add_tag('tag4', 'value1')
        assert node.has_tag('tag2')
        assert not node.has_tag('tag5')
        assert not node.has_tag('tag4', 'value2')
        assert not node.has_tag('tag', 'value1')
        node.remove_tag('tag4')
        assert not node.has_tag('tag4', 'value1')
        assert not node.has_tag('tag4', 'value2')
        assert not node.has_tag('tag4')
        assert node.has_tag('tag1')
        node.remove_tag('tag4')
        assert not node.has_tag('tag4')
        node.remove_tag('tag1', 'invalid')
        assert node.has_tag('tag1')
        node.remove_tag('tag3', 'value1')
        assert not node.has_tag('tag3')


class TestNodeRepositoryOperator:
    pass




if __name__ == "__main__":
    pytest.main(['-v', __file__])
