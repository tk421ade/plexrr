import click
from ..services.sonarr_service import SonarrService
from ..utils.config_loader import get_config
from tabulate import tabulate
import logging
import json

@click.group(name='sonarr')
def sonarr_group():
    """Commands for interacting with Sonarr"""
    pass

@sonarr_group.command(name='profiles')
@click.option('--verbose', is_flag=True, help='Enable verbose debug output')
def list_sonarr_profiles(verbose):
    """List all quality profiles available in Sonarr"""
    try:
        # Configure logging based on verbose flag
        log_level = logging.DEBUG if verbose else logging.INFO
        logging.basicConfig(level=log_level, format='%(levelname)s: %(message)s')
        logger = logging.getLogger('plexrr')

        if verbose:
            logger.debug("Verbose mode enabled")

        config = get_config()

        # Check if Sonarr is configured
        if 'sonarr' not in config:
            click.echo("Error: Sonarr is not configured in your config file.", err=True)
            return

        # Initialize Sonarr service
        click.echo("Connecting to Sonarr...")
        sonarr_service = SonarrService(config['sonarr'])

        # Fetch quality profiles
        click.echo("Fetching quality profiles...")
        if verbose:
            logger.debug(f"Requesting quality profiles from Sonarr API")
        profiles = sonarr_service.get_quality_profiles()
        if verbose:
            logger.debug(f"Received {len(profiles)} quality profiles from API")
            logger.debug(f"Profiles data: {json.dumps(profiles, default=str)}")

        if not profiles:
            click.echo("No quality profiles found in Sonarr.")
            return

        click.echo(f"Found {len(profiles)} quality profiles in Sonarr.")

        # Display profiles in a table
        headers = ['ID', 'Name']
        table = [[
            profile.get('id', 'N/A'),
            profile.get('name', 'N/A')
        ] for profile in profiles]

        click.echo(tabulate(table, headers=headers, tablefmt='grid'))
        click.echo("\nUse the ID when syncing TV shows with Sonarr.")

    except Exception as e:
        error_msg = f"Error: {str(e)}"
        click.echo(error_msg, err=True)
        if verbose:
            logger.exception("Detailed error information:")

@sonarr_group.command(name='folders')
@click.option('--verbose', is_flag=True, help='Enable verbose debug output')
def list_sonarr_folders(verbose):
    """List all root folders available in Sonarr"""
    try:
        # Configure logging based on verbose flag
        log_level = logging.DEBUG if verbose else logging.INFO
        logging.basicConfig(level=log_level, format='%(levelname)s: %(message)s')
        logger = logging.getLogger('plexrr')

        if verbose:
            logger.debug("Verbose mode enabled")

        config = get_config()

        # Check if Sonarr is configured
        if 'sonarr' not in config:
            click.echo("Error: Sonarr is not configured in your config file.", err=True)
            return

        # Initialize Sonarr service
        click.echo("Connecting to Sonarr...")
        sonarr_service = SonarrService(config['sonarr'])

        # Fetch root folders
        click.echo("Fetching root folders...")
        if verbose:
            logger.debug(f"Requesting root folders from Sonarr API")
        folders = sonarr_service.get_root_folders()
        if verbose:
            logger.debug(f"Received {len(folders)} root folders from API")
            logger.debug(f"Folders data: {json.dumps(folders, default=str)}")

        if not folders:
            click.echo("No root folders found in Sonarr.")
            return

        click.echo(f"Found {len(folders)} root folders in Sonarr.")

        # Display folders in a table
        headers = ['ID', 'Path', 'Free Space']
        table = [[
            folder.get('id', 'N/A'),
            folder.get('path', 'N/A'),
            f"{folder.get('freeSpace', 0) / (1024**3):.2f} GB" if 'freeSpace' in folder else 'N/A'
        ] for folder in folders]

        click.echo(tabulate(table, headers=headers, tablefmt='grid'))
        click.echo("\nThe first root folder will be used automatically by the 'sync' command.")

    except Exception as e:
        error_msg = f"Error: {str(e)}"
        click.echo(error_msg, err=True)
        if verbose:
            logger.exception("Detailed error information:")
