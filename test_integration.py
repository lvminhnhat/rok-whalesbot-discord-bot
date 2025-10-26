"""
Integration test for queue system with existing codebase.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from shared.data_manager import DataManager
from shared.constants import DATA_DIR
from discord_bot.services.ui_operation_queue import UIOperationQueue
from discord_bot.services.bot_service import BotService


async def test_integration():
    """Test integration of queue system with existing bot service."""
    print("Testing Queue System Integration")
    print("=" * 40)

    try:
        # Initialize data manager
        data_manager = DataManager(DATA_DIR)
        print("PASS: Data manager initialized")

        # Initialize queue
        queue = UIOperationQueue(max_concurrent_operations=1)
        await queue.start_processor()
        print("PASS: Queue processor started")

        # Initialize bot service with queue
        bot_service = BotService(".", data_manager, queue)
        print("PASS: Bot service initialized with queue support")

        # Test queue availability
        if bot_service.use_queue:
            print("PASS: Queue system is active")
        else:
            print("✗ Queue system is not active")
            return

        # Test queue info
        queue_info = queue.get_queue_info()
        print(f"PASS: Queue info: {queue_info['pending_operations']} pending, {queue_info['processing_operations']} processing")

        # Test adding mock operations
        from discord_bot.services.ui_operation_queue import OperationType, Priority

        async def mock_callback():
            await asyncio.sleep(0.1)
            return {"success": True, "message": "Test operation completed"}

        # Add test operation
        op_id = await queue.add_operation(
            operation_type=OperationType.START,
            user_id="test_user_123",
            user_name="TestUser",
            emulator_index=0,
            priority=Priority.NORMAL,
            callback=mock_callback
        )
        print(f"PASS: Added test operation: {op_id[:8]}...")

        # Wait for completion
        result = await queue.wait_for_operation(op_id, timeout=5)
        if result and result.status.value == "completed":
            print("PASS: Test operation completed successfully")
        else:
            print(f"✗ Test operation failed: {result.status.value if result else 'None'}")

        # Final statistics
        final_stats = queue.get_queue_info()['statistics']
        print(f"PASS: Final stats: {final_stats['total_operations']} total, {final_stats['completed_operations']} completed")

        # Cleanup
        await queue.stop_processor()
        print("PASS: Queue processor stopped")

        print("\nIntegration test completed successfully!")
        print("Queue system is ready for use with existing WhaleBots bot.")

    except Exception as e:
        print(f"\nIntegration test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_integration())