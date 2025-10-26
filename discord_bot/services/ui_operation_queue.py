"""
UI Operation Queue System for WhaleBots

This module provides a queued system for handling UI operations to prevent
conflicts when multiple users try to control the GUI simultaneously.
"""

import asyncio
import threading
import uuid
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, Callable, Optional, List
import pytz

from shared.constants import InstanceStatus


class OperationType(Enum):
    """Types of UI operations."""
    START = "start"
    STOP = "stop"
    STATUS_CHECK = "status"
    VALIDATE = "validate"
    RESTART = "restart"


class Priority(Enum):
    """Priority levels for operations."""
    CRITICAL = 1    # Emergency operations
    HIGH = 2        # Admin operations
    NORMAL = 3      # User operations
    LOW = 4         # Background tasks


class OperationStatus(Enum):
    """Status of an operation."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class UIOperation:
    """Represents a UI operation in the queue."""
    operation_type: OperationType
    user_id: str
    user_name: str
    emulator_index: int
    priority: Priority
    timestamp: datetime
    timeout: int = 30
    operation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: OperationStatus = OperationStatus.PENDING
    callback: Optional[Callable] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Set timezone for timestamp if not already set."""
        if self.timestamp.tzinfo is None:
            self.timestamp = pytz.UTC.localize(self.timestamp)


@dataclass
class OperationResult:
    """Result of an operation."""
    operation_id: str
    status: OperationStatus
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    execution_time: Optional[float] = None


