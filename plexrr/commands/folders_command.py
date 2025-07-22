import click
import logging
import json
from tabulate import tabulate
from ..services.radarr_service import RadarrService
from ..utils.config_loader import get_config

@click.command(name='folders')
@click.option('--verbose', is_flag=True, help='Enable verbose debug output')
def list_folders(verbose):
    """List all root folders available in Radarr"""
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

        # Fetch root folders
        click.echo("Fetching root folders...")
        if verbose:
            logger.debug(f"Requesting root folders from Radarr API")
        folders = radarr_service.get_root_folders()
        if verbose:
            logger.debug(f"Received {len(folders)} root folders from API")
            logger.debug(f"Folders data: {json.dumps(folders, default=str)}")

        if not folders:
            click.echo("No root folders found in Radarr.")
            return

        click.echo(f"Found {len(folders)} root folders.")

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
