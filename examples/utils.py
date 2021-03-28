COLORS = dict(
    red='\033[31m',
    green='\033[32m',
    yellow='\033[33m',
    blue='\033[34m',
    magenta='\033[35m',
    cyan='\033[36m',
    reset='\033[0m'
)

def colored_print(message: str, text_color: str = None):
    if not text_color:
        print(message)
        return

    text_color = text_color.lower()
    try:
        print(f"{COLORS[text_color]}{message}{COLORS['reset']}")
    except KeyError:
        print(f'Invalid color `{text_color}`')
        raise

def red_print(message: str):
    colored_print(message, text_color='red')

def green_print(message: str):
    colored_print(message, text_color='green')

def yellow_print(message: str):
    colored_print(message, text_color='yellow')

def blue_print(message: str):
    colored_print(message, text_color='blue')

def magenta_print(message: str):
    colored_print(message, text_color='magenta')

def cyan_print(message: str):
    colored_print(message, text_color='cyan')