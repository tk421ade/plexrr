import click
import logging
import json
from tabulate import tabulate
from ..services.radarr_service import RadarrService
from ..utils.config_loader import get_config

@click.command(name='profiles')
@click.option('--verbose', is_flag=True, help='Enable verbose debug output')
def list_profiles(verbose):
    """List all quality profiles available in Radarr"""
    try:
        # Configure logging based on verbose flag
        log_level = logging.DEBUG if verbose else logging.INFO
        logging.basicConfig(level=log_level, format='%(levelname)s: %(message)s')
        logger = logging.getLogger('plexrr')

        if verbose:
            logger.debug("Verbose mode enabled")

        config = get_config()

        # Initialize Radarr service
        click.echo("Connecting to Radarr...")
        radarr_service = RadarrService(config['radarr'])

        # Fetch quality profiles
        click.echo("Fetching quality profiles...")
        if verbose:
            logger.debug(f"Requesting quality profiles from Radarr API")
        profiles = radarr_service.get_quality_profiles()
        if verbose:
            logger.debug(f"Received {len(profiles)} profiles from API")
            logger.debug(f"Profiles data: {json.dumps(profiles, default=str)[:1000]}..." if profiles else "No profiles data")

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
        error_msg = f"Error: {str(e)}"
        click.echo(error_msg, err=True)
        if verbose:
            logger.exception("Detailed error information:")
