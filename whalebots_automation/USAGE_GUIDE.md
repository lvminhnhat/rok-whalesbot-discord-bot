# 🐋 WhaleBots Automation - Hướng Dẫn Sử Dụng

## 🚀 Cài Đặt Nhanh

```python
# Cài đặt dependencies (nếu cần)
pip install psutil pywin32  # Optional cho monitoring và UI automation

# Import thư viện
from whalebots_automation import create_whalesbot
```

## 📝 Cách Dùng Cơ Bản

### 1. Khởi tạo WhaleBots
```python
# Cách 1: Tự động detect path
from whalebots_automation import create_whalesbot

with create_whalesbot() as whalesbot:
    # Sử dụng whalesbot...
    pass

# Cách 2: Chỉ định path cụ thể
from whalebots_automation import WhaleBots

whalesbot = WhaleBots("C:/path/to/whalebots")
```

### 2. Kiểm tra trạng thái Emulator
```python
# Lấy danh sách tất cả emulators
states = whalesbot.get_emulator_states()
print(f"Tổng số emulator: {len(states)}")

# Lấy emulator đang chạy
active_emulators = whalesbot.get_active_emulators()
print(f"Emulator đang chạy: {len(active_emulators)}")

# Kiểm tra emulator cụ thể
is_running = whalesbot.is_active("MyEmulator1")
print(f"Emulator đang chạy: {is_running}")
```

### 3. Điều khiển Emulator
```python
# Khởi động emulator
whalesbot.start("MyEmulator1")  # Theo tên
whalesbot.start(0)             # Theo index

# Dừng emulator
whalesbot.stop("MyEmulator1")
whalesbot.stop(0)

# Kiểm tra emulator tồn tại
exists = whalesbot.check_status("MyEmulator1")
```

### 4. Lấy thông tin chi tiết
```python
# Lấy summary trạng thái
summary = whalesbot.get_state_summary()
print(summary)
# Output: "Tổng: 5 emulators | Đang chạy: 2 | Đã dừng: 3"

# Lấy thông tin emulator theo index
emulator_info = whalesbot.get_emulator_by_index(0)
print(emulator_info)

# Lấy thông tin theo tên
emulator_info = whalesbot.get_emulator_by_name("MyEmulator1")
```

## 🔧 Cấu Hình Tùy Chỉnh

```python
from whalebots_automation import WhaleBots, create_default_config

# Tạo config tùy chỉnh
config = create_default_config()
config.ui.step_size = 25           # Khoảng cách click
config.ui.click_delay = 0.1        # Delay giữa các click
config.files.enable_backups = True # Bật backup
config.debug_mode = True           # Debug mode

# Sử dụng với config
whalesbot = WhaleBots("C:/path/to/whalebots", config=config)
```

## 📊 Ví Dụ Hoàn Chỉnh

```python
#!/usr/bin/env python3
from whalebots_automation import create_whalesbot
from whalebots_automation.exceptions import WhaleBotsError

def main():
    try:
        # Khởi tạo WhaleBots
        with create_whalesbot() as whalesbot:

            # Hiển thị trạng thái hiện tại
            print("=== TRẠNG THÁI EMULATOR ===")
            states = whalesbot.get_emulator_states()
            for i, state in enumerate(states):
                status = "🟢 Đang chạy" if state['is_active'] else "🔴 Đã dừng"
                print(f"{i}: {state['name']} - {status}")

            # Điều khiển emulator
            print("\n=== ĐIỀU KHIỂN ===")

            # Khởi động emulator đầu tiên nếu đang dừng
            if states and not states[0]['is_active']:
                print(f"Khởi động: {states[0]['name']}")
                whalesbot.start(0)

            # Hiển thị summary
            summary = whalesbot.get_state_summary()
            print(f"\nTình trạng: {summary}")

    except WhaleBotsError as e:
        print(f"Lỗi WhaleBots: {e}")
    except Exception as e:
        print(f"Lỗi khác: {e}")

if __name__ == "__main__":
    main()
```

## 🔍 Kiểm Tra Process Đang Chạy

```python
# Detect emulator processes đang chạy
running_processes = whalesbot.detect_running_emulators()
for proc in running_processes:
    print(f"PID: {proc['process_info']['pid']} - {proc['process_info']['name']}")
```

## 🛡️ Error Handling

```python
from whalebots_automation.exceptions import (
    EmulatorNotFoundError,
    EmulatorAlreadyRunningError,
    WhaleBotsError
)

try:
    whalesbot.start("NonExistentEmulator")
except EmulatorNotFoundError:
    print("Không tìm thấy emulator!")
except EmulatorAlreadyRunningError:
    print("Emulator đã đang chạy!")
except WhaleBotsError as e:
    print(f"Lỗi: {e}")
```

## 📝 Tips Quan Trọng

- ✅ **Luôn dùng context manager** (`with create_whalesbot() as whalesbot:`)
- ✅ **Check trạng thái** trước khi điều khiển
- ✅ **Handle exceptions** properly
- ✅ **Use config object** cho custom settings
- ✅ **Monitor logs** để debug issues

## 🚀 Chạy Test

```bash
# Test thư viện
cd whalebots_automation
python tests.py

# Hoặc
python -m unittest tests -v
```

**Chúc bạn sử dụng thành công!** 🎉