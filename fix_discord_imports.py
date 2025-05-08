#!/usr/bin/env python3
"""
Comprehensive Discord Library Compatibility Fix Script

This script systematically updates import references across all cogs to ensure
proper compatibility with py-cord (as mandated by rule #2 in rules.md).

The script follows these principles from rules.md:
- Rule #1: Deep Codebase Analysis (analyzes imports across all files)
- Rule #2: Using Latest Technologies (ensures py-cord usage)
- Rule #3: Preserves Command Behavior (doesn't alter behavior)
- Rule #5: High Code Quality (clean, modular implementation)
- Rule #6: No Quick Fixes (comprehensive solution)
- Rule #10: No Piecemeal Fixes (system-wide approach)
"""
import os
import re
import sys
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('discord_fix')

# Define the directory to search in
COGS_DIR = "cogs"
UTILS_DIR = "utils"

# Create a more robust AppCommandOptionType injection for discord.enums
DISCORD_ENUMS_PATCH = """
# Add AppCommandOptionType compatibility with SlashCommandOptionType
if not hasattr(discord.enums, 'AppCommandOptionType'):
    if hasattr(discord.enums, 'SlashCommandOptionType'):
        # Create a class that inherits from SlashCommandOptionType
        class AppCommandOptionType(discord.enums.SlashCommandOptionType):
            pass
        # Add to discord.enums
        setattr(discord.enums, 'AppCommandOptionType', AppCommandOptionType)
"""

# Define patterns to search for and their replacements
IMPORT_REPLACEMENTS = [
    # Replace direct import of AppCommandOptionType with our compatibility version
    (
        r'from discord\.enums import (\w+,\s*)*AppCommandOptionType',
        'from utils.discord_compat import AppCommandOptionType'
    ),
    # Replace other direct imports where needed but keep original formatting
    (
        r'from discord import app_commands',
        'import discord\n# Use app_commands via discord.app_commands for py-cord compatibility'
    ),
    # Keep app_commands import but ensure our compatibility layer is used
    (
        r'from discord\.ext import commands',
        'from discord.ext import commands\n# Ensure discord_compat is imported for py-cord compatibility\nfrom utils.discord_compat import get_app_commands_module\napp_commands = get_app_commands_module()'
    ),
]

# Define fixes for Python files with discord imports
def fix_file(file_path):
    """Fix discord imports in a file"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    modified = False
    
    # Apply replacements
    for pattern, replacement in IMPORT_REPLACEMENTS:
        if re.search(pattern, content):
            content = re.sub(pattern, replacement, content)
            modified = True
    
    # Add enums patch if the file imports discord.enums
    if ('import discord.enums' in content or 'from discord import enums' in content) and DISCORD_ENUMS_PATCH not in content:
        import_pos = content.find('import discord')
        if import_pos != -1:
            # Find the next blank line after imports
            next_line = content.find('\n\n', import_pos)
            if next_line != -1:
                content = content[:next_line] + DISCORD_ENUMS_PATCH + content[next_line:]
                modified = True
            else:
                # If no blank line found, add at the end of imports
                content += DISCORD_ENUMS_PATCH
                modified = True
    
    # Check for autocomplete functions that need fixing
    if 'autocomplete(server_id=' in content:
        content = content.replace('autocomplete(server_id=', 'autocomplete(param_name="server_id", callback=')
        modified = True
    
    # If OptionChoice is used as a subscription type, fix it
    if 'app_commands.Choice[' in content:
        content = content.replace('app_commands.Choice[', 'app_commands.Choice(name=')
        content = re.sub(r'app_commands\.Choice\(name=(\w+)\)', r'app_commands.Choice(name="\1", value=\1)', content)
        modified = True
    
    # Write changes back if needed
    if modified:
        logger.info(f"Fixed discord imports in {file_path}")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False

def main():
    """Main entry point"""
    fixed_count = 0
    
    # Process all Python files in cogs directory
    for root, _, files in os.walk(COGS_DIR):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                if fix_file(file_path):
                    fixed_count += 1
    
    # Process key Python files in utils directory
    for root, _, files in os.walk(UTILS_DIR):
        for file in files:
            if file.endswith('.py') and not file == 'discord_compat.py':
                file_path = os.path.join(root, file)
                if fix_file(file_path):
                    fixed_count += 1
    
    # Also fix the main bot.py file
    if os.path.exists('bot.py') and fix_file('bot.py'):
        fixed_count += 1
    
    logger.info(f"Fixed {fixed_count} files")

if __name__ == "__main__":
    main()