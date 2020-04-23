import os.path

import tinydb
from abc import abstractmethod
from functools import reduce
from typing import List, Any, Dict

from clap.common.config import Defaults
from clap.common.exceptions import TableAlreadyExists
from clap.common.utils import Struct, path_extend
from contextlib import contextmanager


# Configuration Defaults


# Entries
class AbstractEntry(Struct):
    """ This class represent a single entry in the Repository. Basically its a dictionary that is a serializable and
    is a generic container for a data format. Implementations derived from this class represent specific element types in a repository.
    Objects (variables) inside this class can be accessed using `element['variable']` or `element.variable` notations
    """

    def __init__(self, *args, **kwargs):
        """ Create entry element and populates the class with the keyworded values from kwargs.
        Elements can be accessed by `class['element']` or `class.element` notations

        :param args: Additional arguments to be used
        :param kwargs: Keyworded values to populate the class
        """
        super(AbstractEntry, self).__init__(None, **kwargs)


# Repositories
class AbstractRepository:
    """Base class for implementing repositories and their operations. The repository is similar to tabled data models.
    The elements are every object inherited from ``AbstractEntry`` class, which are basically, dictionary types.
    Tables hold a set of elements of the same type and must be created before adding elements.
    The repository then, implement a set of methods to create, retrieve, update and delete elements and tables from the database.

    """
    __repository_id__ = 'abstractrepository'
    __repository_name__ = 'Abstract Repository'
    __repository_version__ = '0.0.1'

    def __init__(self, repository: str, create_repository: bool, storage_type: str = None, *args, **kwargs):
        """ The implementation of every derived class must have

        :param repository: Repository name of path, depending on the implementation
        :type repository: str
        :param create_repository: Boolean indicating if the database shall be created before operating. Diferent implementations may diver their behavior depending on thisflag
        :type create_repository: bool
        :param storage_type: Descriptive name from the type of the storage (such as json, yaml, binary, etc)
        :type storage_type: str
        :param args: Additional arguments to be used
        :param kwargs: Additional keyword arguments to be used
        """
        self.repository = repository
        self.create_repository = create_repository
        self.storage_type = storage_type

    @abstractmethod
    def open_connection(self, *args, **kwargs):
        raise NotImplementedError

    @abstractmethod
    def close_connection(self, *args, **kwargs):
        raise NotImplementedError

    @abstractmethod
    def create_table(self, table: str, *args, **kwargs):
        """ Create a table in the repository  (a container to hold elements of the same type)

        :param table: Name of the table to be created
        :type table: str
        :param args: Additional arguments to be used
        :param kwargs: Additional keyword arguments to be used
        :return: None
        """
        raise NotImplementedError

    @abstractmethod
    def retrieve_tables(self) -> List[str]:
        """ Retrieve tables from the repository.

        :return: List with the table names
        :rtype: List[str]
        """
        raise NotImplementedError

    @abstractmethod
    def exists_table(self, table: str, *args, **kwargs) -> bool:
        """ Check if a table exists in the repsitory

        :param table: Name of the table to be checked
        :type table: str
        :param args: Additional arguments to be used
        :param kwargs: Additional keyword arguments to be used
        :return: True if table exists and False otherwise
        :rtype: bool
        """

        raise NotImplementedError

    @abstractmethod
    def drop_tables(self, tables: List[str], *args, **kwargs):
        """ Delete tables from the repository

        :param tables: Name of the tables to delete
        :type tables: List[str]
        :param args: Additional arguments to be used
        :param kwargs: Additional keyword arguments to be used
        :return: None
        """
        raise NotImplementedError

    @abstractmethod
    def create_element(self, table: str, obj: AbstractEntry, *args, **kwargs):
        """ Insert a new element in the table

        :param table: Name of the table to create the entry
        :type table: str
        :param obj: Entry to be inserted, class derived from ``AbstractEntry``
        :type obj: AbstractEntry
        :param args: Additional arguments to be used
        :param kwargs: Additional keyword arguments to be used
        :return: None
        """
        raise NotImplementedError

    @abstractmethod
    def retrieve_elements(self, table: str, cast_to: type, **where) -> List[Any]:
        """ Retrieve elements from a table in the database, basing on a simle keyworded query

        :param table: Name of the table to retrieve the elements
        :type table: str
        :param cast_to: Type to cast the elements after retrieval from the database (Derived from ``AbstractEntry`)
        :type cast_to: type
        :param where: Keyworded clauses which specify conditions, the key is he field name (from the entry) and value is the data associated.
            Elements that match the conditions will be retrieved (e.g. person_id='person1')
        :type where: Dict[str,Any]
        :return: List of the elements that matches the creteria
        :rtype: List[Any]
        """
        raise NotImplementedError

    @abstractmethod
    def update_element(self, table: str, obj: AbstractEntry, **where):
        """ Update an element from the database table with another one, matching a criteria

        :param table: Name of the table do modify the element
        :type table: str
        :param obj: New element to be inserted (Derived from ``AbstractEntry`)
        :type obj: AbstractEntry
        :param where: Keyworded clauses which specify conditions, the key is he field name (from the entry) and value is the data associated.
            Elements that match the conditions will be retrieved (e.g. person_id='person1')
        :type where: Dict[str,Any]
        :return: None
        """

        raise NotImplementedError

    @abstractmethod
    def drop_elements(self, table: str, **where):
        """ Delete elements from a database table that matches a criteria

        :param table: Name of the table that elements will be deleted
        :type table: str
        :param where:
        :param where: Keyworded clauses which specify conditions, the key is he field name (from the entry) and value is the data associated.
            Elements that match the conditions will be retrieved (e.g. person_id='person1')
        :type where: Dict[str,Any]
        :return: None
        """
        raise NotImplementedError


