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

# Import discord here to ensure it's available for the entire module
try:
    import discord
except ImportError:
    logger.error("Failed to import discord library")
    discord = None

# Detect which Discord library we're using
USING_PYCORD = False
USING_DISCORDPY = False

if discord is not None:
    if hasattr(discord, '__title__') and discord.__title__ == 'py-cord':
        USING_PYCORD = True
        logger.info("Detected py-cord library")
    else:
        USING_DISCORDPY = True
        logger.info("Detected discord.py library")

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
        
        # Attempt to import CommandOptionType, but don't raise an error if not found
        CommandOptionType = None
        try:
            # Check if discord.enums exists and has CommandOptionType
            if hasattr(discord, 'enums') and hasattr(discord.enums, 'CommandOptionType'):
                from discord.enums import CommandOptionType
                # Override our AppCommandOptionType with the actual one
                AppCommandOptionType = CommandOptionType
                logger.info("Successfully imported CommandOptionType from discord.enums")
            else:
                logger.warning("discord.enums.CommandOptionType not available, using fallback")
        except (ImportError, AttributeError):
            logger.warning("Could not import CommandOptionType from py-cord, using fallback")
    except ImportError as e:
        logger.error(f"Error importing py-cord components: {e}")

# Define a mock app_commands module
class MockAppCommands:
    """Mock app_commands module for compatibility"""
    def __init__(self):
        self.logger = logger
    
    def command(self, name=None, description=None):
        def decorator(func):
            return func
        return decorator
    
    def describe(self, **kwargs):
        def decorator(func):
            return func
        return decorator
    
    def autocomplete(self, callback=None):
        def decorator(func):
            return func
        return decorator

# Set up compatibility layers in discord if needed
if USING_DISCORDPY and discord is not None:
    try:
        # For discord.py, add our compatibility type to the discord module
        if not hasattr(discord, 'app_commands'):
            # Create and add our mock app_commands
            mock_app_commands = MockAppCommands()
            # Use setattr to avoid direct attribute assignment that might be flagged by LSP
            setattr(discord, 'app_commands', mock_app_commands)
            logger.info("Added compatibility app_commands to discord module")
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