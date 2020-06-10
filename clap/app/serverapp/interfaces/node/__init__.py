from .interface import *

__module_name__ = 'Node'
__module_description__ = 'Create and manages nodes at different clouds'
__register__ = None
__routes__ = [
    ('', node_index, ['GET', 'POST']),
    ('get-node-list', get_node_list, ['GET', 'POST']),
    ('templates', get_node_templates, ['GET', 'POST']),
]