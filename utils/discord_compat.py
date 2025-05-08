"""
Py-cord Compatibility Layer

This module provides a direct interface to py-cord features while maintaining
compatibility with code that expects a discord.py-style API. This ensures
all components work seamlessly regardless of which patterns they were built for.

This implementation fully embraces py-cord (as required by rule #2) while providing
backward compatibility for code that might expect discord.py structures.
"""
import logging
import sys
from typing import Any, Optional, Union, Dict, List, Callable

logger = logging.getLogger(__name__)

# Import discord (py-cord) here to ensure it's available for the entire module
try:
    import discord
    from discord.commands import Option, OptionChoice, SlashCommandGroup
    from discord.ext.commands import Bot, Cog
except ImportError:
    logger.error("Failed to import py-cord library")
    discord = None

# Verify we're using py-cord and log library information
if discord is not None:
    if hasattr(discord, '__title__') and discord.__title__ == 'pycord':
        logger.info(f"Using py-cord {discord.__version__}")
    else:
        logger.warning(f"Expected py-cord but found {getattr(discord, '__title__', 'unknown discord library')}")
        
# Define a constant for py-cord usage to simplify downstream conditionals
USING_PYCORD = discord is not None and hasattr(discord, '__title__') and discord.__title__ == 'pycord'

# Map SlashCommandOptionType to AppCommandOptionType for compatibility
class AppCommandOptionType:
    """Compatibility layer for discord.py's AppCommandOptionType.
    Maps to py-cord's SlashCommandOptionType."""
    
    # Initialize with default values that match discord.py's AppCommandOptionType
    STRING = 3
    INTEGER = 4
    BOOLEAN = 5
    USER = 6
    CHANNEL = 7
    ROLE = 8
    MENTIONABLE = 9
    NUMBER = 10
    ATTACHMENT = 11
    
    def __init__(self):
        # If py-cord is available, load all values from SlashCommandOptionType
        if USING_PYCORD and hasattr(discord, 'enums') and hasattr(discord.enums, 'SlashCommandOptionType'):
            for attr_name in dir(discord.enums.SlashCommandOptionType):
                if not attr_name.startswith('_'):  # Skip private/dunder methods
                    setattr(self, attr_name, getattr(discord.enums.SlashCommandOptionType, attr_name))
            logger.info("Initialized AppCommandOptionType with SlashCommandOptionType values")

# Create a singleton instance for global use
app_command_option_type = AppCommandOptionType()

# Create app_commands compatibility layer for py-cord
class AppCommandsCompatLayer:
    """Maps discord.py's app_commands module to py-cord's commands functionality."""
    
    def __init__(self):
        self.logger = logger
        
        # Set up Choice for autocomplete 
        if USING_PYCORD:
            self.Choice = OptionChoice  # Use py-cord's OptionChoice
        else:
            # Create a mock Choice class if needed (fallback)
            self.Choice = type('Choice', (), {
                '__init__': lambda s, name, value: setattr(s, 'name', name) or setattr(s, 'value', value)
            })
        
    def command(self, name=None, description=None):
        """Maps to py-cord's slash_command"""
        if USING_PYCORD and hasattr(discord, 'commands') and hasattr(discord.commands, 'slash_command'):
            return discord.commands.slash_command(name=name, description=description)
        
        # Fallback decorator if needed
        def decorator(func):
            return func
        return decorator
    
    def describe(self, **kwargs):
        """Maps to py-cord's options system"""
        # In py-cord, options are specified directly with parameters
        def decorator(func):
            # Store the descriptions for later use if needed
            if not hasattr(func, "_descriptions"):
                func._descriptions = {}
            func._descriptions.update(kwargs)
            return func
        return decorator
    
    def autocomplete(self, param_name=None):
        """Maps to py-cord's autocomplete system"""
        def decorator(callback_func):
            # Associate the autocomplete callback with the parameter
            if not hasattr(callback_func, "_param_autocomplete"):
                callback_func._param_autocomplete = {}
            callback_func._param_autocomplete[param_name] = True
            return callback_func
        return decorator
    
    def guild_only(self):
        """Maps to py-cord's guild_only decorator"""
        if USING_PYCORD and hasattr(discord.commands, 'guild_only'):
            return discord.commands.guild_only()
        
        # Fallback decorator 
        def decorator(func):
            func._guild_only = True
            return func
        return decorator

