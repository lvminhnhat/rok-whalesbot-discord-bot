# Discord Bot Commands Reference

## System Control

### Start System
```bash
run.bat                 # Start both Discord bot and Web dashboard
```

### Stop System
```bash
stop.bat               # Stop both bot and dashboard
```

### Check System
```bash
check_system.bat       # Verify system is ready
```

---

## User Commands (Discord)

### Basic Operations

**Start Bot Instance**
```
/start
```
Starts your bot instance if you have an active subscription.

**Stop Bot Instance**
```
/stop
```
Stops your currently running bot instance.

**Check Status**
```
/status
```
Shows your current bot status, uptime, and subscription info.

**View Subscription**
```
/expiry
```
Shows subscription start date, end date, and days remaining.

**Get Help**
```
/help
```
Shows command help and usage guide.

---

## Admin Commands (Discord)

### User Management

**Grant Subscription**
```
/grant @username days:30 emulator_index:0
```
- Grant 30 days to a user
- Assign them to emulator index 0
- Creates new user or extends existing

**Add Days**
```
/add_days @username days:15
```
Add 15 more days to user's subscription.

**Set Expiry Date**
```
/set_expiry @username date:2025-12-31
```
Set specific expiry date for user.

**Revoke Access**
```
/revoke @username
```
Revoke user's subscription and force stop their bot.

### Instance Control

**Force Start**
```
/force_start @username
```
Force start user's bot instance (bypasses cooldown).

**Force Stop**
```
/force_stop @username
```
Force stop user's bot instance.

### Monitoring

**List Expiring Users**
```
/list_expiring days:7
```
Show users expiring in next 7 days.

**Show Running Instances**
```
/who
```
List all currently running bot instances.

**View Audit Logs**
```
/logs limit:50
```
View last 50 audit log entries.

Filter by user:
```
/logs user:@username limit:50
```

### Configuration

**Add Current Channel to Whitelist**
```
/config current_channel add
```
Allow bot commands in the current channel.

**Remove Current Channel**
```
/config current_channel remove
```

**Add Current Guild**
```
/config current_guild add
```
Allow bot in current server/guild.

**Set Cooldown**
```
/config cooldown set 30
```
Set 30 second cooldown between start/stop commands.

**View Config**
```
/config current_channel view
```
View current channel whitelist.

---

## Web Dashboard

### Access
```
http://127.0.0.1:5000
```

### Pages

**Overview** - `/`
- System statistics
- Active instances count
- Expired/expiring users
- Quick actions

**Users** - `/users`
- User list with filters
- Start/Stop instances
- Add days to subscriptions
- Set expiry dates
- Revoke access

**Instances** - `/instances`
- Running instances monitor
- Uptime tracking
- Last heartbeat
- Force stop

**Config** - `/config`
- Manage allowed guilds
- Manage allowed channels
- Set cooldown
- Admin roles

**Logs** - `/logs`
- Audit trail
- Filter by user
- Search actions
- Pagination

---

## Quick Examples

### Setup New User
```
1. /grant @newuser days:30 emulator_index:0
2. User can now /start
3. Monitor in web dashboard
```

### Extend Subscription
```
/add_days @user days:30
```

### Allow Channel
```
/config current_channel add
```
(Run this command in the channel you want to allow)

### Monitor System
```
1. Open http://127.0.0.1:5000
2. Check Overview page
3. Click on Users to manage
```

### Emergency Stop
```
/force_stop @user
```

### Check Who's Running
```
/who
```

---

## Status Indicators

- `[RUNNING]` - Bot is active
- `[STOPPED]` - Bot is stopped
- `[EXPIRED]` - Subscription expired
- `[ERROR]` - Error state (needs attention)

---

## Tips

1. **All user commands are ephemeral** - Only the user sees the response
2. **Cooldown protection** - Users can't spam start/stop
3. **Auto-stop on expiry** - Bot automatically stops when subscription expires
4. **Real-time monitoring** - Web dashboard updates every 5-10 seconds
5. **Audit trail** - All actions are logged
6. **Channel restrictions** - Control where bot can be used

---

## Troubleshooting Commands

**If bot won't start:**
```
/status                      # Check subscription
/config current_channel add  # Ensure channel is allowed
```

**If instance stuck:**
```
/force_stop @user           # Force stop
/force_start @user          # Force start
```

**Check system health:**
```
/who                        # See all running
/list_expiring days:1       # Check expirations
```

---

**Need help?** Check `START_HERE.md` for full setup guide.

