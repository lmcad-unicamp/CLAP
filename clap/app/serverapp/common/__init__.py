from .interface import *

__module_name__ = 'common'
__module_description__ = 'Common'
__register__ = None
__routes__ = [
    ('', index, ['GET', 'POST']),
    ('index', index, ['GET', 'POST']),
    ('get-navigation-html', get_navigation_html, ['GET', 'POST']),
    ('get-module-cards-html', get_module_cards_html, ['GET', 'POST'])
]