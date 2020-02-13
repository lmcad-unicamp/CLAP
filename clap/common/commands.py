import argparse
from abc import abstractmethod


class AbstractParser:
    @abstractmethod
    def get_parser(self, commands_parser: argparse._SubParsersAction):
        pass