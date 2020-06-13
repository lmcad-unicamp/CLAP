from clap.common.platform import MultiInstanceAPI, ModuleInterface
from clap.common.config import Defaults


class PlatformFactory:
    """ Class used to create common CLAP interfaces used
    """
    __multi_instance_api__ = None
    __module_iface__ = None

    @staticmethod
    def get_module_interface() -> ModuleInterface:
        """ Get the default ModuleInterface used to pick clap modules

        :return: The modules interface
        :rtype: ModuleInterface
        """
        if not PlatformFactory.__module_iface__:
            PlatformFactory.__module_iface__ = ModuleInterface(module_paths=[Defaults.modules_path])
        return PlatformFactory.__module_iface__

    @staticmethod
    def get_instance_api(platform_db: str = Defaults.PLATFORM_REPOSITORY,
                         repository_type: str = Defaults.REPOSITORY_TYPE,
                         default_driver: str = Defaults.DRIVER_ID) -> MultiInstanceAPI:
        """ Get the default MultiInstance API used to manipulate nodes and modules across different drivers

        :return: The MultiInstanceAPI object to manipulate nodes and modules
        :rtype: MultiInstanceAPI
        """
        if not PlatformFactory.__multi_instance_api__:
            PlatformFactory.__multi_instance_api__ = MultiInstanceAPI(platform_db, repository_type, default_driver)

        return PlatformFactory.__multi_instance_api__


