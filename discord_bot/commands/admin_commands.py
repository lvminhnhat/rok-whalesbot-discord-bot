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
        description="[Admin] Cấp quyền sử dụng cho user"
    )
    async def grant(
        ctx: discord.ApplicationContext,
        user: Option(discord.Member, "User cần cấp quyền", required=True),
        days: Option(int, "Số days sử dụng", required=True),
        emulator_index: Option(int, "Emulator index (cho user mới)", required=False, default=None)
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
        
        # Validate emulator index if provided
        if emulator_index is not None:
            config = data_manager.get_config()
            is_valid, error_msg = validate_emulator_index(emulator_index, config.max_emulators)
            if not is_valid:
                await ctx.respond(error_msg, ephemeral=True)
                return
        
        await ctx.defer(ephemeral=True)
        
        result = subscription_service.grant_subscription(
            discord_id=str(user.id),
            discord_name=str(user),
            days=days,
            emulator_index=emulator_index
        )
        
        # Log action
        data_manager.log_action(
            user_id=str(user.id),
            user_name=str(user),
            action=ActionType.GRANT,
            details=f"Granted {days} days, emulator: {emulator_index}",
            result=ActionResult.SUCCESS if result['success'] else ActionResult.FAILED,
            performed_by=str(ctx.author.id)
        )
        
        await ctx.followup.send(result['message'], ephemeral=True)
    
    @bot.slash_command(
        name="add_days",
        description="[Admin] Thêm days sử dụng cho user"
    )
    async def add_days(
        ctx: discord.ApplicationContext,
        user: Option(discord.Member, "User cần thêm days", required=True),
        days: Option(int, "Số days cần thêm", required=True)
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
        description="[Admin] Đặt days hết hạn cho user"
    )
    async def set_expiry(
        ctx: discord.ApplicationContext,
        user: Option(discord.Member, "User cần đặt hạn", required=True),
        date: Option(str, "Ngày hết hạn (YYYY-MM-DD)", required=True)
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
        description="[Admin] Thu hồi quyền sử dụng của user"
    )
    async def revoke(
        ctx: discord.ApplicationContext,
        user: Option(discord.Member, "User cần thu hồi", required=True)
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
        description="[Admin] Bật bot thay cho user"
    )
    async def force_start(
        ctx: discord.ApplicationContext,
        user: Option(discord.Member, "User cần bật bot", required=True)
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
        description="[Admin] Dừng bot thay cho user"
    )
    async def force_stop(
        ctx: discord.ApplicationContext,
        user: Option(discord.Member, "User cần dừng bot", required=True)
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
        description="[Admin] Liệt kê user sắp hết hạn"
    )
    async def list_expiring(
        ctx: discord.ApplicationContext,
        days: Option(int, "Số days (mặc định 7)", required=False, default=7)
    ):
        """List users expiring soon."""
        if not is_admin(ctx):
            await ctx.respond("You don't have permission to use this command.", ephemeral=True)
            return
        
        expiring_users = subscription_service.get_expiring_users(days)
        
        if not expiring_users:
            await ctx.respond(f"✅ Không có user nào hết hạn trong {days} days tới.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title=f"Users expiring soon ({days} days)",
            color=discord.Color.orange()
        )
        
        for user in expiring_users[:25]:  # Limit to 25 fields
            embed.add_field(
                name=user.discord_name,
                value=f"Còn {user.subscription.days_left} days\nEmulator: #{user.emulator_index}",
                inline=True
            )
        
        if len(expiring_users) > 25:
            embed.set_footer(text=f"Và {len(expiring_users) - 25} user khác...")
        
        embed.timestamp = datetime.utcnow()
        
        await ctx.respond(embed=embed, ephemeral=True)
    
    @bot.slash_command(
        name="who",
        description="[Admin] Xem danh sách đang chạy"
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
            embed.set_footer(text=f"Và {len(running_users) - 25} instance khác...")
        else:
            embed.set_footer(text=f"Tổng: {len(running_users)} instances")
        
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
        description="[Admin] Xem audit logs"
    )
    async def logs(
        ctx: discord.ApplicationContext,
        user: Option(discord.Member, "Lọc theo user (tùy chọn)", required=False, default=None),
        limit: Option(int, "Số lượng logs (mặc định 20)", required=False, default=20)
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
            embed.description = f"Logs của {user.mention}"
        
        for log in logs[:10]:  # Show max 10 in embed
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
            embed.set_footer(text=f"Hiển thị 10/{len(logs)} logs")
        
        embed.timestamp = datetime.utcnow()
        
        await ctx.respond(embed=embed, ephemeral=True)

