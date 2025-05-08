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
discord = None
SlashCommandOptionType = None
OptionChoice = None
Option = None
SlashCommandGroup = None
Bot = None
Cog = None

try:
    import discord
    logger.info(f"Successfully imported discord (version: {getattr(discord, '__version__', 'unknown')})")
    
    # Import Option, OptionChoice, SlashCommandGroup with error handling
    try:
        from discord.commands import Option, OptionChoice, SlashCommandGroup
        logger.info("Successfully imported commands components")
    except (ImportError, AttributeError) as e:
        logger.error(f"Failed to import discord.commands components: {e}")
    
    # Import Bot, Cog with error handling
    try:
        from discord.ext.commands import Bot, Cog
        logger.info("Successfully imported Bot and Cog classes")
    except (ImportError, AttributeError) as e:
        logger.error(f"Failed to import Bot and Cog: {e}")
    
    # Define SlashCommandOptionType for use in app_command_option_type
    try:
        from discord.enums import SlashCommandOptionType
        logger.info("Successfully imported SlashCommandOptionType")
    except (ImportError, AttributeError) as e:
        logger.error(f"Failed to import SlashCommandOptionType: {e}")
except ImportError as e:
    logger.error(f"Failed to import py-cord library: {e}")
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
        if USING_PYCORD and SlashCommandOptionType is not None:
            for attr_name in dir(SlashCommandOptionType):
                if not attr_name.startswith('_'):  # Skip private/dunder methods
                    setattr(self, attr_name, getattr(SlashCommandOptionType, attr_name))
            logger.info("Initialized AppCommandOptionType with SlashCommandOptionType values")

# Create AppCommandOptionType instance and also export it to discord.enums for direct imports
app_command_option_type = AppCommandOptionType()

# Add to discord.enums for backwards compatibility with direct imports
if discord is not None and hasattr(discord, 'enums'):
    if not hasattr(discord.enums, 'AppCommandOptionType'):
        setattr(discord.enums, 'AppCommandOptionType', app_command_option_type)
        logger.info("Added AppCommandOptionType to discord.enums for import compatibility")

