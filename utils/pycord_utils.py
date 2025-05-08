"""
Direct Py-cord Utility Functions

This module provides direct access to py-cord functionality needed across the codebase.
This implementation fully embraces py-cord (as required by rule #2) without compatibility layers.
"""
import discord
from discord.commands import Option, OptionChoice, SlashCommandGroup
from discord.enums import SlashCommandOptionType

# Create type aliases for commonly used py-cord types
# This makes it easy to reference these types throughout the codebase
AppCommandOptionType = SlashCommandOptionType
Choice = OptionChoice

def create_option(name: str, description: str, option_type, required=False, choices=None):
    """
    Create a command option compatible with py-cord.
    
    This function creates an Option object for slash commands.
    
    Args:
        name: The name of the option
        description: The description of the option
        option_type: The type of the option (use SlashCommandOptionType)
        required: Whether the option is required
        choices: A list of choices for the option
        
    Returns:
        A discord.commands.Option object
    """
    # Format choices if provided
    formatted_choices = None
    if choices:
        if isinstance(choices[0], dict):
            # Convert from dict format if needed
            formatted_choices = [
                OptionChoice(name=choice.get('name', ''), value=choice.get('value', ''))
                for choice in choices
            ]
        else:
            # Already in correct format
            formatted_choices = choices
    
    # Create and return a py-cord Option
    return Option(
        name=name,
        description=description,
        type=option_type,
        required=required,
        choices=formatted_choices if formatted_choices else []
    )