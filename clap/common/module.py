import argparse
from typing import List
from abc import abstractmethod


class AbstractParser:
    @abstractmethod
    def add_parser(self, commands_parser: argparse._SubParsersAction):
        pass

    @abstractmethod
    def get_name(self) -> str:
        pass
    
    @abstractmethod
    def get_help(self) -> str:
        pass

    def get_module_dependencies(self) -> List[str]:
        return []