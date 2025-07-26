import json
import logging
import os
import re
import subprocess
from typing import Dict, List, Optional, Tuple, Any

from flask import Flask, request, jsonify

from ..utils.config_loader import get_config

logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    """Handle incoming webhook from Plex"""
    if not request.json:
        return jsonify({"status": "error", "message": "Invalid request, no JSON data"}), 400

    payload = request.json
    event = payload.get('event')

    if not event:
        return jsonify({"status": "error", "message": "Missing 'event' in webhook payload"}), 400

    logger.info(f"Received webhook for event: {event}")

    # Map Plex event names to webhook config keys
    event_map = {
        'media.play': 'on-play',
        'media.pause': 'on-pause',
        'media.resume': 'on-resume',
        'media.stop': 'on-stop',
        'media.scrobble': 'after-watched',  # This is triggered when something is marked as watched
        'media.rate': 'on-rate',
        'library.new': 'on-added',
        'library.on.deck': 'on-deck'
    }

    webhook_event = event_map.get(event)
    if not webhook_event:
        logger.warning(f"Unhandled event type: {event}")
        return jsonify({"status": "ignored", "message": f"No handler for event: {event}"}), 200

    # Get webhook configuration
    config = get_config()
    webhook_config = config.get('webhooks', {})

    # Check if we have commands configured for this event
    commands = webhook_config.get(webhook_event, [])
    if not commands:
        logger.info(f"No commands configured for event: {webhook_event}")
        return jsonify({"status": "ignored", "message": f"No commands for event: {webhook_event}"}), 200

    # Get metadata from the payload
    metadata = _extract_metadata(payload)

    # Execute each configured command
    results = []
    for command in commands:
        result = execute_command(command, metadata)
        results.append(result)

    return jsonify({
        "status": "success", 
        "event": webhook_event,
        "results": results
    }), 200

def _extract_metadata(payload: Dict) -> Dict:
    """Extract relevant metadata from Plex webhook payload"""
    metadata = {
        "event": payload.get('event'),
        "user": payload.get('Account', {}).get('title', 'Unknown'),
        "player": payload.get('Player', {}).get('title', 'Unknown')
    }

    # Extract media type and details
    if 'Metadata' in payload:
        meta = payload['Metadata']
        metadata['type'] = meta.get('type')
        metadata['title'] = meta.get('title')

        if metadata['type'] == 'episode':
            metadata['show_title'] = meta.get('grandparentTitle')
            metadata['season'] = meta.get('parentIndex')
            metadata['episode'] = meta.get('index')
            metadata['rating_key'] = meta.get('ratingKey')  # Plex ID
            metadata['show_rating_key'] = meta.get('grandparentRatingKey')  # Show's Plex ID
        elif metadata['type'] == 'movie':
            metadata['year'] = meta.get('year')
            metadata['rating_key'] = meta.get('ratingKey')  # Plex ID

    return metadata

def execute_command(command_str: str, metadata: Dict) -> Dict:
    """Execute a plexrr command with the given parameters"""
    result = {
        "command": command_str,
        "success": False,
        "output": "",
        "error": ""
    }

    try:
        # Parse the command string
        command_parts = _parse_command(command_str, metadata)
        if not command_parts:
            result["error"] = "Failed to parse command"
            return result

        # Determine if we're running from a development environment or installed package
        import sys
        import os

        # Get the current script directory to determine the Python executable path
        current_dir = os.path.dirname(os.path.abspath(__file__))

        # Find the Python executable being used
        python_executable = sys.executable
        logger.debug(f"Using Python executable: {python_executable}")

        # Use python -m plexrr.cli instead of direct plexrr command
        # This ensures the command works in both development and installed environments
        full_command = [python_executable, "-m", "plexrr.cli"] + command_parts
        logger.info(f"Executing command: {' '.join(full_command)}")

        # Execute the command
        process = subprocess.run(
            full_command,
            capture_output=True,
            text=True,
            check=False  # Don't raise exception on non-zero exit
        )

        # Capture the results
        result["success"] = process.returncode == 0
        result["output"] = process.stdout
        result["error"] = process.stderr

        if not result["success"]:
            logger.error(f"Command failed: {command_str}\nError: {result['error']}")
        else:
            logger.info(f"Command succeeded: {command_str}")

    except Exception as e:
        logger.exception(f"Error executing command: {command_str}")
        result["error"] = str(e)

    return result

def _parse_command(command_str: str, metadata: Dict) -> List[str]:
    """Parse a command string into parts, substituting placeholders with values from metadata"""
    # Basic parsing with regex to handle quotes correctly
    parts = []
    pattern = r'([^\s"]+)|"([^"]*)"'

    for match in re.finditer(pattern, command_str):
        # Either group 1 or group 2 will be matched but not both
        part = match.group(1) or match.group(2)

        # Handle metadata placeholders
        if part.startswith('${') and part.endswith('}'):
            key = part[2:-1]  # Remove ${ and }
            if key in metadata:
                part = str(metadata[key])

        parts.append(part)

    return parts

def run_webhook_server(host: str = '0.0.0.0', port: int = 9876, debug: bool = False):
    """Run the webhook server"""
    # Set up logging
    if debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    logger.info(f"Starting webhook server on {host}:{port}")
    app.run(host=host, port=port, debug=debug)
