import argparse

from clap.common.module import AbstractParser
from clap.common.utils import log
from .module import list_templates

class TagsParser(AbstractParser):
    def get_name(self) -> str:
        return "template"
    
    def get_help(self) -> str:
        return "Templates information"

    def add_parser(self, commands_parser: argparse._SubParsersAction):
        template_subcom_parser = commands_parser.add_parser('list', help='List instance templates')
        template_subcom_parser.set_defaults(func=self.commands_list_templates)


    def commands_list_templates(self, namespace: argparse.Namespace):
        templates = list_templates()
        len_templates = len(templates)

        print("Instance Templates")
        for inst_name, inst_values in templates.items():
            try:
                print("* Instance: `{}`".format(inst_name))
                print("    cloud: {}".format(inst_values['provider']))
                print("    login: {}".format(inst_values['login']))
            except KeyError as e:
                log.error("Error with instance template `{}`: {}".format(inst_name, e))
                len_templates -= 1

        print("Listed {} instance templates".format(len_templates))

        return 0