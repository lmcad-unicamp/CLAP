import argparse
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