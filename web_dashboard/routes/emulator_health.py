"""
Emulator health routes for web dashboard.

This module provides endpoints for monitoring emulator health status
and accessing validation results.
"""

from flask import Blueprint, jsonify, request
from datetime import datetime
from typing import Optional

# Create blueprint
emulator_health_bp = Blueprint('emulator_health', __name__)


@emulator_health_bp.route('/api/emulator-health')
def get_emulator_health():
    """Get comprehensive emulator health status."""
    try:
        # Import here to avoid circular imports
        from shared.data_manager import DataManager
        from discord_bot.services.bot_service import BotService

        data_manager = DataManager()
        bot_service = BotService("", data_manager)

        # Get WhaleBots instance
        whalesbot = bot_service.get_whalebots_instance()
        if not whalesbot:
            return jsonify({
                'error': 'WhaleBots instance not available',
                'overall_status': 'unknown',
                'total_emulators': 0,
                'healthy_count': 0,
                'unhealthy_count': 0,
                'missing_count': 0,
                'last_validation': None,
                'validation_count': 0,
                'emulators': []
            }), 503

        # Get emulator health summary
        validator = whalesbot.emulator_validator
        health_summary = validator.get_health_summary()

        return jsonify(health_summary.to_dict())

    except Exception as e:
        return jsonify({
            'error': f'Failed to get emulator health: {str(e)}',
            'overall_status': 'error',
            'total_emulators': 0,
            'healthy_count': 0,
            'unhealthy_count': 0,
            'missing_count': 0,
            'last_validation': None,
            'validation_count': 0,
            'emulators': []
        }), 500


@emulator_health_bp.route('/api/emulator-health/<int:emulator_index>')
def get_emulator_health_by_index(emulator_index: int):
    """Get health status for a specific emulator."""
    try:
        from shared.data_manager import DataManager
        from discord_bot.services.bot_service import BotService

        data_manager = DataManager()
        bot_service = BotService("", data_manager)

        # Get WhaleBots instance
        whalesbot = bot_service.get_whalebots_instance()
        if not whalesbot:
            return jsonify({
                'error': 'WhaleBots instance not available'
            }), 503

        # Get emulator health history
        validator = whalesbot.emulator_validator
        history = validator.get_emulator_health_history(emulator_index)

        if not history:
            return jsonify({
                'error': f'No health data available for emulator {emulator_index}'
            }), 404

        # Return the most recent result
        latest_result = history[-1]
        return jsonify({
            'emulator_index': emulator_index,
            'health_result': latest_result.to_dict(),
            'history_length': len(history),
            'historical_data': [result.to_dict() for result in history[-10:]]  # Last 10 results
        })

    except Exception as e:
        return jsonify({
            'error': f'Failed to get emulator health: {str(e)}'
        }), 500


@emulator_health_bp.route('/api/emulator-health/validate', methods=['POST'])
def trigger_validation():
    """Trigger immediate emulator validation."""
    try:
        from shared.data_manager import DataManager
        from discord_bot.services.bot_service import BotService

        data_manager = DataManager()
        bot_service = BotService("", data_manager)

        # Get WhaleBots instance
        whalesbot = bot_service.get_whalebots_instance()
        if not whalesbot:
            return jsonify({
                'error': 'WhaleBots instance not available'
            }), 503

        # Get request data
        request_data = request.get_json() or {}
        emulator_index = request_data.get('emulator_index')

        # Perform validation
        validator = whalesbot.emulator_validator
        if emulator_index is not None:
            result = validator.validate_emulator_now(emulator_index)
            return jsonify({
                'message': f'Validation completed for emulator {emulator_index}',
                'result': result.to_dict()
            })
        else:
            summary = validator.validate_emulator_now()
            return jsonify({
                'message': 'Validation completed for all emulators',
                'summary': summary.to_dict()
            })

    except Exception as e:
        return jsonify({
            'error': f'Validation failed: {str(e)}'
        }), 500


@emulator_health_bp.route('/api/emulator-health/validator/status')
def get_validator_status():
    """Get emulator validator service status."""
    try:
        from shared.data_manager import DataManager
        from discord_bot.services.bot_service import BotService

        data_manager = DataManager()
        bot_service = BotService("", data_manager)

        # Get WhaleBots instance
        whalesbot = bot_service.get_whalebots_instance()
        if not whalesbot:
            return jsonify({
                'error': 'WhaleBots instance not available',
                'validator_running': False,
                'validator_enabled': False
            }), 503

        # Get validator status
        validator = whalesbot.emulator_validator

        return jsonify({
            'validator_running': validator.is_running(),
            'validator_enabled': True,
            'validation_count': validator.validation_count,
            'last_validation': validator.last_validation_time.isoformat() if validator.last_validation_time else None,
            'resource_monitoring_enabled': validator.enable_resource_monitoring,
            'auto_recovery_enabled': validator.enable_auto_recovery,
            'validation_interval_minutes': validator.interval // 60
        })

    except Exception as e:
        return jsonify({
            'error': f'Failed to get validator status: {str(e)}',
            'validator_running': False,
            'validator_enabled': False
        }), 500


@emulator_health_bp.route('/api/emulator-health/validator/control', methods=['POST'])
def control_validator():
    """Control emulator validator service (start/stop)."""
    try:
        from shared.data_manager import DataManager
        from discord_bot.services.bot_service import BotService

        data_manager = DataManager()
        bot_service = BotService("", data_manager)

        # Get WhaleBots instance
        whalesbot = bot_service.get_whalebots_instance()
        if not whalesbot:
            return jsonify({
                'error': 'WhaleBots instance not available'
            }), 503

        # Get request data
        request_data = request.get_json() or {}
        action = request_data.get('action')  # 'start' or 'stop'

        if action not in ['start', 'stop']:
            return jsonify({
                'error': 'Invalid action. Must be "start" or "stop"'
            }), 400

        # Control validator
        validator = whalesbot.emulator_validator

        if action == 'start':
            if validator.is_running():
                return jsonify({
                    'message': 'Validator is already running'
                })
            else:
                validator.start()
                return jsonify({
                    'message': 'Validator started successfully'
                })
        elif action == 'stop':
            if not validator.is_running():
                return jsonify({
                    'message': 'Validator is already stopped'
                })
            else:
                validator.stop()
                return jsonify({
                    'message': 'Validator stopped successfully'
                })

    except Exception as e:
        return jsonify({
            'error': f'Failed to control validator: {str(e)}'
        }), 500


@emulator_health_bp.route('/api/emulator-health/recovery/reset', methods=['POST'])
def reset_recovery_counters():
    """Reset restart attempt counters for emulators."""
    try:
        from shared.data_manager import DataManager
        from discord_bot.services.bot_service import BotService

        data_manager = DataManager()
        bot_service = BotService("", data_manager)

        # Get WhaleBots instance
        whalesbot = bot_service.get_whalebots_instance()
        if not whalesbot:
            return jsonify({
                'error': 'WhaleBots instance not available'
            }), 503

        # Get request data
        request_data = request.get_json() or {}
        emulator_index = request_data.get('emulator_index')

        # Reset counters
        validator = whalesbot.emulator_validator
        validator.reset_restart_counters(emulator_index)

        if emulator_index is not None:
            return jsonify({
                'message': f'Restart counters reset for emulator {emulator_index}'
            })
        else:
            return jsonify({
                'message': 'Restart counters reset for all emulators'
            })

    except Exception as e:
        return jsonify({
            'error': f'Failed to reset recovery counters: {str(e)}'
        }), 500