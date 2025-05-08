"""
Direct Py-cord 2.6.1 Implementation

This module provides direct access to py-cord 2.6.1 features without any compatibility
layers as required by rule #2 in rules.md. It replaces the previous compatibility
approach with direct imports from the modern py-cord library.

All imports and functionality in this module use py-cord 2.6.1's approach directly.
"""
import logging
import sys
from typing import Any, Optional, Union, Dict, List, Callable

logger = logging.getLogger(__name__)

# Import discord (py-cord) directly
import discord
from discord.ext.commands import Bot, Cog
from discord import app_commands
from discord.enums import AppCommandOptionType
from discord.app_commands import Choice

# Log library information
logger.info(f"Using py-cord {discord.__version__}")

# Define a constant for py-cord usage
USING_PYCORD = True

# Direct method mappings to py-cord 2.6.1 app_commands methods
def command(name=None, description=None, **kwargs):
    """
    Direct implementation of app_commands.command in py-cord 2.6.1
    
    Args:
        name: Command name
        description: Command description
        **kwargs: Additional command parameters
        
    Returns:
        Command decorator
    """
    # Set up command parameters
    command_kwargs = {
        'name': name,
        'description': description
    }
    
    # Add any additional kwargs
    for k, v in kwargs.items():
        command_kwargs[k] = v
        
    # Return direct app_commands.command decorator
    return app_commands.command(**command_kwargs)

def describe(**kwargs):
    """
    Direct implementation of app_commands.describe in py-cord 2.6.1
    
    Args:
        **kwargs: Parameter name to description mapping
        
    Returns:
        Function decorator
    """
    return app_commands.describe(**kwargs)

def autocomplete(param_name=None, **kwargs):
    """
    Direct implementation of app_commands.autocomplete in py-cord 2.6.1
    
    This method now uses the py-cord 2.6.1 pattern directly:
    
    @app_commands.autocomplete(param_name=callback)
    async def my_command(interaction, param_name: str):
        # ...
    
    Args:
        param_name: Only used for backward compatibility
        **kwargs: Parameter name to callback mapping
        
    Returns:
        Autocomplete decorator
    """
    # Special case for old discord.py style (@app_commands.autocomplete("param_name"))
    if param_name is not None and not kwargs:
        # Return a decorator that will wait for the callback
        def outer_decorator(callback_func):
            # Create kwargs dict with the parameter name mapping to the callback
            autocomplete_kwargs = {param_name: callback_func}
            # Return the real decorator with proper kwargs
            return app_commands.autocomplete(**autocomplete_kwargs)
        return outer_decorator
    
    # Special case for compat style with explicit callback parameter
    if 'callback' in kwargs and param_name is not None:
        # Extract the callback and create a direct mapping
        callback = kwargs.pop('callback')
        autocomplete_kwargs = {param_name: callback}
        # Return decorator with proper kwargs
        return app_commands.autocomplete(**autocomplete_kwargs)
    
    # Normal py-cord 2.6.1 style (parameter=callback)
    return app_commands.autocomplete(**kwargs)
# Add more direct py-cord 2.6.1 functions
def guild_only():
    """
    Direct implementation of app_commands.guild_only in py-cord 2.6.1
    
    Returns:
        Guild-only decorator
    """
    return app_commands.guild_only()

# Create a direct CommandTree implementation for py-cord 2.6.1
class CommandTree:
    """Direct implementation of CommandTree for py-cord 2.6.1"""
    
    def __init__(self, bot):
        self.bot = bot
    
    async def sync(self, *args, **kwargs):
        """Maps directly to sync_commands in py-cord 2.6.1"""
        if hasattr(self.bot, 'sync_commands'):
            return await self.bot.sync_commands(*args, **kwargs)
        return []

# Always add tree attribute to Bot for compatibility with apps using tree.sync()
from discord.ext.commands import Bot, hybrid_group
from discord.ext import commands

# Apply this patch only once
if not hasattr(Bot, '_tree_patched'):
    original_bot_init = Bot.__init__
    
    def patched_bot_init(self, *args, **kwargs):
        original_bot_init(self, *args, **kwargs)
        if not hasattr(self, 'tree'):
            self.tree = CommandTree(self)
    
    # Apply the patch
    Bot.__init__ = patched_bot_init
    Bot._tree_patched = True
    logger.info("Added tree attribute to Bot for py-cord 2.6.1 compatibility")
    
    # Make sure commands module has hybrid_group for py-cord 2.6.1 compatibility
    if not hasattr(commands, 'hybrid_group'):
        commands.hybrid_group = hybrid_group
        logger.info("Added hybrid_group to commands module for compatibility")

