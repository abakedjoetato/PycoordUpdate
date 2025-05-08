"""
Log Processor cog for the Tower of Temptation PvP Statistics Discord Bot.

This cog provides commands and background tasks for processing game log files:
1. Background task for reading and processing log files in real-time
2. Commands for manually processing log files for specific servers
3. Integration with the parser coordinator to avoid duplicate event processing
"""
import asyncio
import logging
import os
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple

import discord
import discord
# Use app_commands via discord.app_commands for py-cord compatibility
from discord.ext import commands
# Ensure discord_compat is imported for py-cord compatibility
from utils.discord_compat import get_app_commands_module
app_commands = get_app_commands_module(), tasks

from utils.csv_parser import CSVParser
from utils.sftp import SFTPManager
from utils.embed_builder import EmbedBuilder
from utils.helpers import has_admin_permission
from utils.parser_utils import parser_coordinator, normalize_event_data, categorize_event
from utils.log_parser import LogParser, parse_log_file
from utils.server_utils import get_server
from utils.decorators import has_admin_permission as admin_permission_decorator, premium_tier_required
from utils.discord_utils import get_server_selection, server_id_autocomplete

logger = logging.getLogger(__name__)

class LogProcessorCog(commands.Cog):
    """Commands and background tasks for processing game log files"""

    async def server_id_autocomplete(self, interaction: discord.Interaction, current: str) -> List[discord.commands.OptionChoice]:
        """Autocomplete for server selection by name, returns server_id as value

        Args:
            interaction: Discord interaction
            current: Current input value

        Returns:
            List[discord.commands.OptionChoice]: List of server choices
        """
        return await server_id_autocomplete(interaction, current)

    def __init__(self, bot: commands.Bot):
        """Initialize the log processor cog

        Args:
            bot: Discord bot instance
        """
        self.bot = bot
        self.log_parsers = {} #Added to store LogParser instances by server_id
        # Don't initialize SFTP manager here, we'll create instances as needed
        self.sftp_managers = {}  # Store SFTP managers by server_id
        self.processing_lock = asyncio.Lock()
        self.is_processing = False
        self.last_processed = {}  # Track last processed timestamp per server

        # Create task loop
        self.process_logs_task = tasks.loop(minutes=1.0)(self.process_logs_task)
        # Before loop hook
        self.process_logs_task.before_loop(self.before_process_logs_task)
        # Start background task
        self.process_logs_task.start()

    def cog_unload(self):
        """Stop background tasks and close connections when cog is unloaded"""
        if hasattr(self.process_logs_task, 'cancel'):
            self.process_logs_task.cancel()

        # Close all SFTP connections
        for server_id, sftp_manager in self.sftp_managers.items():
            try:
                asyncio.create_task(sftp_manager.disconnect())
            except Exception as e:
                logger.error(f"Error disconnecting SFTP for server {server_id}: {e}")

    @tasks.loop(minutes=1.0)
    async def process_logs_task(self):
        """Background task for processing game log files

        This task runs every 1 minute and checks for new log entries on all configured servers.
        """
        if self.is_processing:
            logger.debug("Skipping log processing - already running")
            return

        self.is_processing = True

        try:
            # Get list of configured servers
            server_configs = await self._get_server_configs()

            for server_id, config in server_configs.items():
                try:
                    await self._process_server_logs(server_id, config)
                except Exception as e:
                    logger.error(f"Error processing logs for server {server_id}: {str(e)}")

        except Exception as e:
            logger.error(f"Error in log processing task: {str(e)}")

        finally:
            self.is_processing = False

    @process_logs_task.before_loop
    async def before_process_logs_task(self):
        """Wait for bot to be ready before starting task"""
        await self.bot.wait_until_ready()
        # Add a small delay to avoid startup issues
        await asyncio.sleep(15)

    async def _get_server_configs(self) -> Dict[str, Dict[str, Any]]:
        """Get configurations for all servers with SFTP enabled

        Returns:
            Dict: Dictionary of server IDs to server configurations
        """
        configs = {}

        # Import standardization function
        from utils.server_utils import standardize_server_id

        try:
            # Get all servers from the database
            cursor = self.bot.db.servers.find({"sftp_enabled": True})
            servers = await cursor.to_list(length=100)

            for server in servers:
                # Extract server ID and SFTP connection details
                raw_server_id = server.get("server_id")

                # Standardize the server ID for consistent handling
                server_id = standardize_server_id(str(raw_server_id) if raw_server_id is not None else "")
                if not server_id:
                    logger.warning(f"Invalid server ID format: {raw_server_id}, skipping")
                    continue

                # Log the original and standardized server IDs for debugging
                logger.debug(f"Server ID: original={raw_server_id}, standardized={server_id}")

                # The sftp_host might include the port in format "hostname:port"
                sftp_host = server.get("sftp_host", "")
                sftp_port = server.get("sftp_port", 22)  # Default to 22 if not specified

                # Split hostname and port if they're combined
                if sftp_host and ":" in sftp_host:
                    hostname_parts = sftp_host.split(":")
                    sftp_host = hostname_parts[0]  # Extract just the hostname part
                    if len(hostname_parts) > 1 and hostname_parts[1].isdigit():
                        sftp_port = int(hostname_parts[1])  # Use the port from the combined string

                configs[server_id] = {
                    "server_id": server_id,
                    "original_server_id": raw_server_id,  # Keep original for reference
                    # Map database parameter names to what SFTPManager expects
                    "hostname": sftp_host,
                    "port": sftp_port,
                    "username": server.get("sftp_username", ""),
                    "password": server.get("sftp_password", ""),
                    # Keep additional parameters with original names
                    "sftp_path": server.get("sftp_logs_path", ""),  # Empty string will use default path construction
                    "log_pattern": r"Deadside\.log"
                }
        except Exception as e:
            logger.error(f"Error getting server configs: {str(e)}")

        # No hardcoded fallback, just log a warning if no servers are found
        if not configs:
            logger.warning("No servers with SFTP enabled found in the database")
            # Return empty dict, don't add synthetic test server

        return configs

    async def _get_or_create_log_parser(self, server_id: str, hostname: str) -> LogParser:
        """Get or create a LogParser instance for a server

        Args:
            server_id: Server ID
            hostname: SFTP hostname

        Returns:
            LogParser instance
        """
        if server_id not in self.log_parsers:
            self.log_parsers[server_id] = LogParser(hostname=hostname, server_id=server_id)
        return self.log_parsers[server_id]


    async def _process_server_logs(self, server_id: str, config: Dict[str, Any]):
        """Process log files for a specific server

        Args:
            server_id: Server ID
            config: Server configuration

        Returns:
            Tuple[int, int]: Number of files processed and total events processed
        """
        # Connect to SFTP server - use correctly mapped parameter names
        hostname = config["hostname"]   # Already mapped in _get_server_configs
        port = config["port"]           # Already mapped in _get_server_configs
        username = config["username"]   # Already mapped in _get_server_configs
        password = config["password"]   # Already mapped in _get_server_configs

        # Get last processed time or default to 15 minutes ago
        last_time = self.last_processed.get(server_id, datetime.now() - timedelta(minutes=15))

        try:
            # Create a new SFTP client for this server if not already existing
            if server_id and server_id not in self.sftp_managers:
                logger.info(f"Creating new SFTPManager for server {server_id}")
                # Create SFTPManager with the correct parameter mapping
                # Get original_server_id if it exists
                original_server_id = config.get("original_server_id")
                if original_server_id:
                    logger.info(f"Using original server ID for path construction: {original_server_id}")

                self.sftp_managers[server_id] = SFTPManager(
                    hostname=hostname,  # Map from sftp_host above
                    port=port,          # Map from sftp_port
                    username=username,  # Map from sftp_username
                    password=password,  # Map from sftp_password
                    server_id=server_id,  # Pass server_id for tracking
                    original_server_id=original_server_id  # Pass original server ID for path construction
                )

            # Get the SFTP client for this server
            sftp = self.sftp_managers[server_id]

            try:
                # Get the configured SFTP path from server settings
                sftp_path = config.get("sftp_path", "")

                # Always try to get original_server_id first for path construction
                path_server_id = config.get("original_server_id")
                logger.info(f"Initial path_server_id from config: {path_server_id}")
                
                # Attempt multiple methods to get numeric ID
                if not path_server_id:
                    # Try hostname first
                    hostname = config.get("hostname", "")
                    if "_" in hostname:
                        potential_id = hostname.split("_")[-1]
                        if potential_id.isdigit():
                            path_server_id = potential_id
                            logger.info(f"Using numeric ID from hostname: {potential_id}")
                    
                    # Try server name if hostname didn't work
                    if not path_server_id:
                        server_name = config.get("server_name", "")
                        for word in str(server_name).split():
                            if word.isdigit() and len(word) >= 4:
                                path_server_id = word
                                logger.info(f"Using numeric ID from server name: {word}")
                                break
                
                # If still no numeric ID, log warning and use fallback
                if not path_server_id:
                    logger.warning(f"No numeric ID found, using server_id as fallback: {server_id}")
                    path_server_id = server_id
                
                logger.info(f"Final path_server_id: {path_server_id}")

                # Fallback to server_id only if we couldn't find a numeric ID
                if not path_server_id:
                    logger.warning(f"No original_server_id found, using server_id as fallback: {server_id}")
                    path_server_id = server_id

                server_dir = f"{config.get('hostname', 'server').split(':')[0]}_{path_server_id}"
                logger.info(f"Building server directory with original server ID: {path_server_id}")

                # Extract numeric ID from hostname if available
                numeric_id = None
                if '_' in hostname:
                    potential_id = hostname.split('_')[-1]
                    if potential_id.isdigit():
                        numeric_id = potential_id
                        logger.info(f"Extracted numeric ID from hostname: {numeric_id}")

                # Use numeric ID for path if available
                path_server_id = numeric_id or path_server_id
                
                # Build the path based on configured path or default structure
                if sftp_path and sftp_path.startswith("/"):
                    # Absolute path from configuration - use directly
                    logs_path = sftp_path
                    logger.info(f"Using absolute path from configuration: {logs_path}")
                else:
                    # Fallback to traditional path structure if no custom path
                    logs_path = os.path.join("/", f"{hostname.split(':')[0]}_{path_server_id}", "Logs")
                    logger.info(f"Using default directory structure with ID {path_server_id}: {logs_path}")

                logger.info(f"Looking for log files in path: {logs_path}")

                # Keep track of the original connection state to ensure we're maintaining connections
                was_connected = sftp.client is not None
                logger.debug(f"SFTP connection state before get_log_file: connected={was_connected}")

                # Try to get the log file directly using get_log_file method (with enhanced path discovery)
                log_file_path = await sftp.get_log_file()

                # Verify connection persisted after get_log_file call
                still_connected = sftp.client is not None
                logger.debug(f"SFTP connection state after get_log_file: connected={still_connected}, was_connected={was_connected}")

                # Reconnect if connection was lost during get_log_file operation
                if was_connected and not still_connected:
                    logger.warning(f"Connection lost after get_log_file for server {server_id}, reconnecting...")
                    if await sftp.connect():
                        logger.info(f"Successfully reconnected to SFTP for server {server_id}")
                    else:
                        logger.error(f"Failed to reconnect to SFTP for server {server_id}")
                        return 0, 0

                # Set path variable to default value to prevent LSP errors
                path = logs_path  # Default path to start with

                if log_file_path:
                    logger.info(f"Found log file at: {log_file_path}")
                    log_files = [os.path.basename(log_file_path)]
                    path = os.path.dirname(log_file_path)
                else:
                    # Fallback: Try to list files in directory
                    logger.info(f"Log file not found with direct method, trying multiple search paths...")

                    # Try multiple paths in case the server has a non-standard structure
                    possible_paths = [
                        logs_path,
                        "/Logs",
                        f"/{path_server_id}/Logs",  # Using original server ID here too
                        "/logs"
                    ]

                    files = []
                    for search_path in possible_paths:
                        logger.debug(f"Trying to list files in {search_path}")
                        path_files = await sftp.list_files(search_path)
                        if path_files:
                            files = path_files
                            path = search_path  # Update path if files found
                            logger.info(f"Found {len(files)} files in {search_path}")
                            break

                    # Handle case where no files found in any path
                    if not files:
                        logger.info(f"No files returned from SFTP for server {server_id} in any search path")
                        return 0, 0

                    # Filter for log files
                    log_pattern = config.get("log_pattern", r"Deadside\.log$")
                    log_files = [f for f in files if re.match(log_pattern, f)]

                    # If still no log files, try a recursive search as last resort
                    if not log_files:
                        logger.info(f"No log files found with pattern matching, trying recursive search...")
                        result = []
                        try:
                            if hasattr(sftp.client, 'find_files_recursive'):
                                await sftp.client.find_files_recursive("/", r"Deadside\.log", result, recursive=True, max_depth=2)
                            elif hasattr(sftp.client, 'find_files_by_pattern'):
                                result = await sftp.client.find_files_by_pattern("/", r"Deadside\.log", recursive=True, max_depth=2)

                            if result:
                                logger.info(f"Found log file through recursive search: {result[0]}")
                                log_files = [os.path.basename(result[0])]
                                path = os.path.dirname(result[0])
                        except Exception as search_err:
                            logger.warning(f"Recursive search failed: {search_err}")

                if not log_files:
                    logger.info(f"No log files found for server {server_id}")
                    return 0, 0

                # Process each log file
                files_processed = 0
                events_processed = 0
                log_parser = await self._get_or_create_log_parser(server_id, config["hostname"])

                for log_file in log_files:
                    try:
                        # Get file modification time (use os.path.join for proper path handling)
                        file_path = os.path.join(path, log_file)
                        logger.info(f"Getting stats for log file: {file_path}")
                        file_stat = await sftp.get_file_stats(file_path)

                        if not file_stat:
                            logger.warning(f"Could not get file stats for {file_path}")
                            continue

                        # Check if the file has been modified since last check
                        if hasattr(file_stat, 'st_mtime'):
                            # OS-style stat object
                            file_mtime = datetime.fromtimestamp(file_stat.st_mtime)
                        elif isinstance(file_stat, dict) and 'st_mtime' in file_stat:
                            # Dictionary with st_mtime key
                            file_mtime = datetime.fromtimestamp(file_stat['st_mtime'])
                        elif isinstance(file_stat, dict) and 'mtime' in file_stat:
                            # Dictionary with mtime key
                            if isinstance(file_stat['mtime'], datetime):
                                file_mtime = file_stat['mtime']
                            else:
                                file_mtime = datetime.fromtimestamp(file_stat['mtime'])
                        else:
                            logger.warning(f"Unknown file stat format for {file_path}: {file_stat}")
                            continue

                        if file_mtime > last_time:
                            # Download the full file
                            content = await sftp.download_file(file_path)

                            if content:
                                # Parse log file entries
                                log_entries = parse_log_file(content.decode('utf-8', errors='ignore'))

                                # Filter for entries after the last processed time
                                filtered_entries = []
                                for entry in log_entries:
                                    # Get timestamp from entry
                                    entry_timestamp = entry.get("timestamp")
                                    if entry_timestamp and entry_timestamp > last_time:
                                        filtered_entries.append(entry)

                                # Process filtered entries
                                for entry in filtered_entries:
                                    try:
                                        # Normalize event data
                                        normalized_event = normalize_event_data(entry)

                                        # Add server ID
                                        normalized_event["server_id"] = server_id

                                        # Check if this is not a duplicate event
                                        if parser_coordinator and not parser_coordinator.is_duplicate_event(normalized_event):
                                            # Update timestamp in coordinator
                                            if "timestamp" in normalized_event and isinstance(normalized_event["timestamp"], datetime):
                                                parser_coordinator.update_log_timestamp(server_id, normalized_event["timestamp"])

                                            # Process event based on type
                                            event_type = categorize_event(normalized_event)

                                            if event_type in ["kill", "suicide"]:
                                                # Process kill event
                                                await self._process_kill_event(normalized_event)
                                                events_processed += 1
                                            elif event_type == "connection":
                                                # Process connection event
                                                await self._process_connection_event(normalized_event)
                                                events_processed += 1
                                            elif event_type in ["mission", "game_event"]:
                                                # Process mission/game event
                                                await self._process_game_event(normalized_event)
                                                events_processed += 1

                                    except Exception as e:
                                        logger.error(f"Error processing log entry: {str(e)}")

                                files_processed += 1

                                # Update last processed time to file modification time
                                self.last_processed[server_id] = file_mtime

                    except Exception as e:
                        logger.error(f"Error processing log file {log_file}: {str(e)}")

                return files_processed, events_processed

            finally:
                # Keep the connection open for the next check
                pass

        except Exception as e:
            logger.error(f"SFTP error for server {server_id}: {str(e)}")
            return 0, 0

    @app_commands.command(name="process_logs")
    @app_commands.describe(
        server_id="The server ID to process logs for",
        minutes="Number of minutes to look back (default: 15)"
    )
    @app_commands.autocomplete(param_name="server_id", callback=server_id_autocomplete)
    @admin_permission_decorator()
    @premium_tier_required(1)  # Require Survivor tier for log processing
    async def process_logs_command(
        self,
        interaction: discord.Interaction,
        server_id: Optional[str] = None,
        minutes: Optional[int] = 15
    ):
        """Manually process game log files

        Args:
            interaction: Discord interaction
            server_id: Server ID to process (optional)
            minutes: Number of minutes to look back (default: 15)
        """

        await interaction.response.defer(ephemeral=True)

        # Get server ID from guild config if not provided
        if not server_id or server_id == "":
            try:
                # Get server from guild ID
                guild_id = str(interaction.guild_id)
                server = await get_server(self.bot.db, guild_id)
                if server:
                    server_id = server["server_id"]
                else:
                    # No hardcoded fallback, just show error to user
                    server_id = None
            except Exception as e:
                logger.error(f"Error getting server ID: {str(e)}")
                server_id = None

        # Get server config
        server_configs = await self._get_server_configs()

        if not server_id or server_id not in server_configs:
            embed = EmbedBuilder.create_error_embed(
                title="Server Not Found",
                description=f"No SFTP configuration found for server `{server_id}`."
            )
            from utils.discord_utils import hybrid_send
            await hybrid_send(interaction, embed=embed, ephemeral=True)
            return

        # Calculate lookback time
        self.last_processed[server_id] = datetime.now() - timedelta(minutes=minutes)

        # Process log files
        async with self.processing_lock:
            try:
                files_processed, events_processed = await self._process_server_logs(
                    server_id, server_configs[server_id]
                )

                if files_processed > 0:
                    embed = EmbedBuilder.create_success_embed(
                        title="Log Processing Complete",
                        description=f"Processed {files_processed} log file(s) with {events_processed} events."
                    )
                else:
                    embed = EmbedBuilder.create_info_embed(
                        title="No Files Found",
                        description=f"No new log files found for server `{server_id}` in the last {minutes} minutes."
                    )

                from utils.discord_utils import hybrid_send
                await hybrid_send(interaction, embed=embed, ephemeral=True)

            except Exception as e:
                logger.error(f"Error processing log files: {str(e)}")
                embed = EmbedBuilder.create_error_embed(
                    title="Processing Error",
                    description=f"An error occurred while processing log files: {str(e)}"
                )
                from utils.discord_utils import hybrid_send
                await hybrid_send(interaction, embed=embed, ephemeral=True)

    @app_commands.command(name="log_status")
    @admin_permission_decorator()
    @premium_tier_required(1)  # Require Survivor tier for log status
    async def log_status_command(self, interaction: discord.Interaction):
        """Show log processor status

        Args:
            interaction: Discord interaction
        """

        await interaction.response.defer(ephemeral=True)

        # Get server configs
        server_configs = await self._get_server_configs()

        # Create status embed
        embed = EmbedBuilder.create_base_embed(
            title="Log Processor Status",
            description="Current status of the log processor"
        )

        # Add processing status
        embed.add_field(
            name="Currently Processing",
            value="Yes" if self.is_processing else "No",
            inline=True
        )

        # Add configured servers
        server_list = []
        for server_id, config in server_configs.items():
            last_time = self.last_processed.get(server_id, "Never")
            if isinstance(last_time, datetime):
                last_time = last_time.strftime("%Y-%m-%d %H:%M:%S")

            server_list.append(f"• `{server_id}` - Last processed: {last_time}")

        if server_list:
            embed.add_field(
                name="Configured Servers",
                value="\n".join(server_list),
                inline=False
            )
        else:
            embed.add_field(
                name="Configured Servers",
                value="No servers configured",
                inline=False
            )

        from utils.discord_utils import hybrid_send
        await hybrid_send(interaction, embed=embed, ephemeral=True)

    async def _process_kill_event(self, event: Dict[str, Any]) -> bool:
        """Process a kill event and update player stats and rivalries

        Args:
            event: Normalized kill event dictionary

        Returns:
            bool: True if processed successfully, False otherwise
        """
        try:
            server_id = event.get("server_id")
            if not server_id or server_id == "":
                logger.warning("Kill event missing server_id, skipping")
                return False

            # Get kill details
            killer_id = event.get("killer_id", "")
            killer_name = event.get("killer_name", "Unknown")
            victim_id = event.get("victim_id", "")
            victim_name = event.get("victim_name", "Unknown")
            weapon = event.get("weapon", "Unknown")
            distance = event.get("distance", 0)
            timestamp = event.get("timestamp", datetime.utcnow())

            # Ensure timestamp is datetime
            if isinstance(timestamp, str):
                try:
                    timestamp = datetime.fromisoformat(timestamp)
                except ValueError:
                    timestamp = datetime.utcnow()

            # Check if this is a suicide
            is_suicide = False
            if killer_id and victim_id and killer_id == victim_id:
                is_suicide = True

            # Check if we have the necessary player IDs
            if not victim_id:
                logger.warning("Kill event missing victim_id, skipping")
                return False

            # For suicides, we only need to update the victim's stats
            if is_suicide:
                # Get victim player or create if it doesn't exist
                victim = await self._get_or_create_player(server_id, victim_id, victim_name)

                # Update suicide count
                await victim.update_stats(self.bot.db, kills=0, deaths=0, suicides=1)

                return True

            # For regular kills, we need both killer and victim
            if not killer_id:
                logger.warning("Kill event missing killer_id for non-suicide, skipping")
                return False

            # Get killer and victim players, or create if they don't exist
            killer = await self._get_or_create_player(server_id, killer_id, killer_name)
            victim = await self._get_or_create_player(server_id, victim_id, victim_name)

            # Update kill/death stats
            await killer.update_stats(self.bot.db, kills=1, deaths=0)
            await victim.update_stats(self.bot.db, kills=0, deaths=1)

            # Update rivalries
            from models.rivalry import Rivalry
            await Rivalry.record_kill(server_id, killer_id, victim_id, weapon, "")

            # Update nemesis/prey relationships
            await killer.update_nemesis_and_prey(self.bot.db)
            await victim.update_nemesis_and_prey(self.bot.db)

            # Insert kill event into database
            kill_doc = {
                "server_id": server_id,
                "killer_id": killer_id,
                "killer_name": killer_name,
                "victim_id": victim_id,
                "victim_name": victim_name,
                "weapon": weapon,
                "distance": distance,
                "timestamp": timestamp,
                "is_suicide": is_suicide,
                "source": "log"
            }

            await self.bot.db.kills.insert_one(kill_doc)

            return True

        except Exception as e:
            logger.error(f"Error processing kill event: {e}")
            return False

    async def _process_connection_event(self, event: Dict[str, Any]) -> bool:
        """Process a connection event (player join/leave)

        Args:
            event: Normalized connection event dictionary

        Returns:
            bool: True if processed successfully, False otherwise
        """
        try:
            server_id = event.get("server_id")
            if not server_id or server_id == "":
                logger.warning("Connection event missing server_id, skipping")
                return False

            # Get connection details
            player_id = event.get("player_id", "")
            player_name = event.get("player_name", "Unknown")
            action = event.get("action", "")
            timestamp = event.get("timestamp", datetime.utcnow())

            # Ensure timestamp is datetime
            if isinstance(timestamp, str):
                try:
                    timestamp = datetime.fromisoformat(timestamp)
                except ValueError:
                    timestamp = datetime.utcnow()

            # Check if we have the necessary player ID
            if not player_id:
                logger.warning("Connection event missing player_id, skipping")
                return False

            # Get player or create if it doesn't exist
            player = await self._get_or_create_player(server_id, player_id, player_name)

            # Update last seen time
            await player.update_last_seen(self.bot.db, timestamp)

            # Insert connection event into database
            connection_doc = {
                "server_id": server_id,
                "player_id": player_id,
                "player_name": player_name,
                "action": action,
                "timestamp": timestamp,
                "source": "log"
            }

            await self.bot.db.connections.insert_one(connection_doc)

            return True

        except Exception as e:
            logger.error(f"Error processing connection event: {e}")
            return False

    async def _process_game_event(self, event: Dict[str, Any]) -> bool:
        """Process a game event (mission, airdrop, etc.)

        Args:
            event: Normalized game event dictionary

        Returns:
            bool: True if processed successfully, False otherwise
        """
        try:
            server_id = event.get("server_id")
            if not server_id or server_id == "":
                logger.warning("Game event missing server_id, skipping")
                return False

            # Get event details
            event_type = event.get("event_type", "")
            event_id = event.get("event_id", "")
            location = event.get("location", "")
            timestamp = event.get("timestamp", datetime.utcnow())

            # Ensure timestamp is datetime
            if isinstance(timestamp, str):
                try:
                    timestamp = datetime.fromisoformat(timestamp)
                except ValueError:
                    timestamp = datetime.utcnow()

            # Check if this is a mission event
            if event_type == "mission":
                mission_name = event.get("mission_name", "")
                difficulty = event.get("difficulty", "")

                # Insert mission event into database
                mission_doc = {
                    "server_id": server_id,
                    "mission_name": mission_name,
                    "difficulty": difficulty,
                    "location": location,
                    "timestamp": timestamp,
                    "source": "log"
                }

                await self.bot.db.missions.insert_one(mission_doc)

            # Check if this is an airdrop or helicrash
            elif event_type in ["airdrop", "helicrash", "trader", "convoy"]:
                # Insert game event into database
                game_event_doc = {
                    "server_id": server_id,
                    "event_type": event_type,
                    "event_id": event_id,
                    "location": location,
                    "timestamp": timestamp,
                    "source": "log"
                }

                await self.bot.db.game_events.insert_one(game_event_doc)

            return True

        except Exception as e:
            logger.error(f"Error processing game event: {e}")
            return False

    async def _get_or_create_player(self, server_id: str, player_id: str, player_name: str):
        """Get player by ID or create if it doesn't exist

        Args:
            server_id: Server ID
            player_id: Player ID
            player_name: Player name

        Returns:
            Player object
        """
        from models.player import Player

        # Check if player exists
        player = await Player.get_by_player_id(self.bot.db, player_id)

        if not player:
            # Create new player
            player = Player(
                player_id=player_id,
                server_id=server_id,
                name=player_name,
                display_name=player_name,
                last_seen=datetime.utcnow(),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )

            # Insert into database
            await self.bot.db.players.insert_one(player.__dict__)

        return player

async def setup(bot: commands.Bot) -> None:
    """Set up the log processor cog"""
    await bot.add_cog(LogProcessorCog(bot))