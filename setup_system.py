"""
Script setup hệ thống WhaleBots Discord Bot + Web Dashboard
"""

import os
import json
from pathlib import Path


def create_directories():
    """Tạo các thư mục cần thiết"""
    print("📁 Tạo thư mục...")
    
    directories = [
        "data",
        "logs",
        "web_dashboard/static/css",
        "web_dashboard/static/js",
        "web_dashboard/templates"
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"  ✅ {directory}")


def create_config_json():
    """Tạo file config.json mặc định"""
    print("\n⚙️  Tạo config.json...")
    
    config_file = Path("data/config.json")
    
    if config_file.exists():
        print("  ⚠️  config.json đã tồn tại, bỏ qua")
        return
    
    default_config = {
        "allowed_guilds": [],
        "allowed_channels": [],
        "admin_roles": [],
        "admin_users": [],
        "cooldown_seconds": 60,
        "max_emulators": 20
    }
    
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(default_config, f, indent=2, ensure_ascii=False)
    
    print("  ✅ data/config.json đã được tạo")


def create_users_json():
    """Tạo file users.json rỗng"""
    print("\n👥 Tạo users.json...")
    
    users_file = Path("data/users.json")
    
    if users_file.exists():
        print("  ⚠️  users.json đã tồn tại, bỏ qua")
        return
    
    empty_users = {
        "users": {}
    }
    
    with open(users_file, 'w', encoding='utf-8') as f:
        json.dump(empty_users, f, indent=2, ensure_ascii=False)
    
    print("  ✅ data/users.json đã được tạo")


def create_logs_json():
    """Tạo file audit_logs.json rỗng"""
    print("\n📋 Tạo audit_logs.json...")
    
    logs_file = Path("data/audit_logs.json")
    
    if logs_file.exists():
        print("  ⚠️  audit_logs.json đã tồn tại, bỏ qua")
        return
    
    empty_logs = {
        "logs": []
    }
    
    with open(logs_file, 'w', encoding='utf-8') as f:
        json.dump(empty_logs, f, indent=2, ensure_ascii=False)
    
    print("  ✅ data/audit_logs.json đã được tạo")


def check_env_file():
    """Kiểm tra file .env"""
    print("\n🔑 Kiểm tra file .env...")
    
    env_file = Path(".env")
    
    if env_file.exists():
        print("  ✅ File .env đã tồn tại")
        return True
    else:
        print("  ❌ File .env chưa tồn tại!")
        print("\n  📝 Bạn cần tạo file .env với nội dung:")
        print("  " + "="*50)
        print("  DISCORD_BOT_TOKEN=your_discord_bot_token_here")
        print("  WHALEBOTS_PATH=C:\\Users\\DELL\\Downloads\\WhaleBots_1013")
        print("  FLASK_SECRET_KEY=your_random_secret_key_123456")
        print("  FLASK_PORT=5000")
        print("  FLASK_HOST=127.0.0.1")
        print("  FLASK_DEBUG=True")
        print("  " + "="*50)
        print("\n  💡 Copy từ env_example.txt và điền Discord Bot Token")
        return False


def add_admin_user():
    """Hướng dẫn thêm admin user"""
    print("\n👤 Thêm admin user...")
    
    config_file = Path("data/config.json")
    
    if not config_file.exists():
        print("  ⚠️  Chưa có config.json")
        return
    
    with open(config_file, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    if config.get('admin_users'):
        print(f"  ✅ Admin users đã có: {config['admin_users']}")
        return
    
    print("\n  📝 Cần thêm Discord User ID của bạn vào admin_users")
    print("  Cách lấy Discord User ID:")
    print("    1. Bật Developer Mode trong Discord (Settings > Advanced)")
    print("    2. Right-click vào tên của bạn → Copy ID")
    print("    3. Thêm ID vào data/config.json:")
    print('       "admin_users": ["YOUR_DISCORD_USER_ID"]')


def check_dependencies():
    """Kiểm tra dependencies"""
    print("\n📦 Kiểm tra dependencies...")
    
    missing = []
    
    try:
        import discord
        print("  ✅ discord (py-cord)")
    except ImportError:
        print("  ❌ discord (py-cord) chưa cài")
        missing.append("py-cord")
    
    try:
        import flask
        print("  ✅ Flask")
    except ImportError:
        print("  ❌ Flask chưa cài")
        missing.append("Flask")
    
    try:
        import dotenv
        print("  ✅ python-dotenv")
    except ImportError:
        print("  ❌ python-dotenv chưa cài")
        missing.append("python-dotenv")
    
    try:
        import pytz
        print("  ✅ pytz")
    except ImportError:
        print("  ❌ pytz chưa cài")
        missing.append("pytz")
    
    if missing:
        print(f"\n  ⚠️  Thiếu {len(missing)} packages")
        print("  Chạy: pip install -r requirements.txt")
        return False
    else:
        print("\n  ✅ Tất cả dependencies đã sẵn sàng!")
        return True


def main():
    """Main setup"""
    print("=" * 60)
    print("🚀 WhaleBots Discord Bot + Web Dashboard Setup")
    print("=" * 60)
    
    # Tạo directories
    create_directories()
    
    # Tạo JSON files
    create_config_json()
    create_users_json()
    create_logs_json()
    
    # Check .env
    has_env = check_env_file()
    
    # Add admin user
    add_admin_user()
    
    # Check dependencies
    has_deps = check_dependencies()
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 Kết quả Setup")
    print("=" * 60)
    
    if has_env and has_deps:
        print("✅ HỆ THỐNG SẴN SÀNG CHẠY!")
        print("\n📝 Các bước tiếp theo:")
        print("1. Thêm Discord User ID vào data/config.json (admin_users)")
        print("2. Chạy Discord bot:")
        print("   python run_bot.py")
        print("\n3. Chạy Web dashboard (terminal mới):")
        print("   python run_dashboard.py")
        print("\n4. Truy cập: http://127.0.0.1:5000")
    else:
        print("⚠️  CẦN HOÀN THÀNH CÁC BƯỚC SAU:")
        if not has_env:
            print("  - Tạo file .env với Discord Bot Token")
        if not has_deps:
            print("  - Cài đặt dependencies: pip install -r requirements.txt")
        print("\nSau đó chạy lại: python setup_system.py")
    
    print("=" * 60)


if __name__ == "__main__":
    main()

