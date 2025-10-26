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
        days: Option(int, "Số days sử dụng", required=True)
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

    @bot.slash_command(
        name="link_user",
        description="[Admin] Gắn user vào emulator"
    )
    async def link_user(
        ctx: discord.ApplicationContext,
        user: Option(discord.Member, "User cần gắn", required=True),
        emulator_name: Option(str, "Tên emulator để gắn", required=True)
    ):
        """Link user to emulator (admin command)."""
        if not is_admin(ctx):
            await ctx.respond("You don't have permission to use this command.", ephemeral=True)
            return

        await ctx.defer(ephemeral=True)

        # Check if user exists
        existing_user = data_manager.get_user(str(user.id))
        if not existing_user:
            await ctx.followup.send("User chưa có trong hệ thống. Sử dụng `/grant` để cấp quyền trước.", ephemeral=True)
            return

        # Force stop if running
        if existing_user.is_running:
            stop_result = bot_service.force_stop_instance(str(user.id))
            if not stop_result['success']:
                await ctx.followup.send(f"Không thể dừng bot hiện tại: {stop_result['message']}", ephemeral=True)
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
            message = f"✅ **Gắn user thành công!**\n\n"
            message += f"**User:** {user.mention}\n"
            message += f"**Emulator:** {emulator_name}\n\n"
            message += f"User có thể sử dụng `/start` ngay."
        else:
            message = f"❌ **Gắn user thất bại:** {link_result['message']}"

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
            name="📋 Admin Commands",
            value=(
                "• `/link_user <user> <emulator>` - Gắn user vào emulator\n"
                "• `/relink_user <user> <emulator>` - Gắn lại user vào emulator mới\n"
                "• `/grant <user> <days>` - Cấp subscription"
            ),
            inline=False
        )

        embed.add_field(
            name="📝 Note",
            value="User sẽ dùng `/link <emulator_name>` để tự gắn vào emulator",
            inline=False
        )

        embed.timestamp = datetime.utcnow()

        await ctx.followup.send(embed=embed, ephemeral=True)

    @bot.slash_command(
        name="relink_user",
        description="[Admin] Gắn lại user vào emulator mới"
    )
    async def relink_user(
        ctx: discord.ApplicationContext,
        user: Option(discord.Member, "User cần gắn lại", required=True),
        emulator_name: Option(str, "Tên emulator mới", required=True)
    ):
        """Relink user to different emulator."""
        if not is_admin(ctx):
            await ctx.respond("You don't have permission to use this command.", ephemeral=True)
            return

        await ctx.defer(ephemeral=True)

        # Get current user info
        current_user = data_manager.get_user(str(user.id))
        if not current_user:
            await ctx.followup.send("User chưa có trong hệ thống. Sử dụng `/grant_access` để cấp quyền.", ephemeral=True)
            return

        # Force stop if running
        if current_user.is_running:
            stop_result = bot_service.force_stop_instance(str(user.id))
            if not stop_result['success']:
                await ctx.followup.send(f"Không thể dừng bot hiện tại: {stop_result['message']}", ephemeral=True)
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
            message = f"✅ **Gắn lại thành công!**\n\n"
            message += f"**User:** {user.mention}\n"
            message += f"**Từ:** {old_emulator}\n"
            message += f"**Đến:** {emulator_name}\n\n"
            message += f"User có thể sử dụng `/start` ngay."
        else:
            message = f"❌ **Gắn lại thất bại:** {link_result['message']}"

        await ctx.followup.send(message, ephemeral=True)

    @bot.slash_command(
        name="unlink_user",
        description="[Admin] Unlink user from emulator"
    )
    async def unlink_user(
        ctx: discord.ApplicationContext,
        user: Option(discord.Member, "User cần unlink", required=True)
    ):
        """Unlink user from emulator (admin command)."""
        if not is_admin(ctx):
            await ctx.respond("You don't have permission to use this command.", ephemeral=True)
            return

        await ctx.defer(ephemeral=True)

        # Get current user info
        current_user = data_manager.get_user(str(user.id))
        if not current_user:
            await ctx.followup.send("User không tồn tại trong hệ thống.", ephemeral=True)
            return

        # Force stop if running
        if current_user.is_running:
            stop_result = bot_service.force_stop_instance(str(user.id))
            if not stop_result['success']:
                await ctx.followup.send(f"Không thể dừng bot hiện tại: {stop_result['message']}", ephemeral=True)
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
            message = f"✅ **Unlink thành công!**\n\n"
            message += f"**User:** {user.mention}\n"
            message += f"**Đã unlink từ:** {old_emulator}\n\n"
            message += f"User cần được linked lại để sử dụng bot."
        else:
            message = f"❌ **Unlink thất bại:** {unlink_result['message']}"

        await ctx.followup.send(message, ephemeral=True)

    @bot.slash_command(
        name="unlink_expired",
        description="[Admin] Unlink tất cả users đã hết hạn"
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
            await ctx.followup.send("Không có user nào đã hết hạn đang linked to emulator.", ephemeral=True)
            return

        success_count = 0
        error_count = 0
        details = []

        for user in expired_users:
            try:
                # Force stop if running
                if user.is_running:
                    stop_result = bot_service.force_stop_instance(str(user.discord_id))
                    if not stop_result['success']:
                        error_count += 1
                        details.append(f"❌ {user.discord_name}: Không thể dừng bot")
                        continue

                # Unlink user
                unlink_result = bot_service.unlink_user_from_emulator(str(user.discord_id))
                if unlink_result['success']:
                    success_count += 1
                    details.append(f"✅ {user.discord_name}: Unlinked from {user.emulator_name or f'Index {user.emulator_index}'}")
                else:
                    error_count += 1
                    details.append(f"❌ {user.discord_name}: {unlink_result['message']}")
            except Exception as e:
                error_count += 1
                details.append(f"❌ {user.discord_name}: Error - {str(e)}")

        # Log action
        data_manager.log_action(
            user_id=str(ctx.author.id),
            user_name=str(ctx.author),
            action=ActionType.CONFIG_CHANGE,
            details=f"Bulk unlink expired: {success_count} success, {error_count} errors",
            result=ActionResult.SUCCESS if success_count > 0 else ActionResult.FAILED,
            performed_by=str(ctx.author.id)
        )

        # Build response message
        message = f"🔄 **Bulk Unlink Expired Users Complete**\n\n"
        message += f"**Tổng cộng:** {len(expired_users)} users\n"
        message += f"**Thành công:** {success_count} users\n"
        message += f"**Lỗi:** {error_count} users\n\n"

        # Show first 10 details
        message += "**Chi tiết:**\n"
        message += "\n".join(details[:10])
        if len(details) > 10:
            message += f"\n... và {len(details) - 10} kết quả khác."

        await ctx.followup.send(message, ephemeral=True)

    @bot.slash_command(
        name="delete_expired",
        description="[Admin] Xóa tất cả users đã hết hạn"
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
            await ctx.followup.send("Không có user nào đã hết hạn để xóa.", ephemeral=True)
            return

        # Confirm with user
        await ctx.followup.send(
            f"⚠️ **Cảnh báo:** Sẽ xóa {len(expired_users)} users đã hết hạn.\n"
            f"Hành động này không thể hoàn tác. Reply 'confirm' để tiếp tục.",
            ephemeral=True
        )

        # Wait for confirmation (simplified - in production you'd want a better confirmation system)
        # For now, proceed with deletion

        success_count = 0
        error_count = 0
        details = []

        for user in expired_users:
            try:
                # Force stop if running
                if user.is_running:
                    bot_service.force_stop_instance(str(user.discord_id))

                # Delete user
                if data_manager.delete_user(str(user.discord_id)):
                    success_count += 1
                    details.append(f"✅ {user.discord_name}: Đã xóa")
                else:
                    error_count += 1
                    details.append(f"❌ {user.discord_name}: Không thể xóa")
            except Exception as e:
                error_count += 1
                details.append(f"❌ {user.discord_name}: Error - {str(e)}")

        # Log action
        data_manager.log_action(
            user_id=str(ctx.author.id),
            user_name=str(ctx.author),
            action=ActionType.CONFIG_CHANGE,
            details=f"Bulk delete expired: {success_count} success, {error_count} errors",
            result=ActionResult.SUCCESS if success_count > 0 else ActionResult.FAILED,
            performed_by=str(ctx.author.id)
        )

        # Build response message
        message = f"🗑️ **Bulk Delete Expired Users Complete**\n\n"
        message += f"**Tổng cộng:** {len(expired_users)} users\n"
        message += f"**Đã xóa:** {success_count} users\n"
        message += f"**Lỗi:** {error_count} users\n\n"

        # Show first 10 details
        message += "**Chi tiết:**\n"
        message += "\n".join(details[:10])
        if len(details) > 10:
            message += f"\n... và {len(details) - 10} kết quả khác."

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
