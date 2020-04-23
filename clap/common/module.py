import argparse
from typing import List
from abc import abstractmethod


class AbstractParser:
    @abstractmethod
    def add_parser(self, commands_parser: argparse._SubParsersAction):
        pass