# WhaleBots Discord Bot + Web Dashboard

Complete management system for WhaleBots automation with Discord bot integration and web-based administration.

## Features

### Discord Bot (Slash Commands)
- ✅ User commands: `/start`, `/stop`, `/status`, `/expiry`, `/help`
- ✅ Admin commands: `/grant`, `/add_days`, `/revoke`, `/config`, `/logs`
- ✅ Subscription management with expiry tracking
- ✅ Auto-stop on subscription expiry
- ✅ Cooldown protection
- ✅ Ephemeral responses (private)
- ✅ Full audit logging

### Web Dashboard
- ✅ Real-time system overview
- ✅ User management (CRUD operations)
- ✅ Instance monitoring
- ✅ Configuration management
- ✅ Audit log viewer
- ✅ Auto-refresh (polling)
- ✅ Responsive Bootstrap 5 UI

### Integration
- ✅ Seamless integration with `whalebots_automation`
- ✅ JSON-based storage (thread-safe)
- ✅ User → Emulator mapping
- ✅ Heartbeat monitoring
- ✅ Status tracking

## Quick Start

### 1. Check System
```bash
check_system.bat
```

### 2. Configure
Edit `.env`:
```env
DISCORD_BOT_TOKEN=your_bot_token_here
WHALEBOTS_PATH=C:\Users\DELL\Downloads\WhaleBots_1013
```

Edit `data/config.json`:
```json
{
  "admin_users": ["YOUR_DISCORD_USER_ID"]
}
```

### 3. Run
```bash
run.bat
```

This opens 2 windows:
- **Discord Bot** - Handles Discord commands
- **Web Dashboard** - http://127.0.0.1:5000

### 4. Test
In Discord:
```
/help
/config current_channel add
/status
```

## File Structure

```
WhaleBots_1013/
├── discord_bot/          # Discord bot (py-cord)
│   ├── bot.py           # Main bot
│   ├── commands/        # User & admin commands
│   ├── services/        # Bot & subscription services
│   └── utils/           # Permissions & validators
├── web_dashboard/       # Flask dashboard
│   ├── app.py          # Flask app
│   ├── routes/         # API endpoints
│   ├── templates/      # HTML pages
│   └── static/         # CSS & JS
├── shared/             # Shared data layer
│   ├── models.py       # User, Subscription models
│   ├── data_manager.py # JSON operations
│   └── constants.py    # Status constants
├── data/               # JSON database
│   ├── users.json      # User data
│   ├── config.json     # Bot config
│   └── audit_logs.json # Activity logs
├── whalebots_automation/ # WhaleBots integration
├── run.bat             # Start system
├── stop.bat            # Stop system
└── check_system.bat    # Verify setup
```

## Documentation

- 📖 **START_HERE.md** - Complete setup guide
- 📝 **COMMANDS_REFERENCE.md** - All commands reference
- 📋 **discord-bot-web.plan.md** - Technical specifications

## Commands

### User Commands
- `/start` - Start bot instance
- `/stop` - Stop bot instance
- `/status` - Check status
- `/expiry` - View subscription
- `/help` - Show help

### Admin Commands
- `/grant @user days:30 emulator_index:0` - Grant access
- `/add_days @user days:15` - Extend subscription
- `/set_expiry @user date:2025-12-31` - Set expiry
- `/revoke @user` - Revoke access
- `/force_start @user` - Force start
- `/force_stop @user` - Force stop
- `/list_expiring days:7` - List expiring
- `/who` - Show running instances
- `/config current_channel add` - Allow channel
- `/logs limit:50` - View logs

## Web Dashboard

Access: http://127.0.0.1:5000

### Pages
- **Overview** - System stats & running instances
- **Users** - User management & subscriptions
- **Instances** - Monitor running bots
- **Config** - Guild/channel whitelists
- **Logs** - Audit trail

## Requirements

- Python 3.11+
- Discord Bot Token
- WhaleBots.exe running

## Dependencies

```
py-cord>=2.6.0,<3.0
Flask>=3.0.0,<4.0
python-dotenv>=1.0.0,<2.0
pytz>=2024.1
psutil>=5.9,<7
pywin32 (Windows only)
```

Install:
```bash
pip install -r requirements.txt
```

## Configuration

### Discord Bot Token
1. Go to https://discord.com/developers/applications
2. Create New Application
3. Bot → Reset Token → Copy
4. Enable Intents: Message Content, Server Members
5. OAuth2 → URL Generator → bot + applications.commands
6. Invite bot to server

### Admin User ID
1. Discord Settings → Advanced → Enable Developer Mode
2. Right-click your name → Copy ID
3. Add to `data/config.json` → `admin_users`

## Security Notes

⚠️ **Important:**
- Web dashboard has **NO authentication** - only use on localhost!
- Keep `.env` file secret (already in `.gitignore`)
- Don't expose to internet without adding authentication
- All Discord commands use ephemeral responses (private)

## Troubleshooting

### Bot won't start
- Check Discord Bot Token in `.env`
- Verify bot is invited to server
- Check intents enabled in Developer Portal

### "Unknown interaction" error
- Wait 1-2 minutes for command sync
- Restart Discord client
- Verify bot has "Use Slash Commands" permission

### Instance start fails
- Ensure WhaleBots.exe is running
- Check `WHALEBOTS_PATH` in `.env`
- Verify emulator_index < 20
- Check terminal logs for errors

### Dashboard error
- Check port 5000 not in use
- Verify Flask installed: `pip install Flask`
- Check logs in terminal

## Support

Run check script:
```bash
check_system.bat
```

View logs in terminal windows for debugging.

## License

For educational and research purposes.

---

**Ready to use!** Run `run.bat` to start. 🚀

