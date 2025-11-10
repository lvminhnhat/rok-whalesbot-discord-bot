"""
Users management routes for web dashboard.
"""

from flask import Blueprint, jsonify, request, current_app
from shared.constants import ActionType, ActionResult
import asyncio

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

    # Handle async function properly
    try:
        # Check if start_instance is async
        if asyncio.iscoroutinefunction(bot_service.start_instance):
            # Run the coroutine in the event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(bot_service.start_instance(user_id))
            finally:
                loop.close()
        else:
            # If it's not async, call it normally
            result = bot_service.start_instance(user_id)
    except Exception as e:
        # Handle any exceptions during execution
        result = {
            'success': False,
            'message': f'Error starting instance: {str(e)}'
        }

    # Log action
    user = data_manager.get_user(user_id)
    if user:
        # Ensure result is a dict before trying to access 'success'
        success_value = result.get('success', False) if isinstance(result, dict) else False
        data_manager.log_action(
            user_id=user_id,
            user_name=user.discord_name,
            action=ActionType.START,
            details="Started from web dashboard",
            result=ActionResult.SUCCESS if success_value else ActionResult.FAILED,
            performed_by="web_admin"
        )

    return jsonify(result)


@users_bp.route('/<user_id>/stop', methods=['POST'])
def stop_user(user_id):
    """Stop instance for user."""
    bot_service = current_app.bot_service
    data_manager = current_app.data_manager

    # Use force_stop_instance which is not async
    result = bot_service.force_stop_instance(user_id)

    # Log action
    user = data_manager.get_user(user_id)
    if user:
        # Ensure result is a dict before trying to access 'success'
        success_value = result.get('success', False) if isinstance(result, dict) else False
        data_manager.log_action(
            user_id=user_id,
            user_name=user.discord_name,
            action=ActionType.FORCE_STOP,
            details="Stopped from web dashboard",
            result=ActionResult.SUCCESS if success_value else ActionResult.FAILED,
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


@users_bp.route('/<user_id>/unlink', methods=['POST'])
def unlink_user(user_id):
    """Unlink user from emulator."""
    bot_service = current_app.bot_service
    data_manager = current_app.data_manager

    # Force stop if running
    bot_service.force_stop_instance(user_id)

    # Unlink user
    result = bot_service.unlink_user_from_emulator(user_id)

    # Log action
    user = data_manager.get_user(user_id)
    if user:
        data_manager.log_action(
            user_id=user_id,
            user_name=user.discord_name,
            action=ActionType.CONFIG_CHANGE,
            details="Unlinked from web dashboard",
            result=ActionResult.SUCCESS if result['success'] else ActionResult.FAILED,
            performed_by="web_admin"
        )

    return jsonify(result)


@users_bp.route('/<user_id>/delete', methods=['DELETE'])
def delete_user(user_id):
    """Delete user from system."""
    bot_service = current_app.bot_service
    data_manager = current_app.data_manager

    # Get user info before deletion
    user = data_manager.get_user(user_id)
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404

    # Force stop if running
    try:
        bot_service.force_stop_instance(user_id)
    except:
        pass  # Ignore errors during cleanup

    # Delete user
    success = data_manager.delete_user(user_id)

    # Log action
    if user:
        data_manager.log_action(
            user_id=user_id,
            user_name=user.discord_name,
            action=ActionType.CONFIG_CHANGE,
            details="Deleted from web dashboard",
            result=ActionResult.SUCCESS if success else ActionResult.FAILED,
            performed_by="web_admin"
        )

    return jsonify({
        'success': success,
        'message': 'User deleted successfully' if success else 'Failed to delete user'
    })


@users_bp.route('/bulk-unlink-expired', methods=['POST'])
def bulk_unlink_expired():
    """Unlink all expired users."""
    bot_service = current_app.bot_service
    data_manager = current_app.data_manager

    # Get all expired users with emulators
    all_users = data_manager.get_all_users()
    expired_users = [u for u in all_users if u.subscription.is_expired and u.emulator_index != -1]

    if not expired_users:
        return jsonify({
            'success': True,
            'message': 'No expired users with emulators found',
            'results': []
        })

    results = []
    success_count = 0

    for user in expired_users:
        try:
            # Force stop if running
            if user.is_running:
                bot_service.force_stop_instance(user.discord_id)

            # Unlink user
            result = bot_service.unlink_user_from_emulator(user.discord_id)
            results.append({
                'user_id': user.discord_id,
                'user_name': user.discord_name,
                'success': result['success'],
                'message': result['message']
            })

            if result['success']:
                success_count += 1

        except Exception as e:
            results.append({
                'user_id': user.discord_id,
                'user_name': user.discord_name,
                'success': False,
                'message': str(e)
            })

    # Log action
    data_manager.log_action(
        user_id="web_admin",
        user_name="Web Admin",
        action=ActionType.CONFIG_CHANGE,
        details=f"Bulk unlink expired: {success_count}/{len(expired_users)} success",
        result=ActionResult.SUCCESS if success_count > 0 else ActionResult.FAILED,
        performed_by="web_admin"
    )

    return jsonify({
        'success': success_count > 0,
        'message': f'Unlinked {success_count}/{len(expired_users)} expired users',
        'results': results
    })


@users_bp.route('/bulk-delete-expired', methods=['DELETE'])
def bulk_delete_expired():
    """Delete all expired users."""
    bot_service = current_app.bot_service
    data_manager = current_app.data_manager

    # Get all expired users
    all_users = data_manager.get_all_users()
    expired_users = [u for u in all_users if u.subscription.is_expired]

    if not expired_users:
        return jsonify({
            'success': True,
            'message': 'No expired users found',
            'results': []
        })

    results = []
    success_count = 0

    for user in expired_users:
        try:
            # Force stop if running
            if user.is_running:
                bot_service.force_stop_instance(user.discord_id)

            # Delete user
            success = data_manager.delete_user(user.discord_id)
            results.append({
                'user_id': user.discord_id,
                'user_name': user.discord_name,
                'success': success,
                'message': 'Deleted successfully' if success else 'Failed to delete'
            })

            if success:
                success_count += 1

        except Exception as e:
            results.append({
                'user_id': user.discord_id,
                'user_name': user.discord_name,
                'success': False,
                'message': str(e)
            })

    # Log action
    data_manager.log_action(
        user_id="web_admin",
        user_name="Web Admin",
        action=ActionType.CONFIG_CHANGE,
        details=f"Bulk delete expired: {success_count}/{len(expired_users)} success",
        result=ActionResult.SUCCESS if success_count > 0 else ActionResult.FAILED,
        performed_by="web_admin"
    )

    return jsonify({
        'success': success_count > 0,
        'message': f'Deleted {success_count}/{len(expired_users)} expired users',
        'results': results
    })

