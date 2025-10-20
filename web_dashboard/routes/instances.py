"""
Running instances routes for web dashboard.
"""

from flask import Blueprint, jsonify, current_app
from shared.constants import InstanceStatus, ActionType, ActionResult

instances_bp = Blueprint('instances', __name__, url_prefix='/api/instances')


@instances_bp.route('', methods=['GET'])
def get_instances():
    """Get all running instances."""
    data_manager = current_app.data_manager
    
    running_users = data_manager.get_users_by_status(InstanceStatus.RUNNING)
    
    instances = []
    for user in running_users:
        instances.append({
            'discord_id': user.discord_id,
            'discord_name': user.discord_name,
            'emulator_index': user.emulator_index,
            'status': user.status,
            'last_start': user.last_start,
            'last_heartbeat': user.last_heartbeat,
            'uptime_seconds': user.uptime_seconds
        })
    
    return jsonify({'instances': instances})


@instances_bp.route('/<user_id>/stop', methods=['POST'])
def stop_instance(user_id):
    """Force stop instance."""
    bot_service = current_app.bot_service
    data_manager = current_app.data_manager
    
    result = bot_service.force_stop_instance(user_id)
    
    # Log action
    user = data_manager.get_user(user_id)
    if user:
        data_manager.log_action(
            user_id=user_id,
            user_name=user.discord_name,
            action=ActionType.FORCE_STOP,
            details="Force stopped from instances page",
            result=ActionResult.SUCCESS if result['success'] else ActionResult.FAILED,
            performed_by="web_admin"
        )
    
    return jsonify(result)

