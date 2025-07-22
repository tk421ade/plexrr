import click
import time
import json
import logging
from typing import List

from ..services.plex_service import PlexService
from ..services.radarr_service import RadarrService
from ..services.merger_service import merge_movies
from ..models.movie import Movie, Availability
from ..utils.config_loader import get_config

@click.command(name='sync')
@click.option('--quality-profile', required=True, type=int, help='Quality profile ID to use (run "profiles" command to see available options)')
@click.option('--dry-run', is_flag=True, help='Show what would be done without making changes')
@click.option('--confirm', is_flag=True, help='Prompt for confirmation before each action')
@click.option('--verbose', is_flag=True, help='Enable verbose debug output')
def sync_movies(quality_profile, dry_run, confirm, verbose):
    """Sync movies from Plex to Radarr (add Plex movies to Radarr)"""
    try:
        # Configure logging based on verbose flag
        log_level = logging.DEBUG if verbose else logging.INFO
        logging.basicConfig(level=log_level, format='%(levelname)s: %(message)s')
        logger = logging.getLogger('plexrr')

        if verbose:
            logger.debug("Verbose mode enabled")

        config = get_config()

        if verbose:
            logger.debug(f"Using quality profile ID: {quality_profile}")

        # Initialize services
        click.echo("Initializing services...")
        plex_service = PlexService(config['plex'])
        radarr_service = RadarrService(config['radarr'])

        # Verify Radarr root folders
        if verbose:
            logger.debug("Checking Radarr root folders")
        try:
            root_folders = radarr_service.get_root_folders()
            if not root_folders:
                click.echo("Error: No root folders found in Radarr. Please configure at least one root folder.")
                return
            if verbose:
                logger.debug(f"Found {len(root_folders)} root folders. Will use: {root_folders[0]['path']}")
        except Exception as e:
            click.echo(f"Error checking Radarr root folders: {str(e)}")
            return

        # Get movies from both services
        click.echo("Fetching movies from Plex...")
        plex_movies = plex_service.get_movies()
        click.echo(f"Found {len(plex_movies)} movies in Plex")

        plex_watchlist = plex_service.get_watchlist()
        click.echo(f"Found {len(plex_watchlist)} movies in Plex Watchlist")

        click.echo("Fetching movies from Radarr...")
        radarr_movies = radarr_service.get_movies()
        click.echo(f"Found {len(radarr_movies)} movies in Radarr")

        # Merge the results
        click.echo("Merging results...")
        all_movies = merge_movies(plex_movies, radarr_movies, plex_watchlist)

        # Find movies only in Plex (not in Radarr)
        plex_only_movies = [m for m in all_movies if m.availability == Availability.PLEX]

        if not plex_only_movies:
            click.echo("No movies found that are only in Plex. Nothing to sync.")
            return

        click.echo(f"Found {len(plex_only_movies)} movies that exist in Plex but not in Radarr.")

        # Check if dry run and show what would be done
        if dry_run:
            click.echo("DRY RUN MODE - No changes will be made")
            click.echo("The following movies would be added to Radarr:")
            for idx, movie in enumerate(plex_only_movies, 1):
                click.echo(f"{idx}. {movie.title}")
                if movie.tmdb_id:
                    click.echo(f"   TMDB ID: {movie.tmdb_id}")
                if movie.imdb_id:
                    click.echo(f"   IMDB ID: {movie.imdb_id}")
            return

        # Process each movie that needs to be added to Radarr
        click.echo("Starting sync process...")
        added_count = 0
        skipped_count = 0

        for movie in plex_only_movies:
            action_message = f"Adding movie to Radarr: {movie.title}"
            if movie.tmdb_id:
                action_message += f" (TMDB ID: {movie.tmdb_id})"
            elif movie.imdb_id:
                action_message += f" (IMDB ID: {movie.imdb_id})"

            # If confirmation is required, ask user
            if confirm:
                if not click.confirm(f"{action_message}. Proceed?", default=True):
                    click.echo("Skipped.")
                    skipped_count += 1
                    continue
            else:
                click.echo(action_message)

            # Add the movie to Radarr using the service
            try:
                # Attempt to add the movie to Radarr
                response = radarr_service.add_movie(movie, quality_profile)
                added_count += 1
                click.echo(f"Successfully added {movie.title} to Radarr")
            except Exception as e:
                error_msg = f"Error adding {movie.title} to Radarr: {str(e)}"
                click.echo(error_msg, err=True)
                if verbose:
                    logger.exception("Detailed error information:")

        # Summary
        click.echo(f"\nSync completed:")
        click.echo(f"- {added_count} movies added to Radarr")
        click.echo(f"- {skipped_count} movies skipped")

        if verbose:
            logger.debug("Sync process completed successfully")

    except Exception as e:
        error_msg = f"Error: {str(e)}"
        click.echo(error_msg, err=True)
        if verbose:
            logger.exception("Detailed error information:")
