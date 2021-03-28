from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import List, Dict


class EntryNotFound(Exception):
    pass


class Repository(ABC):
    repository_name: str = 'AbstractRepository'
    extension: str = ''

    def __init__(self, repository_path: str, commit_on_close: bool = True):
        self.repository_path = repository_path
        self.commit_on_close = commit_on_close

    @contextmanager
    @abstractmethod
    def connect(self, table_name: str, *args, **kwargs) -> 'Repository':
        pass

    @abstractmethod
    def open(self, table_name: str, *args, **kwargs):
        pass

    @abstractmethod
    def close(self):
        pass

    @abstractmethod
    def commit(self):
        pass

    @abstractmethod
    def upsert(self, key: str, obj: dict):
        pass

    @abstractmethod
    def get(self, key: str) -> Dict[str, dict]:
        pass

    @abstractmethod
    def get_multiple(self, key: List[str]) -> dict:
        pass

    @abstractmethod
    def get_all(self) -> Dict[str, dict]:
        pass

    @abstractmethod
    def remove(self, key: str):
        pass

    @abstractmethod
    def clear(self):
        pass


class SQLiteRepository(Repository):
    import json
    from sqlitedict import SqliteDict

    repository_name: str = 'sqlite'
    extension: str = '.db'

    def __init__(self, repository_path: str, commit_on_close: bool = True):
        super().__init__(repository_path, commit_on_close=commit_on_close)
        self.sqlite_repository = None

    @contextmanager
    def connect(self, table_name: str, *args, **kwargs) -> 'SQLiteRepository':
        try:
            yield self.open(table_name, *args, **kwargs)
        finally:
            self.close()

    def open(self, table_name: str, *args, **kwargs):
        self.sqlite_repository = self.SqliteDict(self.repository_path, tablename=table_name, encode=self.json.dumps, decode=self.json.loads)
        return self

    def close(self):
        if self.commit_on_close:
            self.commit()
        self.sqlite_repository.close()
        self.sqlite_repository = None

    def commit(self):
        self.sqlite_repository.commit()

    def upsert(self, key: str, obj: dict):
        self.sqlite_repository[key] = obj

    def get(self, key: str) -> dict:
        try:
            return self.sqlite_repository[key]
        except KeyError:
            raise EntryNotFound(key)

    def get_multiple(self, keys: List[str]) -> Dict[str, dict]:
        values = {key: element for key, element in self.sqlite_repository.items() if key in keys}
        if len(set(keys)) != len(values):
            invalids = set(keys).difference(values.keys())
            raise EntryNotFound(list(invalids))
        return values

    def get_all(self) -> Dict[str, dict]:
        return {key: element for key, element in self.sqlite_repository.items()}

    def remove(self, key: str):
        try:
            del self.sqlite_repository[key]
        except KeyError:
            raise EntryNotFound(key)

    def remove_multiple(self, keys: List[str]):
        for key in keys:
            self.remove(key)

    def clear(self):
        self.sqlite_repository.clear()


class RepositoryOperator(ABC):
    def __init__(self, repository: Repository):
        self.repository = repository
