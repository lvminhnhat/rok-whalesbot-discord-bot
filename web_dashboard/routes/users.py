"""
Users management routes for web dashboard.
"""

from flask import Blueprint, jsonify, request, current_app
from shared.constants import ActionType, ActionResult

users_bp = Blueprint('users', __name__, url_prefix='/api/users')


@users_bp.route('', methods=['GET'])
def get_users():
    """Get all users with optional filtering."""
    data_manager = current_app.data_manager
    
    # Get query parameters
    status_filter = request.args.get('status', 'all').upper()
    expiry_filter = request.args.get('expiry', 'all')
    
    all_users = data_manager.get_all_users()
    
    # Filter by status
    if status_filter != 'ALL':
        all_users = [u for u in all_users if u.status == status_filter]
    
    # Filter by expiry
    if expiry_filter == 'expired':
        all_users = [u for u in all_users if u.subscription.is_expired]
    elif expiry_filter == 'expiring_7':
        all_users = [u for u in all_users if 0 < u.subscription.days_left <= 7]
    elif expiry_filter == 'expiring_30':
        all_users = [u for u in all_users if 0 < u.subscription.days_left <= 30]
    
    # Convert to dict
    users_data = [u.to_dict() for u in all_users]
    
    return jsonify({'users': users_data})


@users_bp.route('/<user_id>/start', methods=['POST'])
def start_user(user_id):
    """Start instance for user."""
    bot_service = current_app.bot_service
    data_manager = current_app.data_manager
    
    result = bot_service.start_instance(user_id)
    
    # Log action
    user = data_manager.get_user(user_id)
    if user:
        data_manager.log_action(
            user_id=user_id,
            user_name=user.discord_name,
            action=ActionType.START,
            details="Started from web dashboard",
            result=ActionResult.SUCCESS if result['success'] else ActionResult.FAILED,
            performed_by="web_admin"
        )
    
    return jsonify(result)


@users_bp.route('/<user_id>/stop', methods=['POST'])
def stop_user(user_id):
    """Stop instance for user."""
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
            details="Stopped from web dashboard",
            result=ActionResult.SUCCESS if result['success'] else ActionResult.FAILED,
            performed_by="web_admin"
        )
    
    return jsonify(result)


@users_bp.route('/<user_id>/add_days', methods=['POST'])
def add_days(user_id):
    """Add days to user subscription."""
    subscription_service = current_app.subscription_service
    data_manager = current_app.data_manager
    
    data = request.get_json()
    days = data.get('days')
    
    if not days or not isinstance(days, int) or days <= 0:
        return jsonify({'success': False, 'message': 'Invalid days parameter'}), 400
    
    result = subscription_service.add_days(user_id, days)
    
    # Log action
    user = data_manager.get_user(user_id)
    if user:
        data_manager.log_action(
            user_id=user_id,
            user_name=user.discord_name,
            action=ActionType.ADD_DAYS,
            details=f"Added {days} days from web dashboard",
            result=ActionResult.SUCCESS if result['success'] else ActionResult.FAILED,
            performed_by="web_admin"
        )
    
    return jsonify(result)


@users_bp.route('/<user_id>/set_expiry', methods=['POST'])
def set_expiry(user_id):
    """Set expiry date for user."""
    subscription_service = current_app.subscription_service
    data_manager = current_app.data_manager
    
    data = request.get_json()
    date = data.get('date')
    
    if not date:
        return jsonify({'success': False, 'message': 'Missing date parameter'}), 400
    
    result = subscription_service.set_expiry(user_id, date)
    
    # Log action
    user = data_manager.get_user(user_id)
    if user:
        data_manager.log_action(
            user_id=user_id,
            user_name=user.discord_name,
            action=ActionType.SET_EXPIRY,
            details=f"Set expiry to {date} from web dashboard",
            result=ActionResult.SUCCESS if result['success'] else ActionResult.FAILED,
            performed_by="web_admin"
        )
    
    return jsonify(result)


@users_bp.route('/<user_id>/revoke', methods=['POST'])
def revoke_user(user_id):
    """Revoke user subscription."""
    subscription_service = current_app.subscription_service
    bot_service = current_app.bot_service
    data_manager = current_app.data_manager
    
    # Force stop if running
    bot_service.force_stop_instance(user_id)
    
    # Revoke subscription
    result = subscription_service.revoke(user_id)
    
    # Log action
    user = data_manager.get_user(user_id)
    if user:
        data_manager.log_action(
            user_id=user_id,
            user_name=user.discord_name,
            action=ActionType.REVOKE,
            details="Revoked from web dashboard",
            result=ActionResult.SUCCESS if result['success'] else ActionResult.FAILED,
            performed_by="web_admin"
        )
    
    return jsonify(result)