# Create app_commands compatibility layer for py-cord
class AppCommandsCompatLayer:
    """Maps discord.py's app_commands module to py-cord's commands functionality."""
    
    def __init__(self):
        self.logger = logger
        
        # Set up Choice for autocomplete 
        if USING_PYCORD and OptionChoice is not None:
            self.Choice = OptionChoice  # Use py-cord's OptionChoice
        else:
            # Create a mock Choice class if needed (fallback)
            self.Choice = type('Choice', (), {
                '__init__': lambda s, name, value: setattr(s, 'name', name) or setattr(s, 'value', value)
            })
        
    def command(self, name=None, description=None):
        """Maps to py-cord's slash_command"""
        if USING_PYCORD and discord is not None:
            try:
                # Properly access slash_command from py-cord
                return discord.slash_command(name=name, description=description)
            except Exception as e:
                logger.error(f"Error creating slash command: {e}")
        
        # Fallback decorator if needed
        def decorator(func):
            return func
        return decorator
    
    def describe(self, **kwargs):
        """
        Maps to py-cord's options system
        
        In py-cord, command options are specified directly with parameters rather than
        using a separate describe decorator. This compatibility layer stores the
        descriptions as attributes on the function for later use if needed.
        
        Args:
            **kwargs: Parameter name to description mapping
            
        Returns:
            Function decorator
        """
        # Validate inputs
        validated_kwargs = {}
        for param_name, description in kwargs.items():
            if description is None:
                logger.warning(f"Parameter description for '{param_name}' is None, using empty string")
                description = ""
            validated_kwargs[param_name] = str(description)
            
        # Create decorator to apply to slash command functions
        def decorator(func):
            try:
                # Store the descriptions for later use
                if not hasattr(func, "_descriptions"):
                    func._descriptions = {}
                    
                # Update with validated descriptions
                func._descriptions.update(validated_kwargs)
                
                # If this is a slash command in py-cord, we can directly update its parameters
                if USING_PYCORD and hasattr(func, "__commands_slash_params__"):
                    for param_name, description in validated_kwargs.items():
                        if param_name in func.__commands_slash_params__:
                            # Update the parameter description
                            func.__commands_slash_params__[param_name].description = description
                            logger.debug(f"Updated slash command parameter '{param_name}' description")
                
                return func
            except Exception as e:
                logger.error(f"Error in describe decorator: {e}")
                return func
                
        return decorator
    
    def autocomplete(self, param_name=None, **kwargs):
        """
        Maps to py-cord's autocomplete system
        
        This supports multiple autocomplete patterns for compatibility:
        
        1. Discord.py style (parameter name as argument):
            @app_commands.autocomplete("server_id")
            async def server_id_autocomplete(interaction, current):
                # ...
        
        2. Py-cord style (parameter=callback format):
            @app_commands.autocomplete(server_id=server_id_autocomplete)
            async def my_command(ctx, server_id: str):
                # ...
                
        3. Custom compatibility style (explicitly named callback):
            @app_commands.autocomplete(param_name="server_id", callback=server_id_autocomplete)
            async def my_command(ctx, server_id: str):
                # ...
        
        Args:
            param_name: Parameter name to autocomplete (for discord.py style)
            **kwargs: Additional kwargs including callbacks
            
        Returns:
            Appropriate decorator for the autocomplete style being used
        """
        # Specialized handlers for different autocomplete styles
        try:
            # 1. Handle py-cord style (parameter=callback) for direct parameter mapping
            # Example: @app_commands.autocomplete(server_id=server_id_autocomplete)
            for kwarg_name, callback in kwargs.items():
                if kwarg_name != 'callback' and callable(callback):
                    param = kwarg_name
                    
                    def inner_decorator_named_param(func):
                        try:
                            # Store autocomplete callbacks on the function
                            if not hasattr(func, "_param_autocomplete"):
                                func._param_autocomplete = {}
                            
                            func._param_autocomplete[param] = callback
                            
                            # If py-cord, try to apply native autocomplete
                            if USING_PYCORD and hasattr(func, "__commands_slash_params__"):
                                if param in func.__commands_slash_params__:
                                    func.__commands_slash_params__[param].autocomplete = callback
                                    logger.debug(f"Applied py-cord native autocomplete for {param}")
                                else:
                                    logger.warning(f"Parameter {param} not found in slash command params")
                                
                            return func
                        except Exception as e:
                            logger.error(f"Error in autocomplete inner decorator: {e}")
                            return func
                            
                    return inner_decorator_named_param
            
            # 2. Handle explicit callback style
            # Example: @app_commands.autocomplete(param_name="server_id", callback=callback_func)
            if 'callback' in kwargs:
                callback = kwargs.get('callback')
                param = param_name  # Use the param_name argument
                
                if param is None:
                    logger.warning("param_name is None but callback was provided, autocomplete may not work")
                    param = "unknown_param"
                
                def inner_decorator_with_callback(func):
                    try:
                        if not hasattr(func, "_param_autocomplete"):
                            func._param_autocomplete = {}
                        
                        func._param_autocomplete[param] = callback
                        
                        # If py-cord, try to apply native autocomplete
                        if USING_PYCORD and hasattr(func, "__commands_slash_params__"):
                            if param in func.__commands_slash_params__:
                                func.__commands_slash_params__[param].autocomplete = callback
                                logger.debug(f"Applied py-cord native autocomplete for {param}")
                            
                        return func
                    except Exception as e:
                        logger.error(f"Error in autocomplete callback decorator: {e}")
                        return func
                        
                return inner_decorator_with_callback
        
            # 3. Handle discord.py style where param_name is passed as first argument
            # Example: @app_commands.autocomplete("server_id")
            if param_name is not None:
                # This will receive the autocomplete callback function
                def outer_decorator(callback_func):
                    try:
                        # We'll attach the callback to any command this decorates
                        def command_decorator(func):
                            if not hasattr(func, "_param_autocomplete"):
                                func._param_autocomplete = {}
                            
                            func._param_autocomplete[param_name] = callback_func
                            
                            # If py-cord, try to apply native autocomplete
                            if USING_PYCORD and hasattr(func, "__commands_slash_params__"):
                                if param_name in func.__commands_slash_params__:
                                    func.__commands_slash_params__[param_name].autocomplete = callback_func
                                    logger.debug(f"Applied py-cord native autocomplete for {param_name}")
                                
                            return func
                            
                        # If the callback_func is already a command (has been decorated)
                        # then apply our autocomplete directly
                        if hasattr(callback_func, "__commands_slash_params__"):
                            if not hasattr(callback_func, "_param_autocomplete"):
                                callback_func._param_autocomplete = {}
                            callback_func._param_autocomplete[param_name] = True
                            return callback_func
                        
                        # Otherwise, return decorator expecting a command
                        return command_decorator
                    except Exception as e:
                        logger.error(f"Error in autocomplete outer decorator: {e}")
                        if hasattr(callback_func, "__commands_slash_params__"):
                            return callback_func
                        return lambda f: f
                
                return outer_decorator
                
            # Fallback case - parameter with no callback
            logger.warning("Autocomplete called with no valid parameters")
            return lambda f: f
            
        except Exception as e:
            logger.error(f"Error in autocomplete method: {e}")
            return lambda f: f
    
    def guild_only(self):
        """Maps to py-cord's guild_only decorator"""
        if USING_PYCORD and discord is not None:
            try:
                # Properly access guild_only from py-cord
                return discord.guild_only()
            except Exception as e:
                logger.error(f"Error creating guild_only decorator: {e}")
        
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
if USING_PYCORD and discord is not None:
    try:
        # 1. Add app_commands compatibility if not present
        if not hasattr(discord, 'app_commands'):
            app_commands_compat = AppCommandsCompatLayer()
            setattr(discord, 'app_commands', app_commands_compat)
            logger.info("Added app_commands compatibility layer for py-cord")
        
        # 2. Patch Bot class to include tree attribute if needed
        from discord.ext.commands import Bot
        original_bot_init = Bot.__init__
        
        def patched_bot_init(self, *args, **kwargs):
            original_bot_init(self, *args, **kwargs)
            if not hasattr(self, 'tree'):
                self.tree = CommandTreeCompat(self)
        
        # Apply the patch
        Bot.__init__ = patched_bot_init
        logger.info("Patched Bot class to add tree support")
        
        # 3. Add hybrid_group compatibility to commands module
        try:
            from discord.ext import commands
            
            if not hasattr(commands, 'hybrid_group'):
                def hybrid_group(name=None, **kwargs):
                    """Create a hybrid command group compatible with both slash and prefix commands"""
                    # Ensure name is a string if provided
                    name_param = str(name) if name is not None else None
                    description = kwargs.get('description', 'No description')
                    
                    # Define decorator function 
                    def decorator(func):
                        # Apply group decorator first
                        try:
                            # Ensure name is not None to fix py-cord compatibility
                            group_name = name_param if name_param is not None else func.__name__
                            
                            # Create a copy of kwargs without name parameter
                            safe_kwargs = {k: v for k, v in kwargs.items() if k != 'name'}
                            
                            # Apply command group with safe name
                            result = commands.group(name=group_name, **safe_kwargs)(func)
                        except Exception as e:
                            logger.error(f"Error applying group decorator: {e}")
                            result = func  # Fallback to original function
                        
                        # Try to apply slash command decorator if available
                        try:
                            if hasattr(discord, 'slash_command') and not kwargs.get('invoke_without_command', False):
                                result = discord.slash_command(
                                    name=name_param, 
                                    description=description
                                )(result)
                        except Exception as e:
                            logger.error(f"Error applying slash_command decorator: {e}")
                        
                        return result
                    
                    return decorator
                
                # For py-cord 2.6.1, we need to explicitly define hybrid_group in the commands module
                from types import MethodType
                
                def add_hybrid_group_to_commands() -> None:
                    """Add hybrid_group as a properly typed method to commands module"""
                    try:
                        # Only create if it doesn't already exist
                        if not hasattr(commands, 'hybrid_group'):
                            # Define it as a proper function with the same signature as commands.group
                            def hybrid_group_impl(name=None, **attrs):
                                """
                                A decorator that transforms a function into a hybrid command group.
                                A hybrid command can be invoked either as a regular text command or as a slash command.
                                
                                This is equivalent to using @commands.group and @discord.slash_command together.
                                """
                                def decorator(func):
                                    # Use name from function if not provided
                                    cmd_name = name or func.__name__
                                    # Apply regular group decorator
                                    result = commands.group(name=cmd_name, **attrs)(func)
                                    # Apply slash command decorator if available
                                    if hasattr(discord, 'slash_command'):
                                        result = discord.slash_command(
                                            name=cmd_name,
                                            description=attrs.get('description', 'No description')
                                        )(result)
                                    return result
                                return decorator
                            
                            # Add the implementation to the commands module
                            commands.hybrid_group = hybrid_group_impl
                            logger.info("Added hybrid_group to commands module successfully")
                    except Exception as e:
                        logger.error(f"Error adding hybrid_group to commands: {e}")
                
                # Execute immediately
                add_hybrid_group_to_commands()
                logger.info("Hybrid group setup complete")
        except Exception as e:
            logger.error(f"Failed to set up hybrid_group compatibility: {e}")
    except Exception as e:
        logger.error(f"Error setting up py-cord compatibility: {e}")

