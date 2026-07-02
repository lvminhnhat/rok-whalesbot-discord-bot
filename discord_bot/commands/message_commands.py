"""
Message-based user commands for Discord bot.
Users type plain text commands in allowed channels instead of slash commands.
"""

import re
from datetime import datetime

import discord
import pytz

from discord_bot.utils.permissions import in_allowed_channel_msg
from discord_bot.services.bot_service import BotService
from discord_bot.services.subscription_service import SubscriptionService
from discord_bot.services.schedule_service import parse_hhmm_to_next_utc
from shared.data_manager import DataManager
from shared.constants import ActionType, ActionResult


# Commands that the bot recognizes (no prefix)
COMMANDS = {'start', 'stop', 'status', 'expiry', 'link', 'help', 'queue', 'view',
            'schedules', 'unschedule'}

# Loose HH:MM shape - used only to tell "you tried to give a time but it's
# malformed" from "this is an emulator name".
_LOOSE_TIME_RE = re.compile(r"^\d{1,2}:\d{2}$")


def _split_target_time(args: str):
    """Split a start/stop argument string into (target, when_dt, time_error).

    target: '' (default emulator), 'all', or an emulator name.
    when_dt: a UTC datetime if a valid trailing HH:MM was given, else None.
    time_error: a message if the trailing token looked like a time but was
                invalid (e.g. '25:00'), else None.
    """
    toks = args.split()
    when = None
    time_error = None
    if toks:
        last = toks[-1]
        parsed = parse_hhmm_to_next_utc(last)
        if parsed is not None:
            when = parsed
            toks = toks[:-1]
        elif _LOOSE_TIME_RE.match(last):
            time_error = (f"`{last}` isn't a valid 24-hour UTC time "
                          f"(use HH:MM, 00:00-23:59).")
            toks = toks[:-1]
    return " ".join(toks).strip(), when, time_error


def _normalize_target(target: str):
    """'' -> None (default emulator), 'all' (any case) -> 'all', else the name."""
    if not target:
        return None
    if target.lower() == "all":
        return "all"
    return target


def setup_message_commands(
    bot: discord.Bot,
    bot_service: BotService,
    subscription_service: SubscriptionService,
    data_manager: DataManager
):
    """
    Setup message-based user commands.

    Args:
        bot: Discord bot instance
        bot_service: Bot service instance
        subscription_service: Subscription service instance
        data_manager: Data manager instance
    """

    @bot.listen("on_message")
    async def on_message(message: discord.Message):
        # Ignore messages from bots
        if message.author.bot:
            return

        # Parse command from message content
        content = message.content.strip()
        if not content:
            return

        parts = content.split(maxsplit=1)
        command = parts[0].lower()
        args = parts[1].strip() if len(parts) > 1 else ""

        # Ignore unknown commands silently
        if command not in COMMANDS:
            return

        # Check if in allowed channel (silently ignore if not)
        allowed, _ = in_allowed_channel_msg(message)
        if not allowed:
            return

        user_id = str(message.author.id)

        if command == "start":
            await handle_start_stop(message, user_id, args, "start", bot, bot_service, data_manager)
        elif command == "stop":
            await handle_start_stop(message, user_id, args, "stop", bot, bot_service, data_manager)
        elif command == "status":
            await handle_status(message, user_id, bot_service)
        elif command == "expiry":
            await handle_expiry(message, user_id, data_manager)
        elif command == "link":
            await handle_link(message, user_id, args, bot_service, data_manager)
        elif command == "help":
            await handle_help(message)
        elif command == "queue":
            await handle_queue(message, user_id, bot)
        elif command == "view":
            await handle_view(message, user_id, args, bot_service, data_manager)
        elif command == "schedules":
            await handle_schedules(message, user_id, bot)
        elif command == "unschedule":
            await handle_unschedule(message, user_id, args, bot)


async def handle_start_stop(
    message: discord.Message,
    user_id: str,
    args: str,
    action: str,                       # 'start' | 'stop'
    bot,
    bot_service: BotService,
    data_manager: DataManager
):
    """Handle `start`/`stop`, with optional 'all' target and optional trailing
    HH:MM UTC time (which defers the action instead of running it now).

    Forms:
        start                 -> start your (default) emulator now
        start <name>          -> start that emulator now
        start all             -> start every emulator you own now
        start [<name>|all] HH:MM  -> schedule it for the next HH:MM UTC
    """
    target_raw, when, time_error = _split_target_time(args)
    if time_error:
        await message.reply(time_error)
        return
    target = _normalize_target(target_raw)

    if when is not None:
        await _schedule_action(message, user_id, action, target, when, bot, data_manager)
        return

    action_type = ActionType.START if action == "start" else ActionType.STOP
    async with message.channel.typing():
        result = await bot._execute_user_action(user_id, action, target)

    tgt_desc = "all" if target == "all" else (target or "default")
    data_manager.log_action(
        user_id=user_id,
        user_name=str(message.author),
        action=action_type,
        details=f"Emulator {action} attempt ({tgt_desc})",
        result=ActionResult.SUCCESS if result['success'] else ActionResult.FAILED
    )
    await message.reply(result['message'])


