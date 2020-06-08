#!/usr/bin/env python3

import os
import pytest
import unittest
import tempfile
import random

from clap.common import repository
from clap.common import cluster_repository

class TestControlInfo(repository.AbstractEntry):
    """ This class holds control information used to create nodes and cluster in the repository (database).
    It holds an **incremental index** to be used to create such elements.
    """

    def __init__(self, *args, **kwargs):
        self.control_idx = 0
        self.auto_increment_val = 0
        super(TestControlInfo, self).__init__(*args, **kwargs)


class TestInfo(repository.AbstractEntry):
    """ This class holds control information used to create nodes and cluster in the repository (database).
    It holds an **incremental index** to be used to create such elements.
    """

    def __init__(self, *args, **kwargs):
        self.test_id = 0
        self.test_name = None
        self.test_value = None
        self.extra = None
        super(TestInfo, self).__init__(*args, **kwargs)


class TestSqliteRepositoryTables(unittest.TestCase):
    def setUp(self):
        self.path = tempfile.mktemp(suffix='.db')
        self.repository = repository.RepositoryFactory.get_repository(self.path, repository_type='sqlite')
        self.create_tables()
    
    def tearDown(self):
        os.unlink(self.path)

    def create_tables(self):
        with repository.get_repository_connection(self.repository) as rep:
            repository.check_and_create_table(rep, 'control', 'pass')
            repository.check_and_create_table(rep, 'values', 'pass')

    def test_retrieve_tables(self):
        with repository.get_repository_connection(self.repository) as rep:
            expecteds = set(['default', 'control', 'values'])
            self.assertSetEqual(set(rep.retrieve_tables()), expecteds)

    def test_exists_tables(self):
        with repository.get_repository_connection(self.repository) as rep:
            expecteds = set(['control', 'values'])
            for e in expecteds:
                self.assertTrue(rep.exists_table(e))


class TestSqliteRepositoryElements(unittest.TestCase):
    def setUp(self):
        self.path = tempfile.mktemp(suffix='.db')
        self.repository = repository.RepositoryFactory.get_repository(self.path, repository_type='sqlite')
        self.create_tables()
        self.num_elements = 100
        self.test_infos = [TestInfo(test_id='test-{}'.format(i), test_name='name-{}'.format(i), test_value=str(random.random())[2:], 
                                    extra={'twice': i*2, 'another_dict': {'exp': i*i}}) for i in range(0, self.num_elements)]

    def tearDown(self):
        os.unlink(self.path)

    def create_tables(self):
        with repository.get_repository_connection(self.repository) as rep:
            if repository.check_and_create_table(rep, 'control', 'pass'):
                rep.create_element('control', TestControlInfo())
            repository.check_and_create_table(rep, 'values', 'pass')

    def element_insert(self, rep):
        for element in self.test_infos:
            rep.create_element('values', element)

    def test_elements_insertion_01(self):
        with repository.get_repository_connection(self.repository) as rep:
            self.element_insert(rep)
            retrieved_elements = rep.retrieve_elements('values', TestInfo)
            self.assertEqual(len(retrieved_elements), self.num_elements)

            test_infos = sorted(self.test_infos, key=lambda x: x.test_id)
            retrieved_elements = sorted(retrieved_elements, key=lambda x: x.test_id)
            
            for i in range(0, self.num_elements):
                val1 = test_infos[i]
                val2 = retrieved_elements[i]
                self.assertEqual(val1.test_id, val2.test_id)
                self.assertEqual(val1.test_name, val2.test_name)
                self.assertEqual(val1.test_value, val2.test_value)


if __name__ == "__main__":
    pytest.main(['-v', __file__])