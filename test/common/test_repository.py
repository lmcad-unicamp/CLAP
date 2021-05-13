import tempfile
import pytest
import random

from typing import List, Dict
from dataclasses import dataclass, asdict
from common.utils import path_extend
from common.repository import InvalidEntryError


@dataclass
class Entry(object):
    value_int: int
    value_float: float
    value_str: str

    def __eq__(self, other):
        return self.value_int == other.value_int and self.value_float == other.value_float and self.value_str == other.value_str


@pytest.fixture(scope="function", ids=['entries1000'], params=[1000])
def entries(request) -> Dict[str, Entry]:
    return {str(i): Entry(i, float(i), str(i)) for i in range(0, request.param)}


@pytest.fixture(scope="module", ids=['tables10'], params=[10])
def table_names(request) -> List[str]:
    return [f"test-table-{i}" for i in range(0, request.param)]


def make_test_case(repository_class):
    class Repository:
        @pytest.fixture(scope='function')
        def _repository(self):
            with tempfile.TemporaryDirectory() as datadir:
                repository_path = path_extend(datadir, 'test.db')
                yield repository_class(repository_path=repository_path, commit_on_close=True)

        def test_open_close(self, _repository, table_names):
            for table in table_names:
                _repository.open(table)
                _repository.close()

        def test_open_close_context(self, _repository, table_names):
            for table in table_names:
                with _repository.connect(table):
                    pass

        @pytest.mark.dependency(depends=["test_open_close", "test_open_close_context"])
        @pytest.fixture(scope='function')
        def repository_with_data(self, _repository, table_names, entries):
            for table in table_names:
                with _repository.connect(table) as db:
                    for key, entry in entries.items():
                        db.upsert(key, asdict(entry))
            yield _repository

        def test_get_all(self, repository_with_data, table_names, entries):
            for table in table_names:
                with repository_with_data.connect(table) as db:
                    elements = {key: Entry(**entry) for key, entry in db.get_all().items()}
                    assert len(elements) == len(entries)
                    for key, entry in elements.items():
                        assert key in entries
                        assert entry == entries[key]

        @pytest.mark.parametrize("qtde", [10])
        def test_get_random_element(self, repository_with_data, table_names, entries, qtde):
            for table in table_names:
                with repository_with_data.connect(table) as db:
                    for i in range(0, qtde):
                        key, entry = random.choice(list(entries.items()))
                        got_value = Entry(**db.get(key))
                        assert got_value == entry

        @pytest.mark.parametrize("qtde", [10])
        def test_get_multiple_random_elements(self, repository_with_data, table_names, entries, qtde):
            for table in table_names:
                with repository_with_data.connect(table) as db:
                    keys = random.sample(list(entries.keys()), qtde)
                    got_values = {key: Entry(**entry) for key, entry in db.get_multiple(keys).items()}
                    for key in keys:
                        assert entries[key] == got_values[key]

        @pytest.mark.parametrize("qtde", [10])
        def test_remove_random_element(self, repository_with_data, table_names, entries, qtde):
            for table in table_names:
                with repository_with_data.connect(table) as db:
                    for i in range(0, qtde):
                        key, entry = random.choice(list(entries.items()))
                        entries.pop(key)
                        db.remove(key)
                        with pytest.raises(InvalidEntryError):
                            db.get(key)

        @pytest.mark.parametrize("qtde", [10])
        def test_remove_multiple_random_elements(self, repository_with_data, table_names, entries, qtde):
            for table in table_names:
                with repository_with_data.connect(table) as db:
                    keys = random.sample(list(entries.keys()), qtde)
                    db.remove_multiple(keys)
                    for key in keys:
                        with pytest.raises(InvalidEntryError):
                            db.get(key)

        def test_invalid_get_values(self, repository_with_data, table_names, entries):
            for table in table_names:
                with repository_with_data.connect(table) as db:
                    with pytest.raises(InvalidEntryError):
                        db.get('invalid_value-1')
                    with pytest.raises(InvalidEntryError):
                        db.get_multiple(['invalid_value-1', 'invalid_value-2'])
                    with pytest.raises(InvalidEntryError):
                        db.get_multiple(['invalid_value-1', 'invalid_value-2'] + list(entries.keys()))

        def test_invalid_removal(self, repository_with_data, table_names):
            for table in table_names:
                with repository_with_data.connect(table) as db:
                    with pytest.raises(InvalidEntryError):
                        db.remove('invalid_value-1')
                    with pytest.raises(InvalidEntryError):
                        db.remove_multiple(['invalid_value-1', 'deadbeef'])

    return Repository
