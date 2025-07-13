import os
import yaml
from pathlib import Path
import click

def get_config():
    """Load configuration from YAML file"""
    # Check for config in several locations
    config_paths = [
        # Current directory
        Path.cwd() / 'config.yml',
        # User config directory
        Path.home() / '.config' / 'plexrr' / 'config.yml',
        # System config directory (Linux)
        Path('/etc/plexrr/config.yml') if os.name == 'posix' else None,
    ]

    # Filter out None paths
    config_paths = [p for p in config_paths if p is not None]

    # Try to load from each path
    for config_path in config_paths:
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    return yaml.safe_load(f)
            except Exception as e:
                click.echo(f"Error loading config from {config_path}: {str(e)}", err=True)

    # If no config file found, raise an error
    raise FileNotFoundError(
        "No configuration file found. Please create a config.yml file in one of these locations:\n" + 
        "\n".join(str(p) for p in config_paths)
    )

def create_default_config(path=None):
    """Create a default configuration file"""
    if not path:
        # Use user config directory by default
        path = Path.home() / '.config' / 'plexrr' / 'config.yml'

    # Create directory if it doesn't exist
    path.parent.mkdir(parents=True, exist_ok=True)

    default_config = {
        'plex': {
            'base_url': 'http://localhost:32400',
            'token': 'your-plex-token',
            # Option 1: Account credentials
            # 'username': 'your-plex-username',
            # 'password': 'your-plex-password',
            # Option 2: RSS feed URL
            'watchlist_rss': 'https://rss.plex.tv/your-unique-watchlist-id',
        },
        'radarr': {
            'base_url': 'http://localhost:7878',
            'api_key': 'your-radarr-api-key',
        }
    }

    with open(path, 'w') as f:
        yaml.dump(default_config, f, default_flow_style=False)

    return path
