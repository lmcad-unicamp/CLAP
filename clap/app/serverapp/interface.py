import pkgutil
import threading

class ServerInterfaces:
    server_interfaces = None

    def __init__(self):
        if ServerInterfaces.server_interfaces is not None:
            return

        ServerInterfaces.server_interfaces = []
        path = '/home/napoli/Documents/Doutorado/Projects/CEPETRO/clap/app/serverapp/interfaces/'
        for importer, package_name, _ in pkgutil.iter_modules([path]): 
            if 'pycache' in package_name:
                continue
            mod =  importer.find_module(package_name).load_module(package_name) 
            ServerInterfaces.server_interfaces.append({
                'module': package_name,
                'name': mod.__module_name__,
                'description': mod.__module_description__,
                'register': mod.__register__,
                'routes': mod.__routes__
            })

    def get_interfaces(self):
        return ServerInterfaces.server_interfaces