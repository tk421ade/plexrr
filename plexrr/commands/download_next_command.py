import click
import logging
from typing import Dict, List

from ..services.plex_service import PlexService
from ..services.sonarr_service import SonarrService
from ..utils.config_loader import get_config

@click.command(name='download-next')
@click.option('--show-id', help='Optional Plex ID of the show to get next episodes for (all shows if not specified)')
@click.option('--count', type=int, default=1, help='Number of next episodes to download for each show')
@click.option('--quality-profile', type=int, help='Quality profile ID to use when requesting downloads')
@click.option('--confirm', is_flag=True, help='Request downloads in Sonarr with confirmation')
@click.option('--verbose', is_flag=True, help='Enable verbose debug output')
def download_next_episodes(show_id, count, quality_profile, confirm, verbose):
    """Find and suggest next episodes to download for shows you're watching.

    This command analyzes your Plex library to find shows you've been watching and
    suggests the next episodes to download. It will prioritize shows that are in progress
    and only suggest episodes that are not already available in your Plex library.

    By default, it suggests the specified number of episodes (--count) that follow
    episodes you've watched or that are in progress for each show. The command will
    display what will be downloaded by default, and only proceed to request the
    downloads to Sonarr when --confirm flag is used along with a --quality-profile.

    If a show ID is provided, only that specific show will be analyzed.
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

        # Initialize Sonarr service (we'll need it if confirm is provided)
        sonarr_service = None
        if confirm:
            if 'sonarr' not in config:
                click.echo("Error: Sonarr configuration not found. Add sonarr section to your config.yml", err=True)
                return
            if not quality_profile:
                click.echo("Error: --quality-profile is required when using --confirm", err=True)
                return
            click.echo("Initializing Sonarr service...")
            sonarr_service = SonarrService(config['sonarr'])

        # Get next episodes to download
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

                # Request download if confirm is enabled and we have a quality profile
                if confirm and sonarr_service and quality_profile:
                    # Find the show in Sonarr
                    sonarr_show = sonarr_service.find_show_by_title(show_title)

                    # If the show doesn't exist in Sonarr, add it
                    if not sonarr_show:
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
                            download_failed += 1
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
        if confirm and sonarr_service and quality_profile:
            click.echo(f"\nDownload summary:")
            click.echo(f"- {download_requested} episodes requested successfully")
            if download_failed > 0:
                click.echo(f"- {download_failed} episodes failed")
        else:
            # Add instructions for actually downloading the episodes
            click.echo("\nTo request these downloads in Sonarr:")
            click.echo(f"  Run this command with --confirm --quality-profile <ID>")

        if verbose:
            logger.debug("Next episodes search completed successfully")

    except Exception as e:
        error_msg = f"Error: {str(e)}"
        click.echo(error_msg, err=True)
        if verbose:
            logger.exception("Detailed error information:")
