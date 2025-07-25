import click
import logging
import json
from tabulate import tabulate
from ..services.radarr_service import RadarrService
from ..services.sonarr_service import SonarrService
from ..utils.config_loader import get_config

@click.command(name='profiles')
@click.option('--verbose', is_flag=True, help='Enable verbose debug output')
@click.option('--service', type=click.Choice(['radarr', 'sonarr']), default='radarr',
              help='Service to fetch profiles from (radarr/sonarr)')
def list_profiles(verbose, service):
    """List all quality profiles available in Radarr or Sonarr"""
    try:
        # Configure logging based on verbose flag
        log_level = logging.DEBUG if verbose else logging.INFO
        logging.basicConfig(level=log_level, format='%(levelname)s: %(message)s')
        logger = logging.getLogger('plexrr')

        if verbose:
            logger.debug(f"Verbose mode enabled, using {service} service")

        config = get_config()

        # Check if the requested service is configured
        if service not in config:
            click.echo(f"Error: {service.capitalize()} is not configured in your config file.", err=True)
            return

        # Initialize the appropriate service
        if service == 'radarr':
            click.echo("Connecting to Radarr...")
            service_obj = RadarrService(config['radarr'])
        else:  # sonarr
            click.echo("Connecting to Sonarr...")
            service_obj = SonarrService(config['sonarr'])

        # Fetch quality profiles
        click.echo("Fetching quality profiles...")
        if verbose:
            logger.debug(f"Requesting quality profiles from {service.capitalize()} API")
        profiles = service_obj.get_quality_profiles()
        if verbose:
            logger.debug(f"Received {len(profiles)} profiles from API")
            logger.debug(f"Profiles data: {json.dumps(profiles, default=str)[:1000]}..." if profiles else "No profiles data")

        if not profiles:
            click.echo(f"No quality profiles found in {service.capitalize()}.")
            return

        click.echo(f"Found {len(profiles)} quality profiles in {service.capitalize()}.")

        # Display profiles in a table
        headers = ['ID', 'Name']
        table = [[
            profile.get('id', 'N/A'),
            profile.get('name', 'N/A')
        ] for profile in profiles]

        click.echo(tabulate(table, headers=headers, tablefmt='grid'))

        # Show appropriate usage message based on service
        if service == 'radarr':
            click.echo("\nUse these profile IDs with the 'sync' command using the --quality-profile option.")
        else:  # sonarr
            click.echo("\nUse these profile IDs with the 'download-next' command using the --quality-profile option.")

    except Exception as e:
        error_msg = f"Error: {str(e)}"
        click.echo(error_msg, err=True)
        if verbose:
            logger.exception("Detailed error information:")
