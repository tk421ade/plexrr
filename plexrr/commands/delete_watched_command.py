import click
import logging
import humanize
from typing import Dict

from ..services.plex_service import PlexService
from ..utils.config_loader import get_config

@click.command(name='delete-watched')
@click.option('--show-id', help='Optional Plex ID of the show to delete episodes from (all shows if not specified)')
@click.option('--days', type=int, default=10, help='Only delete episodes watched more than X days ago (default: 10)')
@click.option('--skip-pilots', is_flag=True, help='Skip pilot episodes (S01E01) when deleting')
@click.option('--confirm', is_flag=True, help='Prompt for confirmation before each deletion')
@click.option('--execute', is_flag=True, help='Actually perform deletions (without this flag, only shows what would be deleted)')
@click.option('--verbose', is_flag=True, help='Enable verbose debug output')
def delete_watched_episodes(show_id, days, skip_pilots, confirm, execute, verbose):
    """Find and optionally delete watched episodes from Plex.

    This command will find watched episodes in Plex that match the specified criteria.
    By default, it only displays what would be deleted. Use --execute to actually delete episodes.

    If a show ID is provided, only episodes from that show will be processed.
    Episodes watched more than 10 days ago will be processed by default (use --days to change).
    Use --skip-pilots to preserve the first episode (S01E01) of each series.
    Use --confirm with --execute for a confirmation prompt before each deletion.
    Use --verbose to see detailed information, including shows with no eligible episodes.
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

        # Find and optionally delete watched episodes
        click.echo("Searching for watched episodes...")
        results = plex_service.delete_watched_episodes(show_id, confirm, days, skip_pilots, execute, verbose)

        # Show a summary only if there's something worth reporting
        if results['deleted'] > 0 or results['skipped'] > 0:
            action = "Deleted" if execute else "Would delete"
            click.echo(f"\nOperation completed:")
            click.echo(f"- {results['deleted']} episodes {action.lower()}")
            click.echo(f"- Total size: {humanize.naturalsize(results['total_size'])}")
            if results['skipped'] > 0:
                click.echo(f"- {results['skipped']} episodes skipped")

            if not execute and results['deleted'] > 0:
                click.echo("\nThis was a dry run. Use --execute to actually delete these episodes.")
        else:
            click.echo("\nNo eligible episodes found to delete.")
            if verbose:
                click.echo("Try adjusting your criteria (--days, --skip-pilots) or check if episodes are marked as watched in Plex.")

        if verbose:
            logger.debug("Deletion process completed successfully")

    except Exception as e:
        error_msg = f"Error: {str(e)}"
        click.echo(error_msg, err=True)
        if verbose:
            logger.exception("Detailed error information:")
