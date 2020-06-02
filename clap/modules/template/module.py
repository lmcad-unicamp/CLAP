from typing import Dict, Any, List

from clap.common.factory import PlatformFactory

def list_templates() -> Dict[str, Any]:
    """ Get the instance templates defined in the instance configuration files.

    :return:    Dictionary with instance templates. The keys are the instance name and the value are the values for the instance. 
                The dictionary have the same values for the instance configuration files
    :rtype: Dict[str, Any]
    """
    multi_instance = PlatformFactory.get_instance_api()
    return multi_instance.get_instance_templates()

def list_instance_types() -> List[str]:
    """ Get the instance templates defined in the instance configuration files (only instance names)

    :return:    List with instance template names, from the instance configuration files.
    :rtype: List[str]
    """
    multi_instance = PlatformFactory.get_instance_api()
    return list(multi_instance.get_instance_templates().keys())