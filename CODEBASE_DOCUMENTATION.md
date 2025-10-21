# WhaleBots Codebase Documentation

## Tổng quan

WhaleBots là một nền tảng bot game cung cấp giải pháp tự động hóa cho các game mobile, chủ yếu là:
- Rise of Kingdoms Bot (ROKBot.exe)
- Call of Dragons Bot

Nền tảng được xây dựng với các executable đã biên dịch (.exe) và dynamic link libraries (.dll) để giao tiếp với Android emulator và tự động hóa gameplay.

## Kiến trúc hệ thống

### Cấu trúc thư mục

```
WhaleBots_1013/
├── data/                           # Thư mục dữ liệu
├── discord_bot/                    # Discord bot module
│   ├── commands/                   # Lệnh Discord
│   │   ├── admin_commands.py       # Lệnh admin
│   │   └── user_commands.py        # Lệnh người dùng
│   ├── services/                   # Service layer
│   │   ├── bot_service.py          # Bot management service
│   │   └── subscription_service.py # Subscription management
│   └── utils/                      # Utilities
│       ├── permissions.py          # Permission checking
│       └── validators.py           # Input validation
├── openspec/                       # OpenSpec specifications
├── shared/                         # Shared components
│   ├── constants.py                # Constants và enums
│   ├── data_manager.py             # Data management
│   └── models.py                   # Data models
├── web_dashboard/                  # Web dashboard
│   ├── routes/                     # Flask routes
│   ├── static/                     # Static assets
│   └── templates/                  # HTML templates
└── whalebots_automation/           # Core automation
    ├── core/                       # Core functionality
    │   ├── emulator_action.py      # Emulator control
    │   ├── state.py                # State management
    │   └── emulater_action.py      # Legacy emulator control
    ├── services/                   # Automation services
    └── config.py                   # Configuration management
```

### Các thành phần chính

#### 1. Discord Bot (`discord_bot/`)

**Main class: `WhaleBotDiscord`** (`discord_bot/bot.py:21`)
- Kế thừa từ `discord.Bot`
- Quản lý các lệnh slash commands cho người dùng và admin
- Chạy background tasks để monitoring heartbeat và expiry
- Tích hợp với WhaleBots automation core

**Commands:**
- **User Commands** (`discord_bot/commands/user_commands.py`):
  - `/start` - Khởi động bot instance
  - `/stop` - Dừng bot instance
  - `/status` - Kiểm tra trạng thái
  - `/expiry` - Xem thông tin subscription
  - `/link` - Liên kết account với emulator
  - `/unlink` - Hủy liên kết
  - `/list_emulators` - Xem danh sách emulator
  - `/help` - Trợ giúp

- **Admin Commands** (`discord_bot/commands/admin_commands.py`):
  - `/grant` - Cấp quyền sử dụng
  - `/add_days` - Thêm ngày sử dụng
  - `/set_expiry` - Đặt ngày hết hạn
  - `/revoke` - Thu hồi quyền
  - `/force_start` - Bắt đầu bot thay user
  - `/force_stop` - Dừng bot thay user
  - `/list_expiring` - Liệt kê user sắp hết hạn
  - `/who` - Xem danh sách đang chạy
  - `/config` - Cấu hình bot
  - `/logs` - Xem audit logs

#### 2. Bot Service (`discord_bot/services/bot_service.py`)

**Class: `BotService`** (`discord_bot/services/bot_service.py:20`)
- Interface giữa Discord bot và WhaleBots automation
- Quản lý lifecycle của bot instances (start/stop/status)
- Xử lý liên kết giữa user và emulator
- Validation và error handling

**Methods chính:**
- `start_instance(user_id)` - Khởi động bot cho user
- `stop_instance(user_id)` - Dừng bot của user
- `get_status(user_id)` - Lấy trạng thái bot
- `link_user_to_emulator()` - Liên kết user-emulator
- `validate_user_emulators()` - Validate các liên kết

#### 3. Data Management (`shared/`)

**Class: `DataManager`** (`shared/data_manager.py:20`)
- Thread-safe JSON data manager
- Quản lý users, configuration, audit logs
- Cung cấp operations CRUD với locking

**Data Models** (`shared/models.py`):
- `User` - Thông tin user và bot instance mapping
- `Subscription` - Thông tin subscription
- `BotConfig` - Cấu hình bot
- `AuditLog` - Audit trail entries

#### 4. WhaleBots Automation Core (`whalebots_automation/`)

**Class: `WhaleBots`** (`whalebots_automation/whalesbot.py:165`)
- Main class cho managing WhaleBots gaming automation platform
- Cung cấp interface cho emulator detection, state management, process monitoring
- UI automation với proper error handling và security validation

**Core Components:**

- **Emulator State Management** (`whalebots_automation/core/state.py`):
  - `EmulatorStateManager` - Quản lý state của emulator
  - Cache optimization và comprehensive error handling
  - Support cho multiple emulator instances

- **Window Control** (`whalebots_automation/core/emulator_action.py`):
  - `WindowController` - Main window controller với SOLID design
  - `HybridClickHandler` - Click với message-based fallback
  - `MouseScrollHandler` - Scroll functionality
  - Security validation cho coordinates

