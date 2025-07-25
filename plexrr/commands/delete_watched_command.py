import click
import logging
from typing import Dict

from ..services.plex_service import PlexService
from ..utils.config_loader import get_config

@click.command(name='delete-watched')
@click.option('--show-id', help='Optional Plex ID of the show to delete episodes from (all shows if not specified)')
@click.option('--days', type=int, help='Only delete episodes watched more than X days ago')
@click.option('--skip-pilots', is_flag=True, help='Skip pilot episodes (S01E01) when deleting')
@click.option('--confirm', is_flag=True, help='Prompt for confirmation before each deletion')
@click.option('--verbose', is_flag=True, help='Enable verbose debug output')
def delete_watched_episodes(show_id, days, skip_pilots, confirm, verbose):
    """Delete watched episodes from Plex.

    This command will delete all watched episodes from Plex. If a show ID is provided,
    only episodes from that show will be deleted. Use the --days option to only delete
    episodes watched more than X days ago. Use the --skip-pilots flag to preserve the
    first episode of each series. Use the --confirm flag to get a confirmation prompt
    before each deletion.
    """
    try:
        # Configure logging based on verbose flag
        log_level = logging.DEBUG if verbose else logging.INFO
        logging.basicConfig(level=log_level, format='%(levelname)s: %(message)s')
        logger = logging.getLogger('plexrr')

        if verbose:
            logger.debug("Verbose mode enabled")

        config = get_config()

        # Initialize Plex service
        click.echo("Initializing Plex service...")
        plex_service = PlexService(config['plex'])

        # Delete watched episodes
        click.echo("Searching for watched episodes...")
        results = plex_service.delete_watched_episodes(show_id, confirm, days, skip_pilots)

        # Summary
        click.echo(f"\nDeletion completed:")
        click.echo(f"- {results['deleted']} episodes deleted")
        click.echo(f"- {results['skipped']} episodes skipped")

        if verbose:
            logger.debug("Deletion process completed successfully")

    except Exception as e:
        error_msg = f"Error: {str(e)}"
        click.echo(error_msg, err=True)
        if verbose:
            logger.exception("Detailed error information:")
