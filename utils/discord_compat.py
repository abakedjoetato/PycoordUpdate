"""
Discord Library Compatibility Layer

This module provides compatibility between different Discord library versions (discord.py vs py-cord).
It maps API differences and provides fallbacks for missing features to ensure cogs work seamlessly
regardless of which library version is being used.
"""
import logging
import importlib
import sys
from typing import Any, Optional, Union, Dict, List

logger = logging.getLogger(__name__)

# Detect which Discord library we're using
USING_PYCORD = False
USING_DISCORDPY = False

try:
    import discord
    if hasattr(discord, '__title__') and discord.__title__ == 'py-cord':
        USING_PYCORD = True
        logger.info("Detected py-cord library")
    else:
        USING_DISCORDPY = True
        logger.info("Detected discord.py library")
except ImportError:
    logger.error("Failed to import discord library")

# Define our compatibility classes
class AppCommandOptionType:
    """Discord application command option types"""
    STRING = 3
    INTEGER = 4
    BOOLEAN = 5
    USER = 6
    CHANNEL = 7
    ROLE = 8
    MENTIONABLE = 9
    NUMBER = 10
    ATTACHMENT = 11

# Compatibility imports and definitions
if USING_PYCORD:
    try:
        # For py-cord
        from discord.commands import Option, OptionChoice
        # Import the actual CommandOptionType from py-cord
        try:
            from discord.enums import CommandOptionType
            # Override our AppCommandOptionType with the actual one
            AppCommandOptionType = CommandOptionType
        except ImportError:
            logger.warning("Could not import CommandOptionType from py-cord, using fallback")
    except ImportError as e:
        logger.error(f"Error importing py-cord components: {e}")

# Set up compatibility layers in discord if needed
if USING_DISCORDPY:
    try:
        # For discord.py, add our compatibility type to the discord module
        if not hasattr(discord, 'app_commands'):
            # Create a mock app_commands module
            class MockAppCommands:
                pass
            
            # Add describe method
            def describe(**kwargs):
                def decorator(func):
                    return func
                return decorator
                
            # Add our compatibility classes
            MockAppCommands.describe = describe
            # Add to discord module
            discord.app_commands = MockAppCommands()
            logger.info("Added compatibility app_commands to discord")
    except Exception as e:
        logger.error(f"Error setting up discord.py compatibility: {e}")

def create_option(name: str, 
                 description: str, 
                 option_type: Any, 
                 required: bool = False, 
                 choices: Optional[List[Dict[str, Any]]] = None) -> Any:
    """Create a command option compatible with both libraries"""
    if USING_PYCORD:
        from discord.commands import Option
        return Option(
            name=name,
            description=description,
            type=option_type,
            required=required,
            choices=choices if choices is not None else []
        )
    elif USING_DISCORDPY:
        # Discord.py uses a different approach with app_commands.describe
        # This will be handled differently in the commands themselves
        return {
            'name': name,
            'description': description,
            'type': option_type,
            'required': required,
            'choices': choices if choices is not None else []
        }
    return None

# Additional compatibility functions can be added here
def get_app_commands_module():
    """Get the appropriate app_commands module"""
    if USING_PYCORD:
        # For py-cord, use discord.commands
        return getattr(discord, 'commands', None)
    elif USING_DISCORDPY:
        # For discord.py, use discord.app_commands
        return getattr(discord, 'app_commands', None)
    return None