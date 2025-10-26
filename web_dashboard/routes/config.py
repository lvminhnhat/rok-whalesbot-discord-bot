"""
Configuration routes for web dashboard.
"""

from flask import Blueprint, jsonify, request, current_app
from shared.constants import ActionType, ActionResult

config_bp = Blueprint('config', __name__, url_prefix='/api/config')


@config_bp.route('', methods=['GET'])
def get_config():
    """Get current configuration."""
    data_manager = current_app.data_manager
    config = data_manager.get_config()
    
    return jsonify(config.to_dict())


@config_bp.route('/allowed_guilds', methods=['POST'])
def update_allowed_guilds():
    """Update allowed guilds."""
    data_manager = current_app.data_manager
    data = request.get_json()
    
    action = data.get('action')
    guild_id = data.get('guild_id')
    
    if not action or not guild_id:
        return jsonify({'success': False, 'message': 'Missing action or guild_id'}), 400
    
    config = data_manager.get_config()
    
    if action == 'add':
        if guild_id not in config.allowed_guilds:
            config.allowed_guilds.append(guild_id)
            data_manager.save_config(config)
            
            data_manager.log_action(
                user_id="system",
                user_name="Web Admin",
                action=ActionType.CONFIG_UPDATE,
                details=f"Added guild {guild_id} to allowed_guilds",
                result=ActionResult.SUCCESS,
                performed_by="web_admin"
            )
            
            return jsonify({'success': True, 'message': 'Guild added'})
        else:
            return jsonify({'success': False, 'message': 'Guild already in list'})
    
    elif action == 'remove':
        if guild_id in config.allowed_guilds:
            config.allowed_guilds.remove(guild_id)
            data_manager.save_config(config)
            
            data_manager.log_action(
                user_id="system",
                user_name="Web Admin",
                action=ActionType.CONFIG_UPDATE,
                details=f"Removed guild {guild_id} from allowed_guilds",
                result=ActionResult.SUCCESS,
                performed_by="web_admin"
            )
            
            return jsonify({'success': True, 'message': 'Guild removed'})
        else:
            return jsonify({'success': False, 'message': 'Guild not in list'})
    
    return jsonify({'success': False, 'message': 'Invalid action'}), 400


@config_bp.route('/allowed_channels', methods=['POST'])
def update_allowed_channels():
    """Update allowed channels."""
    data_manager = current_app.data_manager
    data = request.get_json()
    
    action = data.get('action')
    channel_id = data.get('channel_id')
    
    if not action or not channel_id:
        return jsonify({'success': False, 'message': 'Missing action or channel_id'}), 400
    
    config = data_manager.get_config()
    
    if action == 'add':
        if channel_id not in config.allowed_channels:
            config.allowed_channels.append(channel_id)
            data_manager.save_config(config)
            
            data_manager.log_action(
                user_id="system",
                user_name="Web Admin",
                action=ActionType.CONFIG_UPDATE,
                details=f"Added channel {channel_id} to allowed_channels",
                result=ActionResult.SUCCESS,
                performed_by="web_admin"
            )
            
            return jsonify({'success': True, 'message': 'Channel added'})
        else:
            return jsonify({'success': False, 'message': 'Channel already in list'})
    
    elif action == 'remove':
        if channel_id in config.allowed_channels:
            config.allowed_channels.remove(channel_id)
            data_manager.save_config(config)
            
            data_manager.log_action(
                user_id="system",
                user_name="Web Admin",
                action=ActionType.CONFIG_UPDATE,
                details=f"Removed channel {channel_id} from allowed_channels",
                result=ActionResult.SUCCESS,
                performed_by="web_admin"
            )
            
            return jsonify({'success': True, 'message': 'Channel removed'})
        else:
            return jsonify({'success': False, 'message': 'Channel not in list'})
    
    return jsonify({'success': False, 'message': 'Invalid action'}), 400


@config_bp.route('/cooldown', methods=['POST'])
def update_cooldown():
    """Update cooldown setting."""
    data_manager = current_app.data_manager
    data = request.get_json()

    seconds = data.get('seconds')

    if seconds is None or not isinstance(seconds, int) or seconds < 0:
        return jsonify({'success': False, 'message': 'Invalid seconds parameter'}), 400

    config = data_manager.get_config()
    config.cooldown_seconds = seconds
    data_manager.save_config(config)

    data_manager.log_action(
        user_id="system",
        user_name="Web Admin",
        action=ActionType.CONFIG_UPDATE,
        details=f"Set cooldown to {seconds} seconds",
        result=ActionResult.SUCCESS,
        performed_by="web_admin"
    )

    return jsonify({'success': True, 'message': f'Cooldown set to {seconds} seconds'})


