"""
Test script for the UI Operation Queue System.

This script tests various aspects of the queue system to ensure it works correctly
before deployment to production.
"""

import asyncio
import sys
import os
import pytz
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from discord_bot.services.ui_operation_queue import (
    UIOperationQueue, OperationType, Priority, OperationStatus
)


class MockUser:
    """Mock user for testing."""
    def __init__(self, user_id: str, name: str, emulator_index: int):
        self.user_id = user_id
        self.name = name
        self.emulator_index = emulator_index


class TestQueueSystem:
    """Test suite for the queue system."""

    def __init__(self):
        self.queue = UIOperationQueue(max_concurrent_operations=2)
        self.test_results = []

    async def test_basic_queue_operations(self):
        """Test basic queue operations."""
        print("Testing basic queue operations...")

        # Test adding operations
        op1_id = await self.queue.add_operation(
            operation_type=OperationType.START,
            user_id="123",
            user_name="User1",
            emulator_index=0,
            priority=Priority.NORMAL,
            callback=self._mock_callback("Start Op 1")
        )

        op2_id = await self.queue.add_operation(
            operation_type=OperationType.STOP,
            user_id="456",
            user_name="User2",
            emulator_index=1,
            priority=Priority.HIGH,
            callback=self._mock_callback("Stop Op 2")
        )

        # Test queue info
        queue_info = self.queue.get_queue_info()
        assert queue_info['pending_operations'] == 2, "Should have 2 pending operations"

        # Test operation status
        status1 = self.queue.get_operation_status(op1_id)
        assert status1 is not None, "Operation 1 should exist"
        assert status1['status'] == OperationStatus.PENDING.value, "Should be pending"

        print("PASS: Basic queue operations test passed")

    async def test_priority_ordering(self):
        """Test priority-based ordering."""
        print("Testing priority ordering...")

        # Add operations with different priorities
        normal_ops = []
        high_ops = []
        critical_ops = []

        # Add normal priority operations
        for i in range(3):
            op_id = await self.queue.add_operation(
                operation_type=OperationType.START,
                user_id=f"user_{i}",
                user_name=f"User{i}",
                emulator_index=i,
                priority=Priority.NORMAL,
                callback=self._mock_callback(f"Normal Op {i}")
            )
            normal_ops.append(op_id)

        # Add high priority operation
        high_op_id = await self.queue.add_operation(
            operation_type=OperationType.STOP,
            user_id="admin",
            user_name="AdminUser",
            emulator_index=0,
            priority=Priority.HIGH,
            callback=self._mock_callback("High Priority Op")
        )
        high_ops.append(high_op_id)

        # Add critical priority operation
        critical_op_id = await self.queue.add_operation(
            operation_type=OperationType.STOP,
            user_id="superadmin",
            user_name="SuperAdmin",
            emulator_index=1,
            priority=Priority.CRITICAL,
            callback=self._mock_callback("Critical Priority Op")
        )
        critical_ops.append(critical_op_id)

        # Get pending operations and check order
        pending_ops = self.queue.get_pending_operations(limit=10)

        # Critical should be first, high should be second
        assert pending_ops[0]['operation_id'] == critical_op_id, "Critical operation should be first"
        assert pending_ops[1]['operation_id'] == high_op_id, "High priority operation should be second"

        print("PASS: Priority ordering test passed")

    async def test_concurrent_operations(self):
        """Test concurrent operation handling."""
        print("Testing concurrent operations...")

        # Add more operations than max_concurrent
        operation_ids = []
        for i in range(5):
            op_id = await self.queue.add_operation(
                operation_type=OperationType.START,
                user_id=f"user_concurrent_{i}",
                user_name=f"ConcurrentUser{i}",
                emulator_index=i,
                priority=Priority.NORMAL,
                timeout=2,
                callback=self._slow_mock_callback(f"Concurrent Op {i}", delay=1)
            )
            operation_ids.append(op_id)

        # Wait for all operations to complete
        await asyncio.sleep(8)

        # Check that all operations completed
        completed_count = 0
        for op_id in operation_ids:
            result = await self.queue.wait_for_operation(op_id, timeout=5)
            if result and result.status == OperationStatus.COMPLETED:
                completed_count += 1

        assert completed_count == 5, f"Expected 5 completed operations, got {completed_count}"

        print("PASS: Concurrent operations test passed")

    async def test_timeout_handling(self):
        """Test operation timeout handling."""
        print("Testing timeout handling...")

        # Add operation that will timeout
        timeout_op_id = await self.queue.add_operation(
            operation_type=OperationType.START,
            user_id="timeout_user",
            user_name="TimeoutUser",
            emulator_index=0,
            priority=Priority.NORMAL,
            timeout=2,
            callback=self._slow_mock_callback("Timeout Op", delay=5)  # Takes longer than timeout
        )

        # Wait for operation to timeout
        result = await self.queue.wait_for_operation(timeout_op_id, timeout=10)

        assert result is not None, "Should get a result"
        assert result.status == OperationStatus.TIMEOUT, "Should have timed out"

        print("PASS: Timeout handling test passed")

    async def test_operation_cancellation(self):
        """Test operation cancellation."""
        print("Testing operation cancellation...")

        # Add operation
        cancel_op_id = await self.queue.add_operation(
            operation_type=OperationType.START,
            user_id="cancel_user",
            user_name="CancelUser",
            emulator_index=0,
            priority=Priority.NORMAL,
            callback=self._slow_mock_callback("Cancel Op", delay=5)
        )

        # Cancel operation
        cancelled = self.queue.cancel_operation(cancel_op_id)
        assert cancelled, "Operation should be cancellable"

        # Check operation status
        status = self.queue.get_operation_status(cancel_op_id)
        assert status['status'] == OperationStatus.CANCELLED.value, "Should be cancelled"

        print("PASS: Operation cancellation test passed")

    async def test_statistics_tracking(self):
        """Test statistics tracking."""
        print("Testing statistics tracking...")

        # Get initial stats
        initial_stats = self.queue.get_queue_info()['statistics']

        # Add and complete several operations
        for i in range(3):
            await self.queue.add_operation(
                operation_type=OperationType.START,
                user_id=f"stats_user_{i}",
                user_name=f"StatsUser{i}",
                emulator_index=i,
                priority=Priority.NORMAL,
                callback=self._mock_callback(f"Stats Op {i}")
            )

        # Wait for operations to complete
        await asyncio.sleep(5)

        # Check updated stats
        final_stats = self.queue.get_queue_info()['statistics']

        assert final_stats['total_operations'] > initial_stats['total_operations'], "Total operations should increase"
        assert final_stats['completed_operations'] > initial_stats['completed_operations'], "Completed operations should increase"

        print("PASS: Statistics tracking test passed")

    async def test_cleanup_functionality(self):
        """Test cleanup of old operations."""
        print("Testing cleanup functionality...")

        # Add some operations
        old_ops = []
        for i in range(3):
            op_id = await self.queue.add_operation(
                operation_type=OperationType.START,
                user_id=f"cleanup_user_{i}",
                user_name=f"CleanupUser{i}",
                emulator_index=i,
                priority=Priority.NORMAL,
                callback=self._mock_callback(f"Cleanup Op {i}")
            )
            old_ops.append(op_id)

        # Wait for operations to complete
        await asyncio.sleep(5)

        # Manually set old timestamps for testing (with timezone)
        import pytz
        old_time = datetime.now(pytz.UTC) - timedelta(hours=25)
        with self.queue._lock:
            for op_id in old_ops:
                if op_id in self.queue._operations:
                    self.queue._operations[op_id].timestamp = old_time

        # Run cleanup
        cleaned_count = self.queue.cleanup_old_operations(hours=24)
        assert cleaned_count >= 3, f"Should clean up at least 3 operations, cleaned {cleaned_count}"

        print("PASS: Cleanup functionality test passed")

    async def test_queue_positions(self):
        """Test queue position calculations."""
        print("Testing queue position calculations...")

        # Add operations and check positions
        operation_ids = []
        for i in range(5):
            op_id = await self.queue.add_operation(
                operation_type=OperationType.START,
                user_id=f"position_user_{i}",
                user_name=f"PositionUser{i}",
                emulator_index=i,
                priority=Priority.NORMAL,
                callback=self._mock_callback(f"Position Op {i}")
            )
            operation_ids.append(op_id)

        # Check positions
        for i, op_id in enumerate(operation_ids):
            status = self.queue.get_operation_status(op_id)
            expected_position = i + 1
            assert status['queue_position'] == expected_position, f"Operation {i} should be at position {expected_position}"

        print("PASS: Queue position calculations test passed")

    def _mock_callback(self, operation_name: str):
        """Create a mock callback that completes quickly."""
        async def callback():
            await asyncio.sleep(0.1)  # Small delay
            return {
                'success': True,
                'message': f'{operation_name} completed successfully',
                'operation_name': operation_name
            }
        return callback

    def _slow_mock_callback(self, operation_name: str, delay: float):
        """Create a mock callback that takes time to complete."""
        async def callback():
            await asyncio.sleep(delay)
            return {
                'success': True,
                'message': f'{operation_name} completed successfully',
                'operation_name': operation_name
            }
        return callback

    async def run_all_tests(self):
        """Run all tests."""
        print("Starting Queue System Tests\n")

        # Start queue processor
        await self.queue.start_processor()

        try:
            # Run all tests
            await self.test_basic_queue_operations()
            await asyncio.sleep(1)

            await self.test_priority_ordering()
            await asyncio.sleep(1)

            await self.test_concurrent_operations()
            await asyncio.sleep(1)

            await self.test_timeout_handling()
            await asyncio.sleep(1)

            await self.test_operation_cancellation()
            await asyncio.sleep(1)

            await self.test_statistics_tracking()
            await asyncio.sleep(1)

            await self.test_cleanup_functionality()
            await asyncio.sleep(1)

            await self.test_queue_positions()
            await asyncio.sleep(1)

            print("\nAll tests passed successfully!")

            # Show final statistics
            final_stats = self.queue.get_queue_info()['statistics']
            print(f"\nFinal Statistics:")
            print(f"   Total Operations: {final_stats['total_operations']}")
            print(f"   Completed: {final_stats['completed_operations']}")
            print(f"   Failed: {final_stats['failed_operations']}")
            print(f"   Timeout: {final_stats['timeout_operations']}")
            print(f"   Avg Wait Time: {final_stats['average_wait_time']:.2f}s")
            print(f"   Avg Execution Time: {final_stats['average_execution_time']:.2f}s")

        except Exception as e:
            print(f"\nTest failed: {e}")
            import traceback
            traceback.print_exc()

        finally:
            # Clean up
            await self.queue.stop_processor()


async def main():
    """Main test runner."""
    print("UI Operation Queue System Test Suite")
    print("=" * 50)

    tester = TestQueueSystem()
    await tester.run_all_tests()


if __name__ == "__main__":
    # Run tests
    asyncio.run(main())