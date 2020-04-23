import argparse

from clap.common.module import AbstractParser
from clap.common.utils import log
from .module import node_add_tag, node_remove_tag

class TagsParser(AbstractParser):
    def get_name(self) -> str:
        return "tag"
    
    def get_help(self) -> str:
        return "Tag nodes"

    def add_parser(self, commands_parser: argparse._SubParsersAction):
        tag_subcom_parser = commands_parser.add_parser('add', help='Add tags to nodes')
        tag_subcom_parser.add_argument('tag', action='store', help='Tag to add. Format: key=val')
        tag_subcom_parser.add_argument('node_ids', action='store', nargs='+', help='ID of the nodes to be added to the group')
        tag_subcom_parser.set_defaults(func=self.command_node_add_tag)

        tag_subcom_parser = commands_parser.add_parser('remove', help='Remove tags to nodes')
        tag_subcom_parser.add_argument('tag', action='store', help='List of tags to remove (just key names)')
        tag_subcom_parser.add_argument('node_ids', action='store', nargs='*', help='ID of the nodes to be added to the group')
        tag_subcom_parser.set_defaults(func=self.command_node_remove_tag)


    def command_node_add_tag(self, namespace: argparse.Namespace):
        try:
            tag = {namespace.tag.split('=')[0]: namespace.tag.split('=')[1]}
        except Exception:
            raise Exception("Error mounting tag parameters. Please check the tag parameters passed")

        addeds = node_add_tag(namespace.node_ids, tag)

        if addeds:
            print("Tag `{}` added to nodes `{}`".format(namespace.tag, ', '.join(addeds)))
        else:
            log.error("Tag `{}` were not added to any node!".format(namespace.tag))
            
        return 0

    def command_node_remove_tag(self, namespace: argparse.Namespace):
        removeds =  node_remove_tag(namespace.node_ids, namespace.tag) 

        if removeds: 
            print("Tag `{}` removed from nodes `{}`".format(namespace.tag, ', '.join(removeds)))
        else:
            log.error("Tag `{}` were not removed from any node!".format(namespace.tag))
        return 0