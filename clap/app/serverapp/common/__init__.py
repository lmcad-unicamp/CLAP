from .interface import *

__module_name__ = 'common'
__module_description__ = 'Common'
__register__ = None
__routes__ = [
    ('', index, ['GET', 'POST']),
    ('index', index, ['GET', 'POST']),
    ('configuration', get_configuration_html, ['GET', 'POST']),
    ('get-configuration', get_configuration, ['GET', 'POST']),
    ('save-configuration', save_configuration, ['GET', 'POST']),
    ('get-navigation-items', get_navigation_items, ['GET', 'POST']),
    ('get-module-cards-html', get_module_cards_html, ['GET', 'POST'])
]