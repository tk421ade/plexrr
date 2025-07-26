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

# Add before/after request handlers to log everything
@app.before_request
def log_request_info():
    """Log request data for debugging"""
    logger.debug(f"Request Method: {request.method}")
    logger.debug(f"Request URL: {request.url}")
    logger.debug(f"Request Headers: {dict(request.headers)}")

    # Only log content for non-GET requests
    if request.method != 'GET':
        content_type = request.headers.get('Content-Type', '')
        logger.debug(f"Content-Type: {content_type}")

        # Log the raw data
        if request.data:
            try:
                logger.debug(f"Request Raw Data: {request.data.decode('utf-8')}")
            except UnicodeDecodeError:
                logger.debug(f"Request Raw Data: [binary data, size: {len(request.data)} bytes]")

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    """Handle incoming webhook from Plex"""
    # Log all raw incoming data for debugging
    content_type = request.headers.get('Content-Type', '')
    logger.debug(f"Webhook received with Content-Type: {content_type}")

    # Parse the payload based on content type
    payload = None
    error_msg = None

    try:
        if 'application/json' in content_type:
            payload = request.json
        elif 'application/x-www-form-urlencoded' in content_type:
            # Plex sometimes sends data as form-encoded with a 'payload' parameter
            form_data = request.form.to_dict()
            if 'payload' in form_data:
                payload = json.loads(form_data['payload'])
                logger.debug(f"Extracted JSON from form data: {payload}")
            else:
                error_msg = "Form data received but no 'payload' parameter found"
                logger.error(f"Form data keys: {list(form_data.keys())}")
        elif 'multipart/form-data' in content_type:
            # Handle multipart form data
            form_data = request.form.to_dict()
            if 'payload' in form_data:
                payload = json.loads(form_data['payload'])
                logger.debug(f"Extracted JSON from multipart form: {payload}")
            else:
                error_msg = "Multipart form data received but no 'payload' parameter found"
                logger.error(f"Form data keys: {list(form_data.keys())}")
        else:
            # Try to parse raw data as JSON as a fallback
            try:
                raw_data = request.get_data(as_text=True)
                if raw_data:
                    payload = json.loads(raw_data)
                    logger.debug(f"Parsed raw data as JSON: {payload}")
                else:
                    error_msg = f"Unsupported Content-Type: {content_type} and no raw data"
            except json.JSONDecodeError as e:
                error_msg = f"Failed to parse request data as JSON: {str(e)}"
                logger.error(f"Raw data: {request.get_data(as_text=True)[:500]}...")
    except Exception as e:
        error_msg = f"Error processing webhook request: {str(e)}"
        logger.exception("Webhook processing error")

    # Handle case where we couldn't get a payload
    if not payload:
        logger.error(f"Invalid webhook request: {error_msg}")
        return jsonify({"status": "error", "message": error_msg or "Invalid request format"}), 415

    # Log the full payload for debugging
    logger.debug(f"Webhook payload: {json.dumps(payload, indent=2)}")

    # Extract the event
    event = payload.get('event')

    if not event:
        return jsonify({"status": "error", "message": "Missing 'event' in webhook payload"}), 400

    # Log basic event information
    logger.info(f"Received webhook for event: {event}")

    # Log additional webhook details if available
    media_type = payload.get('Metadata', {}).get('type')
    media_title = payload.get('Metadata', {}).get('title')
    user = payload.get('Account', {}).get('title')

    log_details = []
    if media_type:
        log_details.append(f"type: {media_type}")
    if media_title:
        log_details.append(f"title: {media_title}")
    if user:
        log_details.append(f"user: {user}")

    if log_details:
        logger.info(f"Webhook details: {', '.join(log_details)}")

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

        # Log command output and results
        if not result["success"]:
            # Log error details
            logger.error(f"Command failed: {command_str}")
            logger.error(f"Exit code: {process.returncode}")
            if result['error']:
                _log_output("Error output", result['error'], logger.error)
        else:
            # Log success and output
            logger.info(f"Command succeeded: {command_str}")

            # Log stdout if available
            if result['output'].strip():
                _log_output("Command output", result['output'], logger.info)

    except Exception as e:
        logger.exception(f"Error executing command: {command_str}")
        result["error"] = str(e)

    return result

def _log_output(prefix: str, text: str, log_func) -> None:
    """Helper to format and log multi-line output

    Args:
        prefix: Prefix text to add before the output block
        text: The text to log (can be multi-line)
        log_func: The logging function to use (e.g., logger.info, logger.error)
    """
    if not text or not text.strip():
        return

    log_func(f"{prefix}:")
    for line in text.strip().split('\n'):
        log_func(f"  {line}")

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

def run_webhook_server(host: str = '0.0.0.0', port: int = 9876, debug: bool = False, log_file: str = None):
    """Run the webhook server"""
    # Set up logging
    log_level = logging.DEBUG if debug else logging.INFO

    if log_file:
        # Configure logging to file with rotation
        from logging.handlers import RotatingFileHandler

        # Create handler with rotation (max 5MB, keep 5 backup files)
        handler = RotatingFileHandler(
            log_file, maxBytes=5*1024*1024, backupCount=5
        )
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        handler.setLevel(log_level)

        # Add handler to root logger and this module's logger
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)
        root_logger.addHandler(handler)

        logger.info(f"Logging to file: {log_file}")
    else:
        # Basic console logging
        logging.basicConfig(level=log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    logger.info(f"Starting webhook server on {host}:{port}")
    app.run(host=host, port=port, debug=debug)