class TinyDBRepository(AbstractRepository):
    """ Repository implementation using the tinydb, document-oriented database.
    """

    __repository_id__ = 'tinydb'
    __repository_name__ = 'TinyDB Repository'
    __repository_version__ = '0.1.0'

    DEFAULT_STORAGE_TYPE = 'json'

    __storage_types_map = {
        'json': tinydb.JSONStorage
    }

    def __init__(self, repository_path: str, create_repository: bool, storage_type: str = DEFAULT_STORAGE_TYPE,
                 *args, **kwargs):
        """ Create a new repository that uses tinydb database

        :param repository_path: Path to the repository file
        :type repository_path: str
        :param create_repository: Boolean indicating if a new repository shall be created. Be careful,
        if the repository already exists it will be overwrite.
        :type create_repository: bool
        :param storage_type: Type that the repository will be save (default is 'json')
        :type storage_type: str
        :param args: Additional arguments to be used
        :param kwargs: Additional keyword arguments to be used
        """
        super(TinyDBRepository, self).__init__(repository_path, create_repository, storage_type)
        self.repository = path_extend(self.repository)
        if create_repository:
            open(self.repository, 'w+')
        self.db = tinydb.database.TinyDB(self.repository, storage=self.__storage_types_map[self.storage_type])

    def open_connection(self, *args, **kwargs) -> AbstractRepository:
        return self

    def close_connection(self, *args, **kwargs):
        pass

    def create_table(self, table: str, *args, **kwargs):
        """ Create a new table in the database

        :param table: Name of the table to be created
        :type table:  str
        :param args: Additional arguments to be used
        :param kwargs: Additional keyword arguments to be used
        :return: None
        :raises TableAlreadyExists: if a table with the same name already exists in the database
        """

        if self.exists_table(table):
            raise TableAlreadyExists(table)
        self.db.table(table)

    def retrieve_tables(self) -> List[str]:
        """ Get the names of all tables in the database

        :return: List with the table names
        :rtype: List[str]
        """
        return list(self.db.tables())

    def exists_table(self, table: str, *args, **kwargs) -> bool:
        """ Check if a table already exists in database

        :param table: Name of the table
        :type table: str
        :param args: Additional arguments to be used
        :param kwargs: Additional keyword arguments to be used
        :return: True if the table exists, False otherwise
        :rtype: bool
        """
        return True if table in self.db.tables() else False

    def drop_tables(self, tables: List[str], *args, **kwargs):
        """ Delete tables from the database

        :param tables: Names of the tables to be removed
        :type tables: List[str]
        :param args: Additional arguments to be used
        :param kwargs: Additional keyword arguments to be used
        :return: None
        """
        for table in tables:
            self.db.purge_table(table)

    def create_element(self, table: str, obj: AbstractEntry, *args, **kwargs):
        """ Insert elements in a database table

        :param table: Name of the table to insert the element
        :type table: str
        :param obj: Element to be inserted (derived from ``AbstractEntry``)
        :type obj: AbstractEntry
        :param args: Additional arguments to be used
        :param kwargs: Additional keyword arguments to be used
        :return: None
        :raises ValueError: If table name is invalid
        """
        if not self.exists_table(table):
            raise ValueError("Invalid table with name `{}` in repository `{}`".format(table, self.repository))
        self.db.table(table).insert(obj)

    def retrieve_elements(self, table: str, cast_to: type = dict, **where) -> List[Any]:
        """ Retrieve elements from the database that match a criteria

        :param table: Name of the table to retrieve the elements
        :type table: str
        :param cast_to: Type that the elements will be casted after retrieved (derived from ``AbstractEntry``)
        :type cast_to: type
        :param where: Keyworded clauses which specify conditions. The key is the field name (from the entry) and value is the data associated.
            Elements that match the conditions will be retrieved (e.g. person_id='person1').
            If no conditions are passed all elements are retrieved
        :type where: Dict[str,Any]
        :return: List with the elements retrieved, properly casted to the type passed
        :rtype: List[Any]
        :raises ValueError: If table name is invalid
        """

        if not self.exists_table(table):
            raise ValueError("Invalid table with name `{}` in repository `{}`".format(table, self.repository))
        table = self.db.table(table)
        if len(where) == 0:
            return [cast_to(**element) for element in table.all()]
        query = tinydb.Query()
        lmd = lambda x, y: x & y
        itens = [getattr(query, key) == val for key, val in where.items()]
        red = reduce(lmd, itens)
        elements = [element for element in table.search(red)]
        casted = [cast_to(**element) for element in elements]
        return casted

    def update_element(self, table: str, obj: AbstractEntry, **where):
        """ Update an element (or elements) matching some creiterias, replacing it with another one.

        :param table: Name of the table that the element will be updated
        :type table: str
        :param obj: Entry to be inserted (derived from ``AbstractEntry``)
        :type obj: AbstractEntry
        :param where: Keyworded clauses which specify conditions. The key is the field name (from the entry) and value is the data associated.
            Elements that match the conditions will be retrieved (e.g. person_id='person1').
            If no conditions are the first retrived element in the table will be updated
        :return: None
        :raises ValueError: If table name is invalid
        """
        if not self.exists_table(table):
            raise ValueError("Invalid table with name `{}` in repository `{}`".format(table, self.repository))
        table = self.db.table(table)
        if where:
            query = tinydb.Query()
            element = table.get(
                reduce(lambda x, y: x & y, [getattr(query, key) == val for key, val in where.items()]))
        else:
            element = next(iter(table.all()), None)

        if not element:
            raise ValueError("There is no element to update that matches the query: `{}`".format(where))
        element.update(obj)
        table.write_back([element])

    # TODO remove without clause!
    def drop_elements(self, table: str, **where):
        """ Remove elements from a table

        :param table: Name of the table that the elements will be removed
        :type table: str
        :param where: Keyworded clauses which specify conditions. The key is the field name (from the entry) and value is the data associated.
            Elements that match the conditions will be retrieved (e.g. person_id='person1').
            A clause must be specified!
        :return:
        :raises ValueError: If table name is invalid
        """
        if not self.exists_table(table):
            raise ValueError("Invalid table with name `{}` in repository `{}`".format(table, self.repository))
        table = self.db.table(table)
        query = tinydb.Query()
        table.remove(reduce(lambda x, y: x & y, [getattr(query, key) == val for key, val in where.items()]))