@config_bp.route('/admin_users', methods=['POST'])
def update_admin_users():
    """Update admin users list."""
    data_manager = current_app.data_manager
    data = request.get_json()

    action = data.get('action')
    user_id = data.get('user_id')
    user_name = data.get('user_name', f'User {user_id}')

    if not action or not user_id:
        return jsonify({'success': False, 'message': 'Missing action or user_id'}), 400

    # Validate user_id format (should be a numeric string)
    if not user_id.isdigit() or len(user_id) < 17 or len(user_id) > 19:
        return jsonify({'success': False, 'message': 'Invalid Discord user ID format'}), 400

    config = data_manager.get_config()

    if action == 'add':
        if user_id not in config.admin_users:
            config.admin_users.append(user_id)
            data_manager.save_config(config)

            data_manager.log_action(
                user_id="system",
                user_name="Web Admin",
                action=ActionType.CONFIG_UPDATE,
                details=f"Added admin user {user_name} ({user_id})",
                result=ActionResult.SUCCESS,
                performed_by="web_admin"
            )

            return jsonify({'success': True, 'message': f'Admin user {user_name} added successfully'})
        else:
            return jsonify({'success': False, 'message': 'User is already an admin'})

    elif action == 'remove':
        if user_id in config.admin_users:
            # Prevent removing the last admin
            if len(config.admin_users) <= 1:
                return jsonify({'success': False, 'message': 'Cannot remove the last admin user'}), 400

            config.admin_users.remove(user_id)
            data_manager.save_config(config)

            data_manager.log_action(
                user_id="system",
                user_name="Web Admin",
                action=ActionType.CONFIG_UPDATE,
                details=f"Removed admin user {user_name} ({user_id})",
                result=ActionResult.SUCCESS,
                performed_by="web_admin"
            )

            return jsonify({'success': True, 'message': f'Admin user {user_name} removed successfully'})
        else:
            return jsonify({'success': False, 'message': 'User is not an admin'})

    return jsonify({'success': False, 'message': 'Invalid action'}), 400


@config_bp.route('/admin_roles', methods=['POST'])
def update_admin_roles():
    """Update admin roles list."""
    data_manager = current_app.data_manager
    data = request.get_json()

    action = data.get('action')
    role_id = data.get('role_id')
    role_name = data.get('role_name', f'Role {role_id}')

    if not action or not role_id:
        return jsonify({'success': False, 'message': 'Missing action or role_id'}), 400

    # Validate role_id format (should be a numeric string)
    if not role_id.isdigit() or len(role_id) < 17 or len(role_id) > 19:
        return jsonify({'success': False, 'message': 'Invalid Discord role ID format'}), 400

    config = data_manager.get_config()

    if action == 'add':
        if role_id not in config.admin_roles:
            config.admin_roles.append(role_id)
            data_manager.save_config(config)

            data_manager.log_action(
                user_id="system",
                user_name="Web Admin",
                action=ActionType.CONFIG_UPDATE,
                details=f"Added admin role {role_name} ({role_id})",
                result=ActionResult.SUCCESS,
                performed_by="web_admin"
            )

            return jsonify({'success': True, 'message': f'Admin role {role_name} added successfully'})
        else:
            return jsonify({'success': False, 'message': 'Role is already an admin role'})

    elif action == 'remove':
        if role_id in config.admin_roles:
            config.admin_roles.remove(role_id)
            data_manager.save_config(config)

            data_manager.log_action(
                user_id="system",
                user_name="Web Admin",
                action=ActionType.CONFIG_UPDATE,
                details=f"Removed admin role {role_name} ({role_id})",
                result=ActionResult.SUCCESS,
                performed_by="web_admin"
            )

            return jsonify({'success': True, 'message': f'Admin role {role_name} removed successfully'})
        else:
            return jsonify({'success': False, 'message': 'Role is not an admin role'})

    return jsonify({'success': False, 'message': 'Invalid action'}), 400


@config_bp.route('/max_emulators', methods=['POST'])
def update_max_emulators():
    """Update maximum emulators setting."""
    data_manager = current_app.data_manager
    data = request.get_json()

    max_emulators = data.get('max_emulators')

    if max_emulators is None or not isinstance(max_emulators, int) or max_emulators < 1:
        return jsonify({'success': False, 'message': 'Invalid max_emulators parameter (must be >= 1)'}), 400

    config = data_manager.get_config()
    config.max_emulators = max_emulators
    data_manager.save_config(config)

    data_manager.log_action(
        user_id="system",
        user_name="Web Admin",
        action=ActionType.CONFIG_UPDATE,
        details=f"Set max emulators to {max_emulators}",
        result=ActionResult.SUCCESS,
        performed_by="web_admin"
    )

    return jsonify({'success': True, 'message': f'Maximum emulators set to {max_emulators}'})

