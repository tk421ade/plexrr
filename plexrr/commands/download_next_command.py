import click
import logging
from typing import Dict, List

from ..services.plex_service import PlexService
from ..services.sonarr_service import SonarrService
from ..utils.config_loader import get_config

@click.command(name='download-next')
@click.option('--show-id', help='Optional Plex ID of the show to get next episodes for (all shows if not specified)')
@click.option('--count', type=int, default=1, help='Number of next episodes to download for each show')
@click.option('--request', is_flag=True, help='Request downloads in Sonarr for the next episodes')
@click.option('--quality-profile', type=int, help='Quality profile ID to use when adding shows to Sonarr')
@click.option('--confirm', is_flag=True, help='Prompt for confirmation before requesting downloads')
@click.option('--verbose', is_flag=True, help='Enable verbose debug output')
def download_next_episodes(show_id, count, request, quality_profile, confirm, verbose):
    """Find next episodes to download for shows you're watching.

    This command will analyze your Plex library to find shows you've been watching
    and suggest the next episodes to download. By default, it suggests 1 episode
    per show, but you can specify more with the --count option.

    If a show ID is provided, only that specific show will be analyzed.

    Use the --request flag to automatically request downloads through Sonarr.
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

        # Initialize Sonarr service if we're requesting downloads
        sonarr_service = None
        if request:
            if 'sonarr' not in config:
                click.echo("Error: Sonarr configuration not found. Add sonarr section to your config.yml", err=True)
                return
            click.echo("Initializing Sonarr service...")
            sonarr_service = SonarrService(config['sonarr'])

        # Get next episodes
        click.echo(f"Finding next episodes to download (max {count} per show)...")
        next_episodes = plex_service.get_next_episodes(show_id, count)

        if not next_episodes:
            click.echo("No next episodes found to download.")
            return

        # Display results
        click.echo(f"\nFound next episodes for {len(next_episodes)} shows:")

        download_requested = 0
        download_failed = 0

        for show_title, episodes in next_episodes.items():
            click.echo(f"\n{show_title}:")

            for i, episode in enumerate(episodes, 1):
                episode_info = f"S{episode['season']:02d}E{episode['episode']:02d} - {episode['title']}"
                click.echo(f"  {i}. {episode_info}")

                # Show summary if available and in verbose mode
                if verbose and episode['summary']:
                    summary = episode['summary'].replace('\n', ' ').strip()
                    if len(summary) > 100:
                        summary = summary[:97] + '...'
                    click.echo(f"     {summary}")

                # Request download if enabled
                if request and sonarr_service:
                    # Check if we should confirm this download
                    proceed = True
                    if confirm:
                        proceed = click.confirm(f"    Request download for {episode_info}?")

                    if proceed:
                        # Find the show in Sonarr
                        sonarr_show = sonarr_service.find_show_by_title(show_title)

                        # If the show doesn't exist in Sonarr and we have a quality profile, add it
                        if not sonarr_show and quality_profile:
                            click.echo(f"    Adding {show_title} to Sonarr...")
                            try:
                                from ..models.tvshow import TVShow
                                from ..models.movie import Availability

                                # Create a basic TVShow object with just the title
                                show_to_add = TVShow(
                                    title=show_title,
                                    availability=Availability.PLEX
                                )

                                # Add the show to Sonarr
                                sonarr_show = sonarr_service.add_show(show_to_add, quality_profile)
                            except Exception as e:
                                click.echo(f"    Error adding show to Sonarr: {str(e)}")
                                continue

                        # If we have the show in Sonarr, request the episode download
                        if sonarr_show:
                            series_id = sonarr_show.get('id') if isinstance(sonarr_show, dict) else sonarr_show.id
                            click.echo(f"    Requesting download for {episode_info}...")
                            success = sonarr_service.request_episode_download(
                                series_id, 
                                episode['season'], 
                                episode['episode']
                            )

                            if success:
                                click.echo(f"    Download requested successfully")
                                download_requested += 1
                            else:
                                click.echo(f"    Failed to request download")
                                download_failed += 1
                        else:
                            click.echo(f"    Show not found in Sonarr and could not be added")
                            download_failed += 1

        # Show download summary if we requested any
        if request and sonarr_service:
            click.echo(f"\nDownload summary:")
            click.echo(f"- {download_requested} episodes requested successfully")
            if download_failed > 0:
                click.echo(f"- {download_failed} episodes failed")
        else:
            # Add instructions for integrating with download systems
            click.echo("\nTo download these episodes, you can:")
            click.echo("1. Run this command with --request to download through Sonarr")
            click.echo("2. Manually search for them in your preferred download client")

        if verbose:
            logger.debug("Next episodes search completed successfully")

    except Exception as e:
        error_msg = f"Error: {str(e)}"
        click.echo(error_msg, err=True)
        if verbose:
            logger.exception("Detailed error information:")
