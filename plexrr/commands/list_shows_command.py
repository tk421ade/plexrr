import click
import logging
from tabulate import tabulate
from typing import List, Dict, Optional

from ..services.plex_service import PlexService
from ..utils.config_loader import get_config

@click.command(name='shows')
@click.option('--search', help='Search for shows matching this title')
@click.option('--verbose', is_flag=True, help='Enable verbose debug output')
def list_shows(search, verbose):
    """List all TV shows in your Plex library with their IDs.

    This command displays all TV shows in your Plex library along with their
    Plex IDs, which can be used with other commands like 'download-next'.

    Use the --search option to filter shows by title.
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
        click.echo("Connecting to Plex...")
        plex_service = PlexService(config['plex'])

        # Get TV shows from Plex
        shows = []

        # Find all show library sections
        show_sections = [section for section in plex_service.server.library.sections() if section.type == 'show']

        if not show_sections:
            click.echo("No TV show libraries found in Plex")
            return

        # Get all shows from each section
        for section in show_sections:
            for plex_show in section.all():
                # Skip if searching and title doesn't match
                if search and search.lower() not in plex_show.title.lower():
                    continue

                # Get episode counts
                total_episodes = len(plex_show.episodes()) if hasattr(plex_show, 'episodes') else 0
                watched_episodes = plex_show.viewedLeafCount if hasattr(plex_show, 'viewedLeafCount') else 0

                shows.append({
                    'id': plex_show.ratingKey,
                    'title': plex_show.title,
                    'year': plex_show.year if hasattr(plex_show, 'year') else None,
                    'seasons': len(plex_show.seasons()) if hasattr(plex_show, 'seasons') else 0,
                    'episodes': total_episodes,
                    'watched': watched_episodes,
                    'progress': f"{watched_episodes}/{total_episodes}" if total_episodes > 0 else "0/0"
                })

        if not shows:
            if search:
                click.echo(f"No shows found matching '{search}'")
            else:
                click.echo("No shows found in your Plex library")
            return

        # Sort shows by title
        shows.sort(key=lambda x: x['title'])

        # Display shows in a table
        headers = ['ID', 'Title', 'Year', 'Seasons', 'Progress']
        table = [
            [show['id'], show['title'], show['year'] or 'N/A', show['seasons'], show['progress']]
            for show in shows
        ]

        click.echo(f"\nFound {len(shows)} TV shows:")
        click.echo(tabulate(table, headers=headers, tablefmt='grid'))

        # Add usage information
        click.echo("\nUse the ID with 'download-next' command:")
        click.echo("Example: ./venv/bin/python -m plexrr.cli download-next --show-id ID --count 2")

    except Exception as e:
        error_msg = f"Error: {str(e)}"
        click.echo(error_msg, err=True)
        if verbose:
            logger.exception("Detailed error information:")