# Generic methods
def generic_read_entry(info_type: type, repository: AbstractRepository, table: str, **where) -> list:
    """ Helper method to read an entry from a repository

    :param info_type: Type of the entry that will be read. The type of the element must derive from AbstractDescriptorEntry
    :type info_type: AbstractEntry
    :param repository: Repository object used to read the element from
    :type repository: AbstractRepository
    :param table: Table of the repository where the element will be retrieved
    :type table: str
    :param where: The clauses to be matched when searching an entry
    :type where: Dict[Any, Any]
    :return: List of elements matching the criteria passed. The elements are all converted to `info_type` argument type
    :rtype: list
    """
    return repository.retrieve_elements(table, info_type, **where)


def generic_write_entry(info: AbstractEntry, repository: AbstractRepository, table: str,
                        create: bool = False, **where):
    """ Helper method to write an entry in a repository

    :param info: Information to be written in repository (derived from AbstractDescriptorEntry class)
    :type info: AbstractEntry
    :param repository: Repository object used to write the element to
    :type repository: AbstractRepository
    :param table: Table of the repository where the element will be created/updated
    :type table: str
    :param create: If true it will create a element in the repository and if false, it will update. If the repository implementation supports insertion upon update, the element will be created when updating, else an exception will be raised
    :type create: bool
    :param where: The clauses to be matched when updating an entry
    :type where: Dict[Any, Any]
    """
    if create:
        repository.create_element(table, info)
    else:
        repository.update_element(table, info, **where)


