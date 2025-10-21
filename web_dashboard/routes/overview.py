"""
Overview routes for web dashboard.
"""

from flask import Blueprint, jsonify, current_app
from shared.constants import InstanceStatus

overview_bp = Blueprint('overview', __name__, url_prefix='/api')


@overview_bp.route('/overview', methods=['GET'])
def get_overview():
    """Get overview statistics."""
    data_manager = current_app.data_manager
    
    all_users = data_manager.get_all_users()
    running_users = data_manager.get_users_by_status(InstanceStatus.RUNNING)
    expired_users = data_manager.get_expired_users()
    expiring_users = data_manager.get_expiring_users(days=7)
    
    stats = {
        'total_users': len(all_users),
        'active_instances': len(running_users),
        'expired_count': len(expired_users),
        'expiring_soon_count': len(expiring_users)
    }
    
    return jsonify(stats)


@overview_bp.route('/running_instances', methods=['GET'])
def get_running_instances():
    """Get running instances summary."""
    data_manager = current_app.data_manager
    
    running_users = data_manager.get_users_by_status(InstanceStatus.RUNNING)
    
    instances = []
    for user in running_users:
        instances.append({
            'discord_id': user.discord_id,
            'discord_name': user.discord_name,
            'emulator_index': user.emulator_index,
            'last_start': user.last_start,
            'last_heartbeat': user.last_heartbeat,
            'uptime_seconds': user.uptime_seconds
        })
    
    return jsonify({'instances': instances})

