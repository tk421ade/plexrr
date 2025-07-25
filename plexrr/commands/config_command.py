import click
import os
from pathlib import Path
from ..utils.config_loader import create_default_config, get_config

# Make sure the name is explicitly set and the command is properly exported
@click.group(name='config')
def config_group():
    """Commands for managing PlexRR configuration"""
    pass

@config_group.command(name='create')
@click.option('--path', help='Path where the config file should be created')
def create_config(path):
    """Create a default configuration file"""
    path_obj = Path(path) if path else None
    result = create_default_config(path_obj)
    if result:
        click.echo(f"Configuration template created successfully at {result}")

@config_group.command(name='validate')
def validate_config():
    """Validate the current configuration file"""
    try:
        config = get_config()
        click.echo("Configuration is valid.")

        # Show configuration summary
        click.echo("\nConfiguration summary:")
        click.echo(f" - Plex server: {config['plex']['base_url']}")
        click.echo(f" - Radarr server: {config['radarr']['base_url']}")

        if 'sonarr' in config:
            click.echo(f" - Sonarr server: {config['sonarr']['base_url']}")
        else:
            click.echo(" - Sonarr: Not configured")

        if 'watchlist_rss' in config['plex']:
            click.echo(" - Plex Watchlist: Using RSS feed")
        elif 'username' in config['plex'] and 'password' in config['plex']:
            click.echo(" - Plex Watchlist: Using username/password")
        else:
            click.echo(" - Plex Watchlist: Not configured")

    except Exception as e:
        click.echo(f"Configuration error: {str(e)}", err=True)
        click.echo("\nRun 'plexrr config create' to generate a template configuration file.")
