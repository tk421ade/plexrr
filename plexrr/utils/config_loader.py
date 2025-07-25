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
        Path.cwd() / 'config.yaml',
        # User config directory
        Path.home() / '.config' / 'plexrr' / 'config.yml',
        Path.home() / '.config' / 'plexrr' / 'config.yaml',
        # System config directory (Linux)
        Path('/etc/plexrr/config.yml') if os.name == 'posix' else None,
        Path('/etc/plexrr/config.yaml') if os.name == 'posix' else None,
    ]

    # Filter out None paths
    config_paths = [p for p in config_paths if p is not None]

    # Try to load from each path
    for config_path in config_paths:
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f)

                # Validate required configurations
                if not config:
                    click.echo(f"Error: Empty configuration file at {config_path}", err=True)
                    continue

                # Validate Plex config
                if 'plex' not in config:
                    raise ValueError(f"Configuration file at {config_path} is missing required 'plex' section")
                plex_config = config['plex']
                if 'base_url' not in plex_config or 'token' not in plex_config:
                    raise ValueError(f"Plex configuration must include 'base_url' and 'token'")

                # Validate Radarr config
                if 'radarr' not in config:
                    raise ValueError(
                        f"Configuration file at {config_path} is missing required 'radarr' section.\n"
                        f"Please add a 'radarr' section with 'base_url' and 'api_key' values to your configuration file.")
                radarr_config = config['radarr']
                if 'base_url' not in radarr_config or 'api_key' not in radarr_config:
                    raise ValueError(f"Radarr configuration must include 'base_url' and 'api_key'")

                # Check Sonarr config if present
                if 'sonarr' in config:
                    sonarr_config = config['sonarr']
                    if 'base_url' not in sonarr_config or 'api_key' not in sonarr_config:
                        raise ValueError(f"Sonarr configuration must include 'base_url' and 'api_key'")

                return config

            except ValueError as ve:
                # Re-raise these as they're specific validation errors we want to show
                raise ve
            except Exception as e:
                click.echo(f"Error loading config from {config_path}: {str(e)}", err=True)

    # Create user-friendly error message with instructions
    config_paths_str = "\n - ".join(str(p) for p in config_paths)
    example_config = """
# Example configuration (save as config.yml):
plex:
  base_url: "http://localhost:32400"
  token: "your-plex-token"
  # For watchlist, either use username/password OR watchlist_rss
  watchlist_rss: "https://rss.plex.tv/your-unique-watchlist-id"

radarr:
  base_url: "http://localhost:7878"
  api_key: "your-radarr-api-key"

# Optional: Configure Sonarr for TV shows
sonarr:
  base_url: "http://localhost:8989"
  api_key: "your-sonarr-api-key"
"""

    error_message = f"""
Error: No configuration file found.

To fix this problem:

1. Create a configuration file in one of these locations:
   {config_paths_str}

2. Run the following command to create a template:
   ./venv/bin/python -m plexrr.cli config create

3. Then edit the file with your actual credentials

{example_config}
"""

    raise FileNotFoundError(error_message)

def create_default_config(path=None):
    """Create a default configuration file"""
    if not path:
        # Use user config directory by default
        path = Path.home() / '.config' / 'plexrr' / 'config.yml'

    # Create directory if it doesn't exist
    path.parent.mkdir(parents=True, exist_ok=True)

    # Check if file already exists to avoid overwriting
    if path.exists():
        click.echo(f"Configuration file already exists at {path}")
        if not click.confirm("Do you want to overwrite it?", default=False):
            click.echo("Operation cancelled.")
            return None

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
        },
        # Optional Sonarr configuration
        'sonarr': {
            'base_url': 'http://localhost:8989',
            'api_key': 'your-sonarr-api-key',
        }
    }

    with open(path, 'w') as f:
        yaml.dump(default_config, f, default_flow_style=False)

    click.echo(f"\nConfiguration file created at {path}")
    click.echo("\nPlease edit this file with your actual Plex, Radarr, and optionally Sonarr credentials.")
    click.echo("\nInstructions:")
    click.echo(" 1. Get your Plex token from: https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/")
    click.echo(" 2. Get your Radarr API key from the Radarr web interface: Settings → General → Security")
    click.echo(" 3. If using Sonarr, get your API key from the Sonarr web interface: Settings → General → Security")

    return path