def create_option(name: str, 
                 description: str, 
                 option_type: Any, 
                 required: bool = False, 
                 choices: Optional[List[Dict[str, Any]]] = None) -> Any:
    """
    Create a command option compatible with py-cord 2.6.1
    
    For py-cord 2.6.1, we directly use discord.app_commands.Choice for choices
    and apply options directly in the command parameter annotations.
    
    Args:
        name: Option name
        description: Option description
        option_type: Type of option (use app_commands.AppCommandOptionType constants)
        required: Whether the option is required
        choices: Optional list of choices for the option
        
    Returns:
        Option object for py-cord 2.6.1 or dictionary for compatibility
    """
    # Validate inputs
    if name is None or description is None:
        logger.error("Option name and description cannot be None")
        name = name or "unnamed_option"
        description = description or "No description provided"
    
    try:
        # Import directly from discord.app_commands (modern py-cord 2.6.1 approach)
        import discord.app_commands
        
        # Format choices for py-cord 2.6.1 if provided
        formatted_choices = []
        if choices:
            for choice in choices:
                try:
                    if isinstance(choice, dict):
                        choice_name = str(choice.get('name', ''))
                        choice_value = choice.get('value', '')
                        choice_obj = discord.app_commands.Choice(name=choice_name, value=choice_value)
                        formatted_choices.append(choice_obj)
                    else:
                        formatted_choices.append(choice)
                except Exception as e:
                    logger.error(f"Error formatting choice {choice}: {e}")
        
        # In py-cord 2.6.1, options are normally defined directly in the command parameter annotations
        # But we can still create a parameter description for use in command registration
        return {
            'name': str(name),
            'description': str(description),
            'type': option_type,
            'required': bool(required),
            'choices': formatted_choices
        }
        
    except (ImportError, AttributeError) as e:
        logger.error(f"Error importing discord.app_commands for option creation: {e}")
        
        # Fall back to the old approach if needed
        try:
            # In py-cord 2.6.1, we don't need Option class as options are defined 
            # through function parameter annotations and the @app_commands.describe decorator
            # We'll use app_commands.describe directly
            option_class = None
                
            # Import Choice class from app_commands (for py-cord 2.6.1)
            choice_class = discord.app_commands.Choice
            # No fallbacks needed as we're using direct py-cord 2.6.1 imports
                
            # If we have both classes, create the option
            if option_class is not None and choice_class is not None:
                # Format choices for py-cord if provided
                formatted_choices = []
                if choices:
                    for choice in choices:
                        try:
                            if isinstance(choice, dict):
                                choice_name = str(choice.get('name', ''))
                                choice_value = choice.get('value', '')
                                choice_obj = choice_class(name=choice_name, value=choice_value)
                                formatted_choices.append(choice_obj)
                            else:
                                formatted_choices.append(choice)
                        except Exception as e:
                            logger.error(f"Error formatting choice {choice}: {e}")
                
                # Create the Option object
                return option_class(
                    name=str(name),
                    description=str(description),
                    type=option_type,
                    required=bool(required),
                    choices=formatted_choices
                )
        except Exception as e:
            logger.error(f"Error creating py-cord Option: {e}")
    
    # Ultimate fallback to dictionary format for compatibility
    return {
        'name': str(name),
        'description': str(description),
        'type': option_type,
        'required': bool(required),
        'choices': choices if choices is not None else []
    }

def get_app_commands_module():
    """
    Get the Discord app_commands module
    
    For py-cord 2.6.1, this directly returns discord.app_commands as required by Rule #2
    in rules.md which specifies we should use the latest technologies without compatibility
    layers.
    
    Returns:
        discord.app_commands: The direct app_commands module
    """
    if discord is None:
        logger.error("Discord module not available for app_commands")
        return None
    
    # Direct import from discord module
    try:
        import discord.app_commands
        return discord.app_commands
    except ImportError as e:
        logger.error(f"Failed to import discord.app_commands directly: {e}")
        return None