import os
import yaml
from pathlib import Path
import click

def get_config():
    """Load configuration from YAML or INI file"""
    # Check for config in several locations
    config_paths = [
        # Current directory
        Path.cwd() / 'config.yml',
        Path.cwd() / 'config.yaml',
        Path.cwd() / 'config.ini',
        # User config directory
        Path.home() / '.config' / 'plexrr' / 'config.yml',
        Path.home() / '.config' / 'plexrr' / 'config.yaml',
        Path.home() / '.config' / 'plexrr' / 'config.ini',
        # Alternative user config directory (for compatibility)
        Path.home() / '.netflarr' / 'config.ini',
        # System config directory (Linux)
        Path('/etc/plexrr/config.yml') if os.name == 'posix' else None,
        Path('/etc/plexrr/config.yaml') if os.name == 'posix' else None,
        Path('/etc/plexrr/config.ini') if os.name == 'posix' else None,
    ]

    # Filter out None paths
    config_paths = [p for p in config_paths if p is not None]

    # Try to load from each path
    for config_path in config_paths:
        if config_path.exists():
            try:
                # Determine file type based on extension
                if config_path.suffix.lower() in ['.ini']:
                    # Load INI file
                    import configparser
                    parser = configparser.ConfigParser()
                    parser.read(config_path)

                    # Debug message for troubleshooting - enable for all config files
                    click.echo(f"Loading config from: {config_path}", err=True)
                    click.echo(f"Sections found: {parser.sections()}", err=True)
                    if 'webhooks' in parser.sections():
                        click.echo(f"Webhook section found with items: {list(parser['webhooks'].items())}", err=True)

                        # Directly read the file to check for webhooks section formatting
                        with open(config_path, 'r') as f:
                            content = f.read()
                            click.echo("\nRaw config file content:", err=True)
                            webhook_section = False
                            webhook_lines = []
                            for line in content.splitlines():
                                if line.strip() == '[webhooks]':
                                    webhook_section = True
                                    webhook_lines.append(line)
                                elif webhook_section and line.strip() and line.strip().startswith('['):
                                    webhook_section = False
                                elif webhook_section:
                                    webhook_lines.append(line)

                            if webhook_lines:
                                click.echo("\nWebhook section content:", err=True)
                                for line in webhook_lines:
                                    click.echo(f"  {line}", err=True)

                    # Convert ConfigParser to dict
                    config = {}
                    for section in parser.sections():
                        config[section] = {}
                        for key, value in parser.items(section):
                            # Special handling for webhooks section
                            if section == 'webhooks' and value.strip():
                                # Split by commas and create a list of commands
                                config[section][key] = [cmd.strip() for cmd in value.split(',') if cmd.strip()]
                            else:
                                config[section][key] = value
                else:
                    # Load YAML file
                    with open(config_path, 'r') as f:
                        config = yaml.safe_load(f)

                # Validate required configurations
                if not config:
                    click.echo(f"Error: Empty configuration file at {config_path}", err=True)
                    continue

                # Store the config path as a metadata attribute (outside the main config structure)
                config.update({'_config_path': str(config_path)})

                # Normalize config fields for compatibility
                # Handle 'url' vs 'base_url' in plex, radarr, and sonarr sections
                for section in ['plex', 'radarr', 'sonarr']:
                    if section in config:
                        if 'url' in config[section] and 'base_url' not in config[section]:
                            config[section]['base_url'] = config[section]['url']

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
    # Determine file format based on path extension
    if path:
        use_ini = Path(path).suffix.lower() == '.ini'
        if use_ini:
            click.echo("Note: YAML format (.yml) is recommended over INI format (.ini)")
    else:
        # Use user config directory by default with YAML format
        path = Path.home() / '.config' / 'plexrr' / 'config.yml'
        use_ini = False

    # Create directory if it doesn't exist
    path.parent.mkdir(parents=True, exist_ok=True)

    # Check if file already exists to avoid overwriting
    if path.exists():
        click.echo(f"Configuration file already exists at {path}")
        if not click.confirm("Do you want to overwrite it?", default=False):
            click.echo("Operation cancelled.")
            return None

    # Use template files instead of hardcoded strings
    if use_ini:
        # INI format is supported but not recommended
        click.echo("Note: INI format is being phased out. YAML format is recommended for better compatibility.")

        # Use INI template file
        template_path = Path(__file__).parent.parent / 'templates' / 'config.ini.template'
        if template_path.exists():
            with open(template_path, 'r') as template_file, open(path, 'w') as output_file:
                output_file.write(template_file.read())
        else:
            # Fallback to creating INI from scratch if template is missing
            import configparser
            config = configparser.ConfigParser()

            # Create Plex section
            config['plex'] = {
                'base_url': 'http://localhost:32400',
                'token': 'your-plex-token-here',
                'watchlist_rss': 'https://rss.plex.tv/your-unique-watchlist-id'
            }

            # Create Radarr section
            config['radarr'] = {
                'base_url': 'http://localhost:7878',
                'api_key': 'your-radarr-api-key'
            }

            # Create Sonarr section
            config['sonarr'] = {
                'base_url': 'http://localhost:8989',
                'api_key': 'your-sonarr-api-key'
            }

            # Create Webhooks section
            config['webhooks'] = {
                'after-watched': 'download-next --count 2 --execute, delete-watched --days 0 --execute',
                'on-play': '',
                'on-stop': '',
                'on-added': ''
            }

            with open(path, 'w') as f:
                config.write(f)
    else:
        # Use YAML format (preferred)
        template_path = Path(__file__).parent.parent / 'templates' / 'config.yml.template'
        if template_path.exists():
            with open(template_path, 'r') as template_file, open(path, 'w') as output_file:
                output_file.write(template_file.read())
        else:
            # Fallback to creating YAML from scratch if template is missing
            default_config = {
                'plex': {
                    'base_url': 'http://localhost:32400',
                    'token': 'your-plex-token',
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
                },
                # Webhook configuration
                'webhooks': {
                    # Event triggered when an episode is marked as watched
                    'after-watched': [
                        'download-next --count 2 --execute',
                        'delete-watched --days 0 --execute'
                    ],
                    # Event triggered when playback starts
                    'on-play': [],
                    # Event triggered when playback stops
                    'on-stop': [],
                    # Event triggered when new content is added to library
                    'on-added': []
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
