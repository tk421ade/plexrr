import click
from tabulate import tabulate
from ..services.radarr_service import RadarrService
from ..utils.config_loader import get_config

@click.command(name='profiles')
def list_profiles():
    """List all quality profiles available in Radarr"""
    try:
        config = get_config()

        # Initialize Radarr service
        click.echo("Connecting to Radarr...")
        radarr_service = RadarrService(config['radarr'])

        # Fetch quality profiles
        click.echo("Fetching quality profiles...")
        profiles = radarr_service.get_quality_profiles()

        if not profiles:
            click.echo("No quality profiles found in Radarr.")
            return

        click.echo(f"Found {len(profiles)} quality profiles.")

        # Display profiles in a table
        headers = ['ID', 'Name']
        table = [[
            profile['id'],
            profile['name']
        ] for profile in profiles]

        click.echo(tabulate(table, headers=headers, tablefmt='grid'))
        click.echo("\nUse these profile IDs with the 'sync' command using the --quality-profile option.")

    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
