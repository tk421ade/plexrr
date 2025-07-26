import click
import json

def print_config_debug(config):
    """Print detailed debug information about the configuration"""
    click.echo("\n===== DEBUG: Configuration Details =====")

    # Show which config file is being used
    if '_config_path' in config:
        click.echo(f"\nConfiguration file: {config['_config_path']}")

    # Print all sections and keys
    click.echo("\nConfiguration sections:")
    for section, values in config.items():
        # Skip the _config_path key as it's a special metadata field, not a section
        if section == '_config_path':
            continue

        click.echo(f"- {section}")
        if not isinstance(values, dict):
            click.echo(f"  Warning: Expected dictionary for section {section}, got {type(values)}")
            continue

        for key, value in values.items():
            # Mask sensitive values
            if key in ['token', 'api_key', 'password']:
                display_val = '********' if value else '[empty]'
            else:
                if isinstance(value, list):
                    display_val = f"[{', '.join(repr(v) for v in value)}]"
                elif isinstance(value, dict):
                    display_val = json.dumps(value, indent=2)
                else:
                    display_val = value
            click.echo(f"  - {key}: {display_val}")

    # Special focus on webhooks section
    if 'webhooks' in config:
        click.echo("\nWebhooks Detail:")
        webhook_config = config['webhooks']
        if not webhook_config:
            click.echo("  [Empty webhooks section]")
        else:
            for event, commands in webhook_config.items():
                click.echo(f"  Event: {event}")
                if isinstance(commands, list):
                    if not commands:
                        click.echo("    [No commands]")
                    else:
                        for i, cmd in enumerate(commands, 1):
                            click.echo(f"    {i}. {cmd}")
                elif isinstance(commands, str):
                    if not commands.strip():
                        click.echo("    [No commands]")
                    else:
                        cmds = [cmd.strip() for cmd in commands.split(',')]
                        for i, cmd in enumerate(cmds, 1):
                            if cmd:
                                click.echo(f"    {i}. {cmd}")
                else:
                    click.echo(f"    Unexpected type: {type(commands)}")

    click.echo("\n===== END DEBUG =====")
