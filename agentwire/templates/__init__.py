"""Template loader for AgentWire web interface."""

import importlib.resources


def get_template(name: str) -> str:
    """Load a template file by name.
    
    Args:
        name: Template name (e.g., 'dashboard.html', 'room.html')
        
    Returns:
        Template content as string
    """
    return importlib.resources.files(__package__).joinpath(name).read_text()
