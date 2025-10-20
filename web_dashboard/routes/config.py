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

