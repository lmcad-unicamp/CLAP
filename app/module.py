import click
import os
import inspect
import pkgutil

from typing import List


class clap_command(click.Group):
    def __init__(self, group):
        self.__dict__ = group.__dict__.copy()


class ModuleInterface:
    def __init__(self, paths: List[str] = None):
        self.paths = paths or [os.path.join(os.path.dirname(__file__), 'modules')]

    def find_modules(self) -> List[clap_command]:
        modules = []
        for importer, package_name, _ in pkgutil.iter_modules(self.paths):
            if 'pycache' in package_name or '.' in package_name or package_name.startswith('__'):
                continue
            try:
                mod = importer.find_module(package_name).load_module(package_name)
                modules += [obj for _, obj in inspect.getmembers(mod, predicate=lambda x: type(x) is clap_command)]
            except Exception as e:
                print(f'Error importing module with name `{package_name}`')
                raise e
        return modules
