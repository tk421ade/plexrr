import click
import os
from pathlib import Path
from ..utils.config_loader import create_default_config, get_config
from ..utils.debug import print_config_debug

# Make sure the name is explicitly set and the command is properly exported
@click.group(name='config')
def config_group():
    """Commands for managing PlexRR configuration"""
    pass

@config_group.command(name='create')
@click.option('--path', help='Path where the config file should be created')
def create_config(path):
    """Create a default configuration file"""
    # Suggest YAML format if user specified INI
    if path and path.lower().endswith('.ini'):
        if not click.confirm("INI format is deprecated. Would you like to use YAML format instead?", default=True):
            click.echo("Using INI format as requested.")
        else:
            # Change extension to .yml
            path = path[:-4] + '.yml'
            click.echo(f"Using YAML format: {path}")

    path_obj = Path(path) if path else None
    result = create_default_config(path_obj)
    if result:
        click.echo(f"Configuration template created successfully at {result}")

@config_group.command(name='validate')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed config information')
def validate_config(verbose):
    """Validate the current configuration file"""
    try:
        verbose_output = verbose
        config = get_config()

        # Print debug information if verbose mode is enabled
        if verbose_output:
            print_config_debug(config)
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

        # Show webhook configuration status
        # More thorough check for webhook config
        has_webhooks = False

        # Show where the configuration file was loaded from
        if '_config_path' in config:
            click.echo(f"\nLoaded configuration from: {config['_config_path']}")

        if 'webhooks' in config:
            click.echo("\nWebhooks configuration:")

            # Always show raw webhook configuration in verbose mode
            if verbose_output:
                click.echo("\nRaw webhook configuration:")
                if not config['webhooks']:
                    click.echo("  [Empty webhooks section]")
                else:
                    for event, commands in config['webhooks'].items():
                        # Skip non-webhook keys that might have been added
                        if event.startswith('_'):
                            continue

                        click.echo(f"  Event: {event}")
                        if isinstance(commands, list):
                            for cmd in commands:
                                click.echo(f"    - {cmd}")
                        else:
                            click.echo(f"    Value: {commands}")
            webhook_events = config['webhooks']
            configured_events = []

            # Debug the actual webhook configuration
            if verbose_output:
                click.echo("\nRaw webhook configuration:")
                click.echo(webhook_events)

            # Make sure webhook_events is a dictionary
            if not isinstance(webhook_events, dict):
                click.echo(f"  Warning: Expected webhooks to be a dictionary, got {type(webhook_events)}")
            else:
                for event, commands in webhook_events.items():
                    # Skip special metadata keys
                    if event.startswith('_'):
                        continue

                    # Check for both list and string command formats
                    has_commands = False
                    cmd_count = 0

                    if isinstance(commands, list) and commands:
                        has_commands = True
                        cmd_count = len(commands)
                    elif isinstance(commands, str) and commands.strip():
                        # Split by commas and count non-empty commands
                        cmds = [cmd.strip() for cmd in commands.split(',')]
                        if any(cmds):
                            has_commands = True
                            cmd_count = len([cmd for cmd in cmds if cmd])

                    if has_commands:
                        configured_events.append((event, cmd_count))
                        has_webhooks = True

            if configured_events:
                click.echo(f" - Status: {len(configured_events)} event(s) configured")
                click.echo(" - Configured events:")
                for event, cmd_count in configured_events:
                    click.echo(f"   * {event}: {cmd_count} command(s)")
            else:
                click.echo(" - Status: No webhook events configured")
        else:
            click.echo("\nWebhooks: Not configured")

    except Exception as e:
        click.echo(f"Configuration error: {str(e)}", err=True)
        click.echo("\nRun 'plexrr config create' to generate a template configuration file.")