- **Configuration Management** (`whalebots_automation/config.py`):
  - `WhaleBotsConfiguration` - Main configuration class
  - Modular config components (UI, Security, Process, File, Logging)
  - Validation và default values

#### 5. Web Dashboard (`web_dashboard/`)

Flask-based web interface cho:
- User management
- Configuration
- Logs viewing
- Real-time status monitoring

**Routes:**
- `/` - Overview dashboard
- `/users` - User management
- `/config` - Bot configuration
- `/logs` - Audit logs
- `/instances` - Instance management

## Quy trình hoạt động

### 1. User Onboarding
1. Admin grants access via `/grant` command
2. User links to emulator via `/link <emulator_name>`
3. System validates emulator availability
4. User can start bot via `/start` command

### 2. Bot Lifecycle Management
1. **Start**:
   - Validate subscription và user permissions
   - Check emulator availability
   - Start emulator qua WhaleBots automation
   - Update user status và heartbeat

2. **Monitoring**:
   - Background heartbeat checker (5 minutes interval)
   - Expiry checker (1 hour interval)
   - Emulator validator (10 minutes interval)

3. **Stop**:
   - Stop emulator automation
   - Update user status
   - Calculate uptime statistics

### 3. State Management
- Thread-safe JSON operations với file locking
- Real-time status updates
- Audit logging cho所有 actions
- Backup và recovery mechanisms

## Dependencies

### Core Dependencies
- **discord.py** - Discord bot framework
- **Flask** - Web dashboard framework
- **pywin32** - Windows API access cho emulator control
- **pytz** - Timezone handling
- **dataclasses** - Data model definitions

### External Dependencies
- **WhaleBots.exe** - Main launcher application
- **WhaleBots.dll** - Core bot engine library
- Android emulators (BlueStacks, Nox, etc.)

## Security Features

### Permission System
- Role-based access control (Admin vs User)
- Channel/guild restrictions
- Cooldown mechanisms để prevent abuse

### Data Protection
- Thread-safe file operations
- Input validation cho tất cả user inputs
- Secure coordinate validation cho UI automation
- Audit trail cho tất cả administrative actions

### Error Handling
- Comprehensive exception handling
- Graceful degradation khi components fail
- Resource cleanup on shutdown
- Logging với security filtering

## Configuration

### Automated Setup
- Run `python setup_system.py` to create the `.venv` virtual environment, install dependencies, and scaffold required data files.
- The script copies `.env` from `env_example.txt` if needed and reminds operators to add their Discord admin ID.
- All generated JSON files use UTF-8 encoding and `ensure_ascii=False` so multilingual values (Chinese, Korean, Japanese, etc.) are preserved.
- Configuration loaders fall back to UTF-8-SIG/UTF-16 encodings automatically when reading existing files, keeping multilingual names intact.

### Environment Variables
```bash
DISCORD_BOT_TOKEN=your_bot_token
WHALEBOTS_PATH=path/to/whalebots/installation
DATA_DIR=./data
```

### Configuration Files
- `data/config.json` - Bot configuration
- `data/users.json` - User data và subscriptions
- `data/audit_logs.json` - Audit trail

### Bot Configuration
```json
{
  "allowed_guilds": ["guild_id1", "guild_id2"],
  "admin_channels": ["channel_id1"],
  "user_channels": ["channel_id2"],
  "cooldown_seconds": 5
}
```

## Monitoring và Maintenance

### Background Tasks
1. **Heartbeat Checker** - Monitor bot health
2. **Expiry Checker** - Handle subscription expiration
3. **Emulator Validator** - Validate emulator states
4. **Process Monitor** - Monitor running processes

### Logging
- Structured logging với levels
- Performance logging với decorators
- Security-aware message filtering
- File-based log rotation

### Metrics
- User activity tracking
- Bot uptime statistics
- Error rate monitoring
- Resource usage tracking

## Development Notes

### Design Patterns
- **Service Layer Pattern** - Separation of business logic
- **Repository Pattern** - Data access abstraction
- **Factory Pattern** - Component creation
- **Observer Pattern** - Event handling
- **Strategy Pattern** - Different control mechanisms

### Best Practices
- SOLID principles implementation
- Comprehensive error handling
- Thread safety cho concurrent operations
- Modular architecture với clear interfaces
- Extensive logging và monitoring

### Testing
- Unit tests cho core components
- Integration tests cho service layer
- Mock dependencies cho reliable testing
- Performance testing cho UI automation

## Troubleshooting

### Common Issues
1. **Emulator not found** - Check WhaleBots installation path
2. **Permission denied** - Verify Discord permissions
3. **Stale heartbeat** - Check bot connectivity
4. **Configuration errors** - Validate JSON syntax

### Debug Tools
- `/logs` command cho audit trail
- `/who` command cho instance status
- Web dashboard cho visual monitoring
- Log files trong data directory

## Future Enhancements

### Planned Features
- Multi-game support expansion
- Advanced scheduling system
- Performance analytics dashboard
- Mobile companion app
- API cho third-party integrations

### Technical Improvements
- Database migration từ JSON to SQL
- Redis caching cho performance
- Microservices architecture
- Container deployment support
- Advanced security features