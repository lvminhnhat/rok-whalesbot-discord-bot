"""
Audit logs routes for web dashboard.
"""

from flask import Blueprint, jsonify, request, current_app

logs_bp = Blueprint('logs', __name__, url_prefix='/api/logs')


@logs_bp.route('', methods=['GET'])
def get_logs():
    """Get audit logs with optional filtering."""
    data_manager = current_app.data_manager
    
    # Get query parameters
    user_id = request.args.get('user_id')
    limit = int(request.args.get('limit', 50))
    offset = int(request.args.get('offset', 0))
    
    # Limit max to 100
    limit = min(limit, 100)
    
    logs = data_manager.get_logs(user_id=user_id, limit=limit, offset=offset)
    total_count = data_manager.get_logs_count(user_id=user_id)
    
    logs_data = [log.to_dict() for log in logs]
    
    return jsonify({
        'logs': logs_data,
        'total': total_count,
        'limit': limit,
        'offset': offset
    })