def _validate_schedulable(user_id, target, bot_service, data_manager):
    """Return an error message if this user can't schedule `target`, else None."""
    is_admin = bot_service._is_admin(user_id)
    user = data_manager.get_user(user_id)
    if target == "all":
        if not user or not user.is_linked:
            return "You aren't linked to any emulator, so `all` has nothing to act on."
        return None
    if target is None:
        if is_admin and not user:
            return "Admins must name an emulator (there's no default to schedule)."
        if not user or not user.is_linked:
            return "You aren't linked to any emulator. Use `link <name>` first."
        return None
    # named emulator
    if is_admin:
        return None
    if not user:
        return "You don't have access. Please contact admin."
    if not user.get_emulator_by_name(target):
        return f'You are not linked to emulator "{target}". Use `link {target}` first.'
    return None


async def _schedule_action(message, user_id, action, target, when, bot, data_manager):
    """Persist a deferred start/stop and confirm it."""
    err = _validate_schedulable(user_id, target, bot.bot_service, data_manager)
    if err:
        await message.reply(err)
        return
    job = bot.schedule_service.add(
        user_id=user_id,
        user_name=str(message.author),
        channel_id=message.channel.id,
        action=action,
        target=target,
        when_utc=when,
    )
    delta = when - datetime.now(pytz.UTC)
    mins = max(0, int(delta.total_seconds() // 60))
    in_txt = f"{mins // 60}h {mins % 60}m" if mins >= 60 else f"{mins}m"
    await message.reply(
        f"🗓️ Scheduled **{action} {job.describe_target()}** for "
        f"<t:{int(when.timestamp())}:t> UTC (in ~{in_txt}). "
        f"Cancel with `unschedule {job.id}`."
    )


async def handle_schedules(message: discord.Message, user_id: str, bot):
    """List the user's pending scheduled actions."""
    jobs = bot.schedule_service.for_user(user_id)
    if not jobs:
        await message.reply("You have no scheduled actions. "
                            "Schedule one with e.g. `start all 13:00`.")
        return
    lines = ["**Your scheduled actions**"]
    for j in jobs:
        lines.append(f"• `{j.id}` — {j.action} {j.describe_target()} at "
                     f"<t:{int(j.when_dt.timestamp())}:f> (<t:{int(j.when_dt.timestamp())}:R>)")
    lines.append("\nCancel one with `unschedule <id>`.")
    await message.reply("\n".join(lines))


async def handle_unschedule(message: discord.Message, user_id: str, args: str, bot):
    """Cancel a pending scheduled action by id."""
    job_id = args.strip().split()[0] if args.strip() else ""
    if not job_id:
        await message.reply("Usage: `unschedule <id>` (see ids with `schedules`).")
        return
    if bot.schedule_service.remove(job_id, user_id=user_id):
        await message.reply(f"🗑️ Cancelled scheduled action `{job_id}`.")
    else:
        await message.reply(f"No scheduled action `{job_id}` found for you.")


async def handle_status(
    message: discord.Message,
    user_id: str,
    bot_service: BotService
):
    """Handle the status command."""
    status_info = bot_service.get_status(user_id)

    if not status_info['exists']:
        await message.reply(status_info['message'])
        return

    # Build plain text status
    lines = []
    lines.append(f"**Miner Status**")
    lines.append(f"Status: {status_info['status']}")
    lines.append(f"Emulator: #{status_info['emulator_index']}")

    if status_info['is_running'] and status_info['uptime_seconds']:
        hours = status_info['uptime_seconds'] // 3600
        minutes = (status_info['uptime_seconds'] % 3600) // 60
        lines.append(f"Uptime: {hours}h {minutes}m")

    if status_info['last_heartbeat']:
        try:
            hb_dt = datetime.fromisoformat(status_info['last_heartbeat'])
            lines.append(f"Last Update: <t:{int(hb_dt.timestamp())}:R>")
        except Exception:
            pass

    sub_status = "Active" if status_info['subscription_active'] else "Expired"
    lines.append(f"Subscription: {sub_status}")
    lines.append(f"Remaining: {status_info['days_left']} days")

    if status_info.get('state_synced', False):
        lines.append(f"\n⚠️ {status_info.get('sync_message', 'State was synchronized with GUI.')}")

    await message.reply("\n".join(lines))


async def handle_expiry(
    message: discord.Message,
    user_id: str,
    data_manager: DataManager
):
    """Handle the expiry command."""
    user = data_manager.get_user(user_id)

    if not user:
        await message.reply("You don't have access. Please contact admin.")
        return

    try:
        start_dt = user.subscription.start_datetime
        end_dt = user.subscription.end_datetime

        lines = []
        lines.append("**Subscription Information**")
        lines.append(f"Start: <t:{int(start_dt.timestamp())}:D>")
        lines.append(f"Expires: <t:{int(end_dt.timestamp())}:D>")
        lines.append(f"Remaining: {user.subscription.days_left} days")

        if user.subscription.is_active:
            lines.append("Status: Active")
        else:
            lines.append("Status: Expired - Please renew")

        await message.reply("\n".join(lines))
    except Exception:
        await message.reply("Error displaying subscription information.")


async def handle_link(
    message: discord.Message,
    user_id: str,
    args: str,
    bot_service: BotService,
    data_manager: DataManager
):
    """Handle the link command."""
    if not args:
        await message.reply("Usage: `link <emulator_name>`")
        return

    emulator_name = args

    result = bot_service.link_user_to_emulator(
        user_id,
        emulator_name,
        discord_name=str(message.author)
    )

    data_manager.log_action(
        user_id=user_id,
        user_name=str(message.author),
        action=ActionType.CONFIG_CHANGE,
        details=f"Link to emulator: {emulator_name}",
        result=ActionResult.SUCCESS if result['success'] else ActionResult.FAILED
    )

    await message.reply(result['message'])


async def handle_view(
    message: discord.Message,
    user_id: str,
    args: str,
    bot_service: BotService,
    data_manager: DataManager
):
    """Handle the view command - screenshot an emulator."""
    if not args:
        await message.reply("Usage: `view <emulator_name>`")
        return

    emulator_name = args

    # Check ownership or admin
    is_admin = bot_service._is_admin(user_id)
    if not is_admin:
        user = data_manager.get_user(user_id)
        if not user:
            await message.reply("You don't have access. Please contact admin.")
            return
        emu_entry = user.get_emulator_by_name(emulator_name)
        if not emu_entry:
            await message.reply(f'You are not linked to emulator "{emulator_name}".')
            return

    async with message.channel.typing():
        result = await bot_service.screenshot_emulator(emulator_name)

    if not result['success']:
        await message.reply(result['message'])
        return

    file = discord.File(result['image'], filename=f"{result['name']}.png")
    await message.reply(file=file)


async def handle_help(message: discord.Message):
    """Handle the help command."""
    help_text = (
        "**Miner Usage Guide**\n"
        "\n"
        "**Miner Control**\n"
        "`start` / `stop` - Start/stop your miner\n"
        "`start <name>` / `stop <name>` - A specific emulator\n"
        "`start all` / `stop all` - Every emulator you own\n"
        "`status` - Check miner status\n"
        "`view <name>` - Screenshot an emulator\n"
        "`expiry` - View subscription info\n"
        "\n"
        "**Scheduling (times are UTC, 24-hour)**\n"
        "`start <name> 13:00` - Start at the next 13:00 UTC\n"
        "`stop all 14:30` - Stop everything at 14:30 UTC\n"
        "`schedules` - List your scheduled actions\n"
        "`unschedule <id>` - Cancel a scheduled action\n"
        "\n"
        "**Emulator Management**\n"
        "`link <emulator_name>` - Link to an emulator\n"
        "\n"
        "**Other**\n"
        "`queue` - Show queue status\n"
        "`help` - Show this help message\n"
        "\n"
        "**Notes**\n"
        "• Already-running/stopped emulators are reported, not toggled\n"
        "• Scheduled actions survive a bot restart\n"
        "• Bot auto-stops when subscription expires\n"
        "• Contact admin for support"
    )

    await message.reply(help_text)


async def handle_queue(
    message: discord.Message,
    user_id: str,
    bot: discord.Bot
):
    """Handle the queue command."""
    if not hasattr(bot, 'operation_queue'):
        await message.reply("Queue system is not available.")
        return

    queue_info = bot.operation_queue.get_queue_info()
    pending_ops = bot.operation_queue.get_pending_operations(limit=10)

    user_pending_ops = [op for op in pending_ops if op['user_name'] == str(message.author)]

    lines = []
    lines.append("**Queue Status**")
    lines.append(f"Pending: {queue_info['pending_operations']}")
    lines.append(f"Processing: {queue_info['processing_operations']}")
    lines.append(f"Processor Active: {'Yes' if queue_info['is_processing'] else 'No'}")

    if user_pending_ops:
        op = user_pending_ops[0]
        lines.append(f"\n**Your Queue Position**")
        lines.append(f"Operation: {op['operation_type'].title()}")
        lines.append(f"Position: #{op['queue_position']}")
        lines.append(f"Emulator: #{op['emulator_index']}")
    else:
        lines.append("\nYou have no pending operations.")

    if pending_ops:
        lines.append(f"\n**Pending Operations**")
        for i, op in enumerate(pending_ops[:5], 1):
            lines.append(f"#{i}. {op['operation_type'].title()} - {op['user_name']} (Emulator #{op['emulator_index']})")
        if len(pending_ops) > 5:
            lines.append(f"... and {len(pending_ops) - 5} more")

    await message.reply("\n".join(lines))