def create_option(name: str, 
                 description: str, 
                 option_type: Any, 
                 required: bool = False, 
                 choices: Optional[List[Dict[str, Any]]] = None) -> Any:
    """
    Create a command option compatible with py-cord
    
    Args:
        name: Option name
        description: Option description
        option_type: Type of option (use app_command_option_type constants)
        required: Whether the option is required
        choices: Optional list of choices for the option
        
    Returns:
        Option object for py-cord or dictionary for compatibility
    """
    # Validate inputs
    if name is None or description is None:
        logger.error("Option name and description cannot be None")
        name = name or "unnamed_option"
        description = description or "No description provided"
    
    # Attempt to use py-cord Option if available
    if USING_PYCORD and discord is not None:
        try:
            # Import Option class if not already available
            option_class = Option
            if option_class is None and hasattr(discord, 'commands') and hasattr(discord.commands, 'Option'):
                option_class = discord.commands.Option
                
            # Import OptionChoice class if not already available
            choice_class = OptionChoice
            if choice_class is None and hasattr(discord, 'commands') and hasattr(discord.commands, 'OptionChoice'):
                choice_class = discord.commands.OptionChoice
                
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
    
    # Fallback to dictionary format for compatibility
    return {
        'name': str(name),
        'description': str(description),
        'type': option_type,
        'required': bool(required),
        'choices': choices if choices is not None else []
    }

def get_app_commands_module():
    """
    Get the appropriate app_commands module for the current environment
    
    For py-cord, this returns our compatibility layer or creates one if needed.
    This function is useful for dynamically retrieving the app_commands module
    in places where direct imports might fail.
    
    Returns:
        AppCommandsCompatLayer or None: The app_commands module to use
    """
    if discord is None:
        logger.error("Discord module not available for app_commands")
        return None
    
    # Check if app_commands already exists
    app_commands = getattr(discord, 'app_commands', None)
    
    # If not, create it (this shouldn't normally happen as it's created in the initialization)
    if app_commands is None and USING_PYCORD:
        try:
            app_commands = AppCommandsCompatLayer()
            setattr(discord, 'app_commands', app_commands)
            logger.info("Created new app_commands compatibility layer on demand")
        except Exception as e:
            logger.error(f"Failed to create app_commands on demand: {e}")
    
    return app_commands