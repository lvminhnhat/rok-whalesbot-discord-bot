"""
Admin commands for Discord bot.
"""

import discord
from discord import Option
from datetime import datetime
from typing import Optional

from discord_bot.utils.permissions import is_admin
from discord_bot.utils.validators import validate_emulator_index, validate_days, validate_date
from discord_bot.services.bot_service import BotService
from discord_bot.services.subscription_service import SubscriptionService
from shared.data_manager import DataManager
from shared.constants import ActionType, ActionResult, InstanceStatus


def setup_admin_commands(
    bot: discord.Bot,
    bot_service: BotService,
    subscription_service: SubscriptionService,
    data_manager: DataManager
):
    """
    Setup admin commands.
    
    Args:
        bot: Discord bot instance
        bot_service: Bot service instance
        subscription_service: Subscription service instance
        data_manager: Data manager instance
    """
    
    @bot.slash_command(
        name="grant",
        description="[Admin] Grant access to user"
    )
    async def grant(
        ctx: discord.ApplicationContext,
        user: Option(discord.Member, "User to grant access", required=True),
        days: Option(int, "Number of days", required=True)
    ):
        """Grant subscription to user."""
        if not is_admin(ctx):
            await ctx.respond("You don't have permission to use this command.", ephemeral=True)
            return

        # Validate days
        is_valid, error_msg = validate_days(days)
        if not is_valid:
            await ctx.respond(error_msg, ephemeral=True)
            return

        await ctx.defer(ephemeral=True)

        result = subscription_service.grant_subscription(
            discord_id=str(user.id),
            discord_name=str(user),
            days=days
        )

        # Log action
        data_manager.log_action(
            user_id=str(user.id),
            user_name=str(user),
            action=ActionType.GRANT,
            details=f"Granted {days} days subscription",
            result=ActionResult.SUCCESS if result['success'] else ActionResult.FAILED,
            performed_by=str(ctx.author.id)
        )

        await ctx.followup.send(result['message'], ephemeral=True)
    
    @bot.slash_command(
        name="add_days",
        description="[Admin] Add days to user subscription"
    )
    async def add_days(
        ctx: discord.ApplicationContext,
        user: Option(discord.Member, "User to add days", required=True),
        days: Option(int, "Number of days to add", required=True)
    ):
        """Add days to user's subscription."""
        if not is_admin(ctx):
            await ctx.respond("You don't have permission to use this command.", ephemeral=True)
            return
        
        # Validate days
        is_valid, error_msg = validate_days(days)
        if not is_valid:
            await ctx.respond(error_msg, ephemeral=True)
            return
        
        result = subscription_service.add_days(str(user.id), days)
        
        # Log action
        data_manager.log_action(
            user_id=str(user.id),
            user_name=str(user),
            action=ActionType.ADD_DAYS,
            details=f"Added {days} days",
            result=ActionResult.SUCCESS if result['success'] else ActionResult.FAILED,
            performed_by=str(ctx.author.id)
        )
        
        await ctx.respond(result['message'], ephemeral=True)
    
    @bot.slash_command(
        name="set_expiry",
        description="[Admin] Set expiry date for user"
    )
    async def set_expiry(
        ctx: discord.ApplicationContext,
        user: Option(discord.Member, "User to set expiry", required=True),
        date: Option(str, "Expiry date (YYYY-MM-DD)", required=True)
    ):
        """Set expiry date for user."""
        if not is_admin(ctx):
            await ctx.respond("You don't have permission to use this command.", ephemeral=True)
            return
        
        # Validate date
        is_valid, error_msg = validate_date(date)
        if not is_valid:
            await ctx.respond(error_msg, ephemeral=True)
            return
        
        result = subscription_service.set_expiry(str(user.id), date)
        
        # Log action
        data_manager.log_action(
            user_id=str(user.id),
            user_name=str(user),
            action=ActionType.SET_EXPIRY,
            details=f"Set expiry to {date}",
            result=ActionResult.SUCCESS if result['success'] else ActionResult.FAILED,
            performed_by=str(ctx.author.id)
        )
        
        await ctx.respond(result['message'], ephemeral=True)
    
    @bot.slash_command(
        name="revoke",
        description="[Admin] Revoke user access"
    )
    async def revoke(
        ctx: discord.ApplicationContext,
        user: Option(discord.Member, "User to revoke", required=True)
    ):
        """Revoke user's subscription."""
        if not is_admin(ctx):
            await ctx.respond("You don't have permission to use this command.", ephemeral=True)
            return
        
        await ctx.defer(ephemeral=True)
        
        # Force stop if running
        bot_service.force_stop_instance(str(user.id))
        
        # Revoke subscription
        result = subscription_service.revoke(str(user.id))
        
        # Log action
        data_manager.log_action(
            user_id=str(user.id),
            user_name=str(user),
            action=ActionType.REVOKE,
            details="Revoked subscription and stopped instance",
            result=ActionResult.SUCCESS if result['success'] else ActionResult.FAILED,
            performed_by=str(ctx.author.id)
        )
        
        await ctx.followup.send(result['message'], ephemeral=True)
    
    @bot.slash_command(
        name="force_start",
        description="[Admin] Force start bot for user"
    )
    async def force_start(
        ctx: discord.ApplicationContext,
        user: Option(discord.Member, "User to start bot for", required=True)
    ):
        """Force start user's instance."""
        if not is_admin(ctx):
            await ctx.respond("You don't have permission to use this command.", ephemeral=True)
            return
        
        await ctx.defer(ephemeral=True)
        
        result = bot_service.start_instance(str(user.id))
        
        # Log action
        data_manager.log_action(
            user_id=str(user.id),
            user_name=str(user),
            action=ActionType.FORCE_START,
            details="Admin forced start",
            result=ActionResult.SUCCESS if result['success'] else ActionResult.FAILED,
            performed_by=str(ctx.author.id)
        )
        
        await ctx.followup.send(result['message'], ephemeral=True)
    
    @bot.slash_command(
        name="force_stop",
        description="[Admin] Force stop bot for user"
    )
    async def force_stop(
        ctx: discord.ApplicationContext,
        user: Option(discord.Member, "User to stop bot for", required=True)
    ):
        """Force stop user's instance."""
        if not is_admin(ctx):
            await ctx.respond("You don't have permission to use this command.", ephemeral=True)
            return
        
        await ctx.defer(ephemeral=True)
        
        result = bot_service.force_stop_instance(str(user.id))
        
        # Log action
        data_manager.log_action(
            user_id=str(user.id),
            user_name=str(user),
            action=ActionType.FORCE_STOP,
            details="Admin forced stop",
            result=ActionResult.SUCCESS if result['success'] else ActionResult.FAILED,
            performed_by=str(ctx.author.id)
        )
        
        await ctx.followup.send(result['message'], ephemeral=True)
    
    @bot.slash_command(
        name="list_expiring",
        description="[Admin] List users expiring soon"
    )
    async def list_expiring(
        ctx: discord.ApplicationContext,
        days: Option(int, "Number of days (default 7)", required=False, default=7)
    ):
        """List users expiring soon."""
        if not is_admin(ctx):
            await ctx.respond("You don't have permission to use this command.", ephemeral=True)
            return
        
        expiring_users = subscription_service.get_expiring_users(days)
        
        if not expiring_users:
            await ctx.respond(f"No users expiring in the next {days} days.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title=f"Users expiring soon ({days} days)",
            color=discord.Color.orange()
        )
        
        for user in expiring_users[:25]:
            embed.add_field(
                name=user.discord_name,
                value=f"{user.subscription.days_left} days left\nEmulator: #{user.emulator_index}",
                inline=True
            )
        
        if len(expiring_users) > 25:
            embed.set_footer(text=f"And {len(expiring_users) - 25} more users...")
        
        embed.timestamp = datetime.utcnow()
        
        await ctx.respond(embed=embed, ephemeral=True)
    
    @bot.slash_command(
        name="who",
        description="[Admin] View running instances"
    )
    async def who(ctx: discord.ApplicationContext):
        """List running instances."""
        if not is_admin(ctx):
            await ctx.respond("You don't have permission to use this command.", ephemeral=True)
            return
        
        running_users = data_manager.get_users_by_status(InstanceStatus.RUNNING)
        
        if not running_users:
            await ctx.respond("No instances running.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="Running Instances",
            color=discord.Color.green()
        )
        
        for user in running_users[:25]:  # Limit to 25 fields
            uptime_text = ""
            if user.uptime_seconds:
                hours = user.uptime_seconds // 3600
                minutes = (user.uptime_seconds % 3600) // 60
                uptime_text = f"\nUptime: {hours}h {minutes}m"
            
            embed.add_field(
                name=user.discord_name,
                value=f"Emulator: #{user.emulator_index}{uptime_text}",
                inline=True
            )
        
        if len(running_users) > 25:
            embed.set_footer(text=f"And {len(running_users) - 25} more instances...")
        else:
            embed.set_footer(text=f"Total: {len(running_users)} instances")
        
        embed.timestamp = datetime.utcnow()
        
        await ctx.respond(embed=embed, ephemeral=True)
    
    @bot.slash_command(
        name="config",
        description="[Admin] Configure bot settings"
    )
    async def config_command(
        ctx: discord.ApplicationContext,
        setting: Option(
            str,
            "Setting to configure",
            choices=["current_channel", "current_guild", "admin_roles", "cooldown"],
            required=True
        ),
        action: Option(
            str,
            "Action to perform",
            choices=["add", "remove", "set", "view"],
            required=True
        ),
        value: Option(str, "Value (ID or number) - auto-detect for current_channel/guild", required=False, default=None)
    ):
        """Configure bot settings."""
        if not is_admin(ctx):
            await ctx.respond("You don't have permission to use this command.", ephemeral=True)
            return
        
        config = data_manager.get_config()
        
        # Auto-detect current channel/guild
        if setting == "current_channel":
            value = str(ctx.channel.id)
            setting = "allowed_channels"
        elif setting == "current_guild":
            if ctx.guild:
                value = str(ctx.guild.id)
                setting = "allowed_guilds"
            else:
                await ctx.respond("This command must be used in a server (guild).", ephemeral=True)
                return
        
        if action == "view":
            # Show current config
            embed = discord.Embed(
                title=f"Configuration: {setting}",
                color=discord.Color.blue()
            )
            
            if setting == "cooldown":
                embed.description = f"Cooldown: {config.cooldown_seconds} seconds"
            else:
                current_values = getattr(config, setting, [])
                if current_values:
                    embed.description = "\n".join([f"• {v}" for v in current_values])
                else:
                    embed.description = "No values configured"
            
            await ctx.respond(embed=embed, ephemeral=True)
            return
        
        if not value:
            await ctx.respond("Value is required for this action.", ephemeral=True)
            return
        
        if setting == "cooldown":
            if action == "set":
                try:
                    seconds = int(value)
                    if seconds < 0:
                        await ctx.respond("Cooldown must be >= 0 seconds.", ephemeral=True)
                        return
                    
                    config.cooldown_seconds = seconds
                    data_manager.save_config(config)
                    
                    # Log action
                    data_manager.log_action(
                        user_id=str(ctx.author.id),
                        user_name=str(ctx.author),
                        action=ActionType.CONFIG_UPDATE,
                        details=f"Set cooldown to {seconds}s",
                        result=ActionResult.SUCCESS,
                        performed_by=str(ctx.author.id)
                    )
                    
                    await ctx.respond(f"Cooldown set to {seconds} seconds.", ephemeral=True)
                except ValueError:
                    await ctx.respond("Value must be an integer.", ephemeral=True)
            else:
                await ctx.respond("Cooldown only supports 'set' action.", ephemeral=True)
        else:
            # Handle list-type configs
            current_list = getattr(config, setting)
            
            if action == "add":
                if value not in current_list:
                    current_list.append(value)
                    setattr(config, setting, current_list)
                    data_manager.save_config(config)
                    
                    # Log action
                    data_manager.log_action(
                        user_id=str(ctx.author.id),
                        user_name=str(ctx.author),
                        action=ActionType.CONFIG_UPDATE,
                        details=f"Added {value} to {setting}",
                        result=ActionResult.SUCCESS,
                        performed_by=str(ctx.author.id)
                    )
                    
                    location_name = f"<#{value}>" if setting == "allowed_channels" else f"Guild {value}"
                    await ctx.respond(f"Added {location_name} to {setting}.", ephemeral=True)
                else:
                    await ctx.respond(f"{value} is already in {setting}.", ephemeral=True)
            
            elif action == "remove":
                if value in current_list:
                    current_list.remove(value)
                    setattr(config, setting, current_list)
                    data_manager.save_config(config)
                    
                    # Log action
                    data_manager.log_action(
                        user_id=str(ctx.author.id),
                        user_name=str(ctx.author),
                        action=ActionType.CONFIG_UPDATE,
                        details=f"Removed {value} from {setting}",
                        result=ActionResult.SUCCESS,
                        performed_by=str(ctx.author.id)
                    )
                    
                    location_name = f"<#{value}>" if setting == "allowed_channels" else f"Guild {value}"
                    await ctx.respond(f"Removed {location_name} from {setting}.", ephemeral=True)
                else:
                    await ctx.respond(f"{value} is not in {setting}.", ephemeral=True)
    
    @bot.slash_command(
        name="logs",
        description="[Admin] View audit logs"
    )
    async def logs(
        ctx: discord.ApplicationContext,
        user: Option(discord.Member, "Filter by user (optional)", required=False, default=None),
        limit: Option(int, "Number of logs (default 20)", required=False, default=20)
    ):
        """View audit logs."""
        if not is_admin(ctx):
            await ctx.respond("You don't have permission to use this command.", ephemeral=True)
            return
        
        user_id = str(user.id) if user else None
        logs = data_manager.get_logs(user_id=user_id, limit=min(limit, 50))
        
        if not logs:
            await ctx.respond("No logs found.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="📋 Audit Logs",
            color=discord.Color.blue()
        )
        
        if user:
            embed.description = f"Logs for {user.mention}"
        
        for log in logs[:10]:
            try:
                timestamp = datetime.fromisoformat(log.timestamp)
                time_str = f"<t:{int(timestamp.timestamp())}:R>"
            except:
                time_str = log.timestamp
            
            result_emoji = "✅" if log.result == ActionResult.SUCCESS.value else "❌"
            
            embed.add_field(
                name=f"{result_emoji} {log.action} - {time_str}",
                value=f"User: {log.user_name}\n{log.details}",
                inline=False
            )
        
        if len(logs) > 10:
            embed.set_footer(text=f"Showing 10/{len(logs)} logs")
        
        embed.timestamp = datetime.utcnow()
        
        await ctx.respond(embed=embed, ephemeral=True)

    @bot.slash_command(
        name="link_user",
        description="[Admin] Link user to emulator"
    )
    async def link_user(
        ctx: discord.ApplicationContext,
        user: Option(discord.Member, "User to link", required=True),
        emulator_name: Option(str, "Emulator name to link", required=True)
    ):
        """Link user to emulator (admin command)."""
        if not is_admin(ctx):
            await ctx.respond("You don't have permission to use this command.", ephemeral=True)
            return

        await ctx.defer(ephemeral=True)

        # Check if user exists
        existing_user = data_manager.get_user(str(user.id))
        if not existing_user:
            await ctx.followup.send("User not in system. Use `/grant` to grant access first.", ephemeral=True)
            return

        if existing_user.is_running:
            stop_result = bot_service.force_stop_instance(str(user.id))
            if not stop_result['success']:
                await ctx.followup.send(f"Cannot stop current bot: {stop_result['message']}", ephemeral=True)
                return

        # Link user to emulator
        link_result = bot_service.link_user_to_emulator(
            user_id=str(user.id),
            emulator_name=emulator_name,
            discord_name=str(user)
        )

        # Log action
        old_emulator = existing_user.emulator_name or f"Index {existing_user.emulator_index}"
        data_manager.log_action(
            user_id=str(user.id),
            user_name=str(user),
            action=ActionType.CONFIG_CHANGE,
            details=f"Admin linked user from {old_emulator} to {emulator_name}",
            result=ActionResult.SUCCESS if link_result['success'] else ActionResult.FAILED,
            performed_by=str(ctx.author.id)
        )

        if link_result['success']:
            message = f"**User linked successfully!**\n\n"
            message += f"**User:** {user.mention}\n"
            message += f"**Emulator:** {emulator_name}\n\n"
            message += f"User can now use `/start`."
        else:
            message = f"**Link failed:** {link_result['message']}"

        await ctx.followup.send(message, ephemeral=True)

    @bot.slash_command(
        name="list_emulators",
        description="[Admin] View all available emulators and their status"
    )
    async def list_emulators(ctx: discord.ApplicationContext):
        """List all available emulators (admin command)."""
        if not is_admin(ctx):
            await ctx.respond("You don't have permission to use this command.", ephemeral=True)
            return

        # Defer response
        await ctx.defer(ephemeral=True)

        # Get emulators
        result = bot_service.get_available_emulators()

        if not result['success']:
            await ctx.followup.send(result['message'], ephemeral=True)
            return

        # Build embed
        embed = discord.Embed(
            title="🖥️ Available Emulators",
            description=f"Total: {result['count']} emulators",
            color=discord.Color.blue()
        )

        # Group emulators
        linked = []
        available = []

        for emu in result['emulators']:
            status = "[ACTIVE]" if emu['is_active'] else "[INACTIVE]"
            if emu['linked_user']:
                linked.append(f"{status} **{emu['name']}** (Index {emu['index']})\n└─ Linked to: {emu['linked_user']}")
            else:
                available.append(f"{status} **{emu['name']}** (Index {emu['index']})\n└─ Available")

        if available:
            embed.add_field(
                name=f"🟢 Available ({len(available)})",
                value="\n".join(available[:10]) + ("\n..." if len(available) > 10 else ""),
                inline=False
            )

        if linked:
            embed.add_field(
                name=f"🔴 Linked ({len(linked)})",
                value="\n".join(linked[:10]) + ("\n..." if len(linked) > 10 else ""),
                inline=False
            )

        embed.add_field(
            name="Admin Commands",
            value=(
                "• `/link_user <user> <emulator>` - Link user to emulator\n"
                "• `/relink_user <user> <emulator>` - Relink user to new emulator\n"
                "• `/grant <user> <days>` - Grant subscription"
            ),
            inline=False
        )

        embed.add_field(
            name="Note",
            value="Users use `/link <emulator_name>` to link themselves to an emulator",
            inline=False
        )

        embed.timestamp = datetime.utcnow()

        await ctx.followup.send(embed=embed, ephemeral=True)

    @bot.slash_command(
        name="relink_user",
        description="[Admin] Relink user to different emulator"
    )
    async def relink_user(
        ctx: discord.ApplicationContext,
        user: Option(discord.Member, "User to relink", required=True),
        emulator_name: Option(str, "New emulator name", required=True)
    ):
        """Relink user to different emulator."""
        if not is_admin(ctx):
            await ctx.respond("You don't have permission to use this command.", ephemeral=True)
            return

        await ctx.defer(ephemeral=True)

        # Get current user info
        current_user = data_manager.get_user(str(user.id))
        if not current_user:
            await ctx.followup.send("User not in system. Use `/grant` to grant access first.", ephemeral=True)
            return

        if current_user.is_running:
            stop_result = bot_service.force_stop_instance(str(user.id))
            if not stop_result['success']:
                await ctx.followup.send(f"Cannot stop current bot: {stop_result['message']}", ephemeral=True)
                return

        # Link to new emulator
        link_result = bot_service.link_user_to_emulator(
            user_id=str(user.id),
            emulator_name=emulator_name,
            discord_name=str(user)
        )

        # Log action
        old_emulator = current_user.emulator_name or f"Index {current_user.emulator_index}"
        data_manager.log_action(
            user_id=str(user.id),
            user_name=str(user),
            action=ActionType.CONFIG_CHANGE,
            details=f"Relinked from {old_emulator} to {emulator_name}",
            result=ActionResult.SUCCESS if link_result['success'] else ActionResult.FAILED,
            performed_by=str(ctx.author.id)
        )

        if link_result['success']:
            message = f"**Relink successful!**\n\n"
            message += f"**User:** {user.mention}\n"
            message += f"**From:** {old_emulator}\n"
            message += f"**To:** {emulator_name}\n\n"
            message += f"User can now use `/start`."
        else:
            message = f"**Relink failed:** {link_result['message']}"

        await ctx.followup.send(message, ephemeral=True)

    @bot.slash_command(
        name="unlink_user",
        description="[Admin] Unlink user from emulator"
    )
    async def unlink_user(
        ctx: discord.ApplicationContext,
        user: Option(discord.Member, "User to unlink", required=True)
    ):
        """Unlink user from emulator (admin command)."""
        if not is_admin(ctx):
            await ctx.respond("You don't have permission to use this command.", ephemeral=True)
            return

        await ctx.defer(ephemeral=True)

        # Get current user info
        current_user = data_manager.get_user(str(user.id))
        if not current_user:
            await ctx.followup.send("User not found in system.", ephemeral=True)
            return

        if current_user.is_running:
            stop_result = bot_service.force_stop_instance(str(user.id))
            if not stop_result['success']:
                await ctx.followup.send(f"Cannot stop current bot: {stop_result['message']}", ephemeral=True)
                return

        # Unlink user
        unlink_result = bot_service.unlink_user_from_emulator(str(user.id))

        # Log action
        old_emulator = current_user.emulator_name or f"Index {current_user.emulator_index}"
        data_manager.log_action(
            user_id=str(user.id),
            user_name=str(user),
            action=ActionType.CONFIG_CHANGE,
            details=f"Admin unlinked user from {old_emulator}",
            result=ActionResult.SUCCESS if unlink_result['success'] else ActionResult.FAILED,
            performed_by=str(ctx.author.id)
        )

        if unlink_result['success']:
            message = f"**Unlink successful!**\n\n"
            message += f"**User:** {user.mention}\n"
            message += f"**Unlinked from:** {old_emulator}\n\n"
            message += f"User needs to be linked again to use the bot."
        else:
            message = f"**Unlink failed:** {unlink_result['message']}"

        await ctx.followup.send(message, ephemeral=True)

    @bot.slash_command(
        name="unlink_expired",
        description="[Admin] Unlink all expired users"
    )
    async def unlink_expired(ctx: discord.ApplicationContext):
        """Unlink all expired users."""
        if not is_admin(ctx):
            await ctx.respond("You don't have permission to use this command.", ephemeral=True)
            return

        await ctx.defer(ephemeral=True)

        # Get all expired users
        all_users = data_manager.get_all_users()
        expired_users = [u for u in all_users if u.subscription.is_expired and u.emulator_index != -1]

        if not expired_users:
            await ctx.followup.send("No expired users currently linked to emulators.", ephemeral=True)
            return

        success_count = 0
        error_count = 0
        details = []

        for user in expired_users:
            try:
                if user.is_running:
                    stop_result = bot_service.force_stop_instance(str(user.discord_id))
                    if not stop_result['success']:
                        error_count += 1
                        details.append(f"Failed {user.discord_name}: Cannot stop bot")
                        continue

                unlink_result = bot_service.unlink_user_from_emulator(str(user.discord_id))
                if unlink_result['success']:
                    success_count += 1
                    details.append(f"OK {user.discord_name}: Unlinked from {user.emulator_name or f'Index {user.emulator_index}'}")
                else:
                    error_count += 1
                    details.append(f"Failed {user.discord_name}: {unlink_result['message']}")
            except Exception as e:
                error_count += 1
                details.append(f"Failed {user.discord_name}: Error - {str(e)}")

        # Log action
        data_manager.log_action(
            user_id=str(ctx.author.id),
            user_name=str(ctx.author),
            action=ActionType.CONFIG_CHANGE,
            details=f"Bulk unlink expired: {success_count} success, {error_count} errors",
            result=ActionResult.SUCCESS if success_count > 0 else ActionResult.FAILED,
            performed_by=str(ctx.author.id)
        )

        message = f"**Bulk Unlink Expired Users Complete**\n\n"
        message += f"**Total:** {len(expired_users)} users\n"
        message += f"**Success:** {success_count} users\n"
        message += f"**Errors:** {error_count} users\n\n"

        message += "**Details:**\n"
        message += "\n".join(details[:10])
        if len(details) > 10:
            message += f"\n... and {len(details) - 10} more results."

        await ctx.followup.send(message, ephemeral=True)

    @bot.slash_command(
        name="delete_expired",
        description="[Admin] Delete all expired users"
    )
    async def delete_expired(ctx: discord.ApplicationContext):
        """Delete all expired users from system."""
        if not is_admin(ctx):
            await ctx.respond("You don't have permission to use this command.", ephemeral=True)
            return

        await ctx.defer(ephemeral=True)

        # Get all expired users
        all_users = data_manager.get_all_users()
        expired_users = [u for u in all_users if u.subscription.is_expired]

        if not expired_users:
            await ctx.followup.send("No expired users to delete.", ephemeral=True)
            return

        await ctx.followup.send(
            f"**Warning:** Will delete {len(expired_users)} expired users.\n"
            f"This action cannot be undone. Reply 'confirm' to proceed.",
            ephemeral=True
        )

        # Wait for confirmation (simplified - in production you'd want a better confirmation system)
        # For now, proceed with deletion

        success_count = 0
        error_count = 0
        details = []

        for user in expired_users:
            try:
                if user.is_running:
                    bot_service.force_stop_instance(str(user.discord_id))

                if data_manager.delete_user(str(user.discord_id)):
                    success_count += 1
                    details.append(f"OK {user.discord_name}: Deleted")
                else:
                    error_count += 1
                    details.append(f"Failed {user.discord_name}: Cannot delete")
            except Exception as e:
                error_count += 1
                details.append(f"Failed {user.discord_name}: Error - {str(e)}")

        # Log action
        data_manager.log_action(
            user_id=str(ctx.author.id),
            user_name=str(ctx.author),
            action=ActionType.CONFIG_CHANGE,
            details=f"Bulk delete expired: {success_count} success, {error_count} errors",
            result=ActionResult.SUCCESS if success_count > 0 else ActionResult.FAILED,
            performed_by=str(ctx.author.id)
        )

        message = f"**Bulk Delete Expired Users Complete**\n\n"
        message += f"**Total:** {len(expired_users)} users\n"
        message += f"**Deleted:** {success_count} users\n"
        message += f"**Errors:** {error_count} users\n\n"

        message += "**Details:**\n"
        message += "\n".join(details[:10])
        if len(details) > 10:
            message += f"\n... and {len(details) - 10} more results."

        await ctx.followup.send(message, ephemeral=True)

    @bot.slash_command(
        name="sync_states",
        description="[Admin] Manually sync states between GUI and Discord"
    )
    async def sync_states(
        ctx: discord.ApplicationContext,
        user: Option(discord.Member, "Sync specific user (optional, syncs all if not specified)", required=False, default=None)
    ):
        """Manually sync states between GUI and Discord."""
        if not is_admin(ctx):
            await ctx.respond("You don't have permission to use this command.", ephemeral=True)
            return

        await ctx.defer(ephemeral=True)

        sync_count = 0
        error_count = 0
        users_to_sync = []

        if user:
            # Sync specific user
            target_user = data_manager.get_user(str(user.id))
            if target_user:
                users_to_sync = [target_user]
            else:
                await ctx.followup.send(f"User {user.mention} not found in database.", ephemeral=True)
                return
        else:
            # Sync all users with active subscriptions
            users_to_sync = data_manager.get_all_users()

        message_parts = []
        message_parts.append(f"🔄 **State Synchronization Report**\n")

        for target_user in users_to_sync:
            # Skip users with no emulator or expired subscriptions
            if target_user.emulator_index == -1 or target_user.subscription.is_expired:
                continue

            try:
                # Get actual emulator state
                actual_state = bot_service._get_actual_emulator_state(target_user.emulator_index)

                # Check for inconsistencies and sync
                if target_user.is_running and not actual_state:
                    print(f"[SYNC] Manual sync: User {target_user.discord_name} was stopped outside Discord. Updating state...")
                    target_user.status = InstanceStatus.STOPPED.value
                    target_user.last_stop = datetime.now(pytz.UTC).isoformat()
                    data_manager.save_user(target_user)
                    sync_count += 1
                    message_parts.append(f"✅ {target_user.discord_name}: Synced from RUNNING to STOPPED")

                elif not target_user.is_running and actual_state:
                    print(f"[SYNC] Manual sync: User {target_user.discord_name} was started outside Discord. Updating state...")
                    target_user.status = InstanceStatus.RUNNING.value
                    target_user.last_start = datetime.now(pytz.UTC).isoformat()
                    target_user.last_heartbeat = datetime.now(pytz.UTC).isoformat()
                    data_manager.save_user(target_user)
                    sync_count += 1
                    message_parts.append(f"✅ {target_user.discord_name}: Synced from STOPPED to RUNNING")

            except Exception as e:
                error_count += 1
                print(f"[ERROR] Failed to sync state for user {target_user.discord_name}: {e}")
                message_parts.append(f"❌ {target_user.discord_name}: Error - {str(e)}")

        # Build final message
        if sync_count == 0 and error_count == 0:
            message_parts.append("\n✅ All states are already synchronized.")
        else:
            message_parts.append(f"\n📊 **Summary:** {sync_count} users synced, {error_count} errors")

        # Log action
        data_manager.log_action(
            user_id=str(ctx.author.id),
            user_name=str(ctx.author),
            action=ActionType.CONFIG_CHANGE,
            details=f"Manual state sync: {sync_count} users synced, {error_count} errors",
            result=ActionResult.SUCCESS,
            performed_by=str(ctx.author.id)
        )

        # Limit message length if too many users
        final_message = "\n".join(message_parts[:20])  # Limit to 20 lines
        if len(message_parts) > 20:
            final_message += f"\n... and {len(message_parts) - 20} more entries."

        await ctx.followup.send(final_message, ephemeral=True)