class UIOperationQueue:
    """
    Thread-safe queue for managing UI operations.

    This class handles queuing and processing of UI operations to prevent
    conflicts when multiple users try to control the GUI simultaneously.
    """

    def __init__(self, max_concurrent_operations: int = 1):
        """
        Initialize the UI operation queue.

        Args:
            max_concurrent_operations: Maximum number of concurrent operations
        """
        self._queue = asyncio.PriorityQueue()
        self._operations: Dict[str, UIOperation] = {}
        self._results: Dict[str, OperationResult] = {}
        self._processing_operations: Dict[str, datetime] = {}

        self._max_concurrent = max_concurrent_operations
        self._is_processing = False
        self._processor_task = None
        self._lock = threading.Lock()

        # Statistics
        self._stats = {
            'total_operations': 0,
            'completed_operations': 0,
            'failed_operations': 0,
            'timeout_operations': 0,
            'average_wait_time': 0.0,
            'average_execution_time': 0.0
        }

        self.logger = self._get_logger()

    def _get_logger(self):
        """Get logger instance."""
        import logging
        return logging.getLogger(f"{__name__}.UIOperationQueue")

    async def add_operation(
        self,
        operation_type: OperationType,
        user_id: str,
        user_name: str,
        emulator_index: int,
        priority: Priority = Priority.NORMAL,
        timeout: int = 30,
        callback: Optional[Callable] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Add an operation to the queue.

        Args:
            operation_type: Type of operation
            user_id: Discord user ID
            user_name: Discord user name
            emulator_index: Index of emulator
            priority: Priority level
            timeout: Operation timeout in seconds
            callback: Async callback function to execute
            metadata: Additional metadata

        Returns:
            Operation ID
        """
        operation = UIOperation(
            operation_type=operation_type,
            user_id=user_id,
            user_name=user_name,
            emulator_index=emulator_index,
            priority=priority,
            timestamp=datetime.now(pytz.UTC),
            timeout=timeout,
            callback=callback,
            metadata=metadata or {}
        )

        # Store operation
        with self._lock:
            self._operations[operation.operation_id] = operation
            self._stats['total_operations'] += 1

        # Add to priority queue
        priority_value = (priority.value, operation.timestamp.timestamp())
        await self._queue.put((priority_value, operation.operation_id))

        self.logger.info(
            f"Added operation {operation.operation_id} to queue: "
            f"{operation_type.value} for user {user_name} (emulator {emulator_index})"
        )

        # Start processor if not running
        if not self._is_processing:
            await self.start_processor()

        return operation.operation_id

    async def start_processor(self) -> None:
        """Start the queue processor task."""
        if self._processor_task is None or self._processor_task.done():
            self._is_processing = True
            self._processor_task = asyncio.create_task(self._process_queue())
            self.logger.info("Queue processor started")

    async def stop_processor(self) -> None:
        """Stop the queue processor task."""
        if self._processor_task and not self._processor_task.done():
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
            self._is_processing = False
            self.logger.info("Queue processor stopped")

    async def _process_queue(self) -> None:
        """Process operations from the queue."""
        self.logger.info("Starting queue processor")

        while True:
            try:
                # Wait for an operation
                priority_value, operation_id = await self._queue.get()

                # Check if operation was cancelled
                operation = self._operations.get(operation_id)
                if not operation or operation.status == OperationStatus.CANCELLED:
                    self._queue.task_done()
                    continue

                # Check concurrent operation limit
                while len(self._processing_operations) >= self._max_concurrent:
                    await asyncio.sleep(0.1)
                    # Clean up timed out operations
                    await self._cleanup_timed_out_operations()

                # Process operation
                asyncio.create_task(self._execute_operation(operation_id))
                self._queue.task_done()

            except asyncio.CancelledError:
                self.logger.info("Queue processor cancelled")
                break
            except Exception as e:
                self.logger.error(f"Error in queue processor: {e}")
                await asyncio.sleep(1)

    async def _execute_operation(self, operation_id: str) -> None:
        """
        Execute a single operation.

        Args:
            operation_id: ID of operation to execute
        """
        operation = self._operations.get(operation_id)
        if not operation:
            return

        # Mark as processing
        with self._lock:
            operation.status = OperationStatus.PROCESSING
            self._processing_operations[operation_id] = datetime.now(pytz.UTC)

        # Create result
        result = OperationResult(
            operation_id=operation_id,
            status=OperationStatus.PROCESSING,
            started_at=datetime.now(pytz.UTC)
        )

        self.logger.info(
            f"Executing operation {operation_id}: {operation.operation_type.value} "
            f"for user {operation.user_name} (emulator {operation.emulator_index})"
        )

        try:
            # Execute callback with timeout
            if operation.callback:
                execution_result = await asyncio.wait_for(
                    operation.callback(),
                    timeout=operation.timeout
                )

                result.result = execution_result
                result.status = OperationStatus.COMPLETED

                with self._lock:
                    self._stats['completed_operations'] += 1

                self.logger.info(
                    f"Operation {operation_id} completed successfully"
                )
            else:
                raise ValueError("No callback provided for operation")

        except asyncio.TimeoutError:
            result.status = OperationStatus.TIMEOUT
            result.error = f"Operation timed out after {operation.timeout} seconds"

            with self._lock:
                self._stats['timeout_operations'] += 1

            self.logger.warning(
                f"Operation {operation_id} timed out after {operation.timeout} seconds"
            )

        except Exception as e:
            result.status = OperationStatus.FAILED
            result.error = str(e)

            with self._lock:
                self._stats['failed_operations'] += 1

            self.logger.error(
                f"Operation {operation_id} failed: {e}"
            )

        finally:
            # Complete operation
            result.completed_at = datetime.now(pytz.UTC)
            if result.started_at:
                result.execution_time = (result.completed_at - result.started_at).total_seconds()

            with self._lock:
                operation.status = result.status
                self._results[operation_id] = result
                self._processing_operations.pop(operation_id, None)

                # Update statistics
                self._update_statistics(result)

    async def _cleanup_timed_out_operations(self) -> None:
        """Clean up operations that have been processing too long."""
        now = datetime.now(pytz.UTC)
        timed_out = []

        with self._lock:
            for operation_id, start_time in self._processing_operations.items():
                operation = self._operations.get(operation_id)
                if operation and (now - start_time).total_seconds() > operation.timeout * 2:
                    timed_out.append(operation_id)

        for operation_id in timed_out:
            operation = self._operations.get(operation_id)
            if operation:
                # Create timeout result
                result = OperationResult(
                    operation_id=operation_id,
                    status=OperationStatus.TIMEOUT,
                    error="Operation timed out during processing",
                    started_at=self._processing_operations.get(operation_id),
                    completed_at=now
                )

                with self._lock:
                    operation.status = OperationStatus.TIMEOUT
                    self._results[operation_id] = result
                    self._processing_operations.pop(operation_id, None)
                    self._stats['timeout_operations'] += 1

                self.logger.warning(f"Cleaned up timed out operation {operation_id}")

    def _update_statistics(self, result: OperationResult) -> None:
        """Update operation statistics."""
        if result.execution_time:
            completed = self._stats['completed_operations']
            current_avg = self._stats['average_execution_time']
            self._stats['average_execution_time'] = (
                (current_avg * (completed - 1) + result.execution_time) / completed
            )

    async def wait_for_operation(
        self,
        operation_id: str,
        timeout: Optional[int] = None
    ) -> Optional[OperationResult]:
        """
        Wait for an operation to complete.

        Args:
            operation_id: ID of operation to wait for
            timeout: Maximum time to wait (uses operation timeout if None)

        Returns:
            Operation result or None if timeout
        """
        operation = self._operations.get(operation_id)
        if not operation:
            return None

        if timeout is None:
            timeout = operation.timeout

        start_time = datetime.now(pytz.UTC)

        while (datetime.now(pytz.UTC) - start_time).total_seconds() < timeout:
            # Check if operation is complete
            with self._lock:
                if operation_id in self._results:
                    return self._results[operation_id]

            await asyncio.sleep(0.1)

        return None

    def cancel_operation(self, operation_id: str) -> bool:
        """
        Cancel a pending operation.

        Args:
            operation_id: ID of operation to cancel

        Returns:
            True if operation was cancelled, False if not found or already processing
        """
        with self._lock:
            operation = self._operations.get(operation_id)
            if operation and operation.status == OperationStatus.PENDING:
                operation.status = OperationStatus.CANCELLED

                # Create cancelled result
                result = OperationResult(
                    operation_id=operation_id,
                    status=OperationStatus.CANCELLED,
                    completed_at=datetime.now(pytz.UTC)
                )
                self._results[operation_id] = result

                self.logger.info(f"Cancelled operation {operation_id}")
                return True

        return False

    def get_operation_status(self, operation_id: str) -> Optional[Dict[str, Any]]:
        """
        Get status of an operation.

        Args:
            operation_id: ID of operation

        Returns:
            Operation status info or None if not found
        """
        with self._lock:
            operation = self._operations.get(operation_id)
            if not operation:
                return None

            result = self._results.get(operation_id)
            queue_position = self._get_queue_position(operation_id)

            return {
                'operation_id': operation_id,
                'operation_type': operation.operation_type.value,
                'user_name': operation.user_name,
                'emulator_index': operation.emulator_index,
                'priority': operation.priority.value,
                'status': operation.status.value,
                'timestamp': operation.timestamp.isoformat(),
                'queue_position': queue_position,
                'result': result.__dict__ if result else None
            }

    def _get_queue_position(self, operation_id: str) -> int:
        """Get position of operation in queue."""
        position = 0
        operation = self._operations.get(operation_id)

        if not operation or operation.status != OperationStatus.PENDING:
            return -1

        # Count pending operations with higher priority or earlier timestamp
        for op_id, op in self._operations.items():
            if (op.status == OperationStatus.PENDING and
                op_id != operation_id and
                (op.priority.value < operation.priority.value or
                 (op.priority.value == operation.priority.value and
                  op.timestamp < operation.timestamp))):
                position += 1

        return position + 1

    def get_queue_info(self) -> Dict[str, Any]:
        """
        Get information about the queue.

        Returns:
            Queue information
        """
        with self._lock:
            pending_count = sum(1 for op in self._operations.values()
                              if op.status == OperationStatus.PENDING)
            processing_count = len(self._processing_operations)

            return {
                'is_processing': self._is_processing,
                'pending_operations': pending_count,
                'processing_operations': processing_count,
                'max_concurrent': self._max_concurrent,
                'statistics': self._stats.copy(),
                'queue_size': self._queue.qsize()
            }

    def get_pending_operations(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get list of pending operations.

        Args:
            limit: Maximum number of operations to return

        Returns:
            List of pending operations
        """
        pending_ops = []

        with self._lock:
            for operation in self._operations.values():
                if operation.status == OperationStatus.PENDING:
                    queue_pos = self._get_queue_position(operation.operation_id)
                    pending_ops.append({
                        'operation_id': operation.operation_id,
                        'operation_type': operation.operation_type.value,
                        'user_name': operation.user_name,
                        'emulator_index': operation.emulator_index,
                        'priority': operation.priority.value,
                        'queue_position': queue_pos,
                        'timestamp': operation.timestamp.isoformat()
                    })

        # Sort by queue position and limit
        pending_ops.sort(key=lambda x: x['queue_position'])
        return pending_ops[:limit]

    def cleanup_old_operations(self, hours: int = 24) -> int:
        """
        Clean up old operations and results.

        Args:
            hours: Age of operations to clean up

        Returns:
            Number of operations cleaned up
        """
        cutoff_time = datetime.now(pytz.UTC) - timedelta(hours=hours)
        cleaned = 0

        with self._lock:
            # Clean up old operations
            old_operations = [
                op_id for op_id, op in self._operations.items()
                if op.timestamp < cutoff_time and op.status in [
                    OperationStatus.COMPLETED,
                    OperationStatus.FAILED,
                    OperationStatus.TIMEOUT,
                    OperationStatus.CANCELLED
                ]
            ]

            for op_id in old_operations:
                self._operations.pop(op_id, None)
                self._results.pop(op_id, None)
                cleaned += 1

        self.logger.info(f"Cleaned up {cleaned} old operations")
        return cleaned