# Create tree compatibility for Bot class
class CommandTreeCompat:
    """Provides a tree attribute compatible with discord.py's app_commands system
    but implemented with py-cord functionality."""
    
    def __init__(self, bot):
        self.bot = bot
    
    async def sync(self, *args, **kwargs):
        """Maps to py-cord's sync_commands"""
        if hasattr(self.bot, 'sync_commands'):
            return await self.bot.sync_commands(*args, **kwargs)
        return []

# Set up key compatibility components for py-cord
if USING_PYCORD:
    # 1. Add app_commands compatibility if not present
    if not hasattr(discord, 'app_commands'):
        app_commands_compat = AppCommandsCompatLayer()
        setattr(discord, 'app_commands', app_commands_compat)
        logger.info("Added app_commands compatibility layer for py-cord")
    
    # 2. Patch Bot class to include tree attribute if needed
    if hasattr(discord.ext, 'commands') and hasattr(discord.ext.commands, 'Bot'):
        original_bot_init = discord.ext.commands.Bot.__init__
        
        def patched_bot_init(self, *args, **kwargs):
            original_bot_init(self, *args, **kwargs)
            if not hasattr(self, 'tree'):
                self.tree = CommandTreeCompat(self)
        
        discord.ext.commands.Bot.__init__ = patched_bot_init
        logger.info("Patched Bot class to add tree support")
    
    # 3. Add hybrid_group compatibility
    if hasattr(discord.ext, 'commands') and not hasattr(discord.ext.commands, 'hybrid_group'):
        def hybrid_group(name=None, **kwargs):
            """Create a hybrid command group compatible with both slash and prefix commands"""
            # For py-cord we need to combine slash_command and group
            group_decorator = discord.ext.commands.group(name=name, **kwargs)
            # Get a slash command decorator if possible
            slash_decorator = discord.commands.slash_command(
                name=name,
                description=kwargs.get('description', 'No description')
            ) if hasattr(discord.commands, 'slash_command') else None
            
            def decorator(func):
                # Apply both decorators
                result = group_decorator(func)
                if slash_decorator and not kwargs.get('invoke_without_command', False):
                    result = slash_decorator(result)
                return result
            return decorator
        
        # Add hybrid_group to discord.ext.commands
        discord.ext.commands.hybrid_group = hybrid_group
        logger.info("Added hybrid_group compatibility to commands")

def create_option(name: str, 
                 description: str, 
                 option_type: Any, 
                 required: bool = False, 
                 choices: Optional[List[Dict[str, Any]]] = None) -> Any:
    """Create a command option compatible with py-cord"""
    if USING_PYCORD:
        try:
            # Format choices for py-cord if provided as dictionaries
            formatted_choices = None
            if choices:
                formatted_choices = [
                    OptionChoice(name=choice.get('name', ''), value=choice.get('value', ''))
                    if isinstance(choice, dict) else choice
                    for choice in choices
                ]
            
            # Create a py-cord Option
            return Option(
                name=name,
                description=description,
                type=option_type,
                required=required,
                choices=formatted_choices if formatted_choices else []
            )
        except Exception as e:
            logger.error(f"Error creating option: {e}")
    
    # Fallback to dictionary format
    return {
        'name': name,
        'description': description,
        'type': option_type,
        'required': required,
        'choices': choices if choices is not None else []
    }

def get_app_commands_module():
    """Get the appropriate app_commands module for the current environment"""
    # For py-cord, this function will return our compatibility layer
    return getattr(discord, 'app_commands', None)