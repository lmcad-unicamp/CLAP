class RepositoryError(Exception):
    pass


class TableAlreadyExists(RepositoryError):
    def __init__(self, table_name: str, *args, **kwargs):
        self.table_name = table_name

    def __str__(self):
        return "Table `{}` already exists.".format(self.table_name)


class ModuleError(Exception):
    pass


class ValueNotFound(RepositoryError):
    pass


class ClusterError(Exception):
    pass


class ClusterCreationError(ClusterError):
    pass

class ConfigurationError(Exception):
    """ This exception is raised if any invalid value or type exists in configuration files
    """
    pass