def check_and_create_table(repository: AbstractRepository, table_name: str, exists: str) -> bool:
    """Check if table exists and creates table based on `exists` variable policy. The table is always created if it does not exists

    :param repository: Repository that the table will be created
    :type repository: AbstractRepository
    :param table_name: Name of the table to be created
    :type table_name: str
    :param exists: Policy taken when the table already exists. This parameter can be:
        'pass' (default): will do nothing
        'fail': will raise `TableAlreadyExists` exception
        'overwrite': will drop the old table and create a new table
    :return: True indicating if the a new table was created, False otherwise
    :rtype: bool
    :raises:
    TableAlreadyExists
        If table already exists and 'fail' parameter is passed
    ValueError
        If exists parameter is invalid
    """
    if repository.exists_table(table_name):
        if exists == 'fail':
            raise TableAlreadyExists(table_name)
        elif exists == 'overwrite':
            repository.drop_tables([table_name])
            repository.create_table(table_name)
            return True
        elif exists == 'pass':
            return False
        else:
            raise Exception("Invalid operation to perform if table already exists: `{}`".format(exists))
    else:
        repository.create_table(table_name)
        return True


@contextmanager
def get_repository_connection(repository: AbstractRepository, *args, **kwargs):
    conn = repository.open_connection(*args, **kwargs)
    try:
        yield conn
    finally:
        repository.close_connection()


class RepositoryFactory:
    @staticmethod
    def get_repository(repository: str, repository_type: str = Defaults.REPOSITORY_TYPE,
                       storage_type: str = None, create_new: bool = True) -> AbstractRepository:
        """ Get a repository, based on a implementation of the ``AbstractRepository`` class.

        :param repository: Name of the repository to get
        :type repository: str
        :param repository_type: Repository implementation type (default is ``tinydb`` repository imlpementation)
        :type repository_type: str
        :param storage_type: Type of the storage (default is json)
        :type storage_type: str
        :param create_new: True to create a new repository (overwriting an existent one), false otherwise (default is True)
        :type create_new: bool
        :return: The repository in the specified implementation (derived from ``AbstractRepository``)
        :rtype: AbstractRepository
        :raises ValueError: If the repository implementation type is invalid
        """

        if repository_type == 'tinydb':
            repository = path_extend(repository)
            if os.path.isfile(repository) and create_new:
                create_new = False

            return TinyDBRepository(repository, create_new,
                                    TinyDBRepository.DEFAULT_STORAGE_TYPE if storage_type is None else storage_type)
        else:
            raise ValueError("Invalid repository type `{}`".format(repository_type))

    @staticmethod
    def exists_repository(repository: str, repository_type=Defaults.REPOSITORY_TYPE) -> bool:
        """ Check if a repository already exists

        :param repository: Name of the repository
        :type repository: str
        :param repository_type: Repository implementation type (default is ``tinydb`` repository imlpementation)
        :type repository_type: str
        :return: True of the repository already exists and false otherwise
        :rtype: bool
        :raises ValueError: If the repository implementation type is invalid
        """
        if repository_type == 'tinydb':
            repository = path_extend(repository)
            return os.path.exists(repository) and os.path.isfile(repository)
        else:
            raise ValueError("Invalid repository type `{}`".format(repository_type))