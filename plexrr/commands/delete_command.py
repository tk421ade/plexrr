import click
import logging
import json
import time
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from tabulate import tabulate

from ..services.plex_service import PlexService
from ..services.radarr_service import RadarrService
from ..services.merger_service import merge_movies
from ..models.movie import Movie, Availability, WatchStatus
from ..utils.config_loader import get_config

@click.command(name='delete')
@click.option('--has-size', is_flag=True, help='Only include movies with file size')
@click.option('--no-size', is_flag=True, help='Only include movies without file size')
@click.option('--days', type=int, help='Only include movies older than X days')
@click.option('--watchlist', is_flag=True, help='Only include movies in watchlist')
@click.option('--no-watchlist', is_flag=True, help='Only include movies not in watchlist')
@click.option('--availability', type=click.Choice(['plex', 'radarr', 'both']), help='Filter by availability')
@click.option('--status', type=click.Choice(['watched', 'in_progress', 'not_watched']), help='Filter by watch status')
@click.option('--tag', help='Filter by tag')
@click.option('--confirm', is_flag=True, help='Prompt for confirmation before each deletion')
@click.option('--execute', is_flag=True, help='Actually perform deletions (without this flag, only shows what would be deleted)')
@click.option('--verbose', is_flag=True, help='Enable verbose debug output')
def delete_movies(has_size, no_size, days, watchlist, no_watchlist, availability, status, tag, confirm, execute, verbose):
    """Delete movies from Radarr based on filters.

    By default, this command only lists what would be deleted. Use --execute to actually delete movies.
    """
    try:
        # Configure logging based on verbose flag
        log_level = logging.DEBUG if verbose else logging.INFO
        logging.basicConfig(level=log_level, format='%(levelname)s: %(message)s')
        logger = logging.getLogger('plexrr')

        if verbose:
            logger.debug("Verbose mode enabled")

        # Validate conflicting options
        if has_size and no_size:
            click.echo("Error: --has-size and --no-size cannot be used together", err=True)
            return

        if watchlist and no_watchlist:
            click.echo("Error: --watchlist and --no-watchlist cannot be used together", err=True)
            return

        config = get_config()

        # Initialize services
        click.echo("Initializing services...")
        plex_service = PlexService(config['plex'])
        radarr_service = RadarrService(config['radarr'])

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

        # Apply filters
        filtered_movies = all_movies

        # We only care about movies that are in Radarr (otherwise we can't delete them)
        filtered_movies = [m for m in filtered_movies if m.availability in [Availability.RADARR, Availability.BOTH]]

        if has_size:
            filtered_movies = [m for m in filtered_movies if m.file_size]

        if no_size:
            filtered_movies = [m for m in filtered_movies if not m.file_size]

        if days:
            cutoff_date = datetime.now() - timedelta(days=days)
            filtered_movies = [m for m in filtered_movies if m.added_date and m.added_date < cutoff_date]

        if watchlist:
            filtered_movies = [m for m in filtered_movies if m.in_watchlist]

        if no_watchlist:
            filtered_movies = [m for m in filtered_movies if not m.in_watchlist]

        if availability:
            if availability == 'plex':
                filtered_movies = [m for m in filtered_movies if m.availability == Availability.BOTH]
            elif availability == 'radarr':
                filtered_movies = [m for m in filtered_movies if m.availability == Availability.RADARR]
            elif availability == 'both':
                filtered_movies = [m for m in filtered_movies if m.availability == Availability.BOTH]

        if status:
            if status == 'watched':
                filtered_movies = [m for m in filtered_movies if m.watch_status == WatchStatus.WATCHED]
            elif status == 'in_progress':
                filtered_movies = [m for m in filtered_movies if m.watch_status == WatchStatus.IN_PROGRESS]
            elif status == 'not_watched':
                filtered_movies = [m for m in filtered_movies if m.watch_status == WatchStatus.NOT_WATCHED]

        if tag:
            # Get the tag details for each movie
            tagged_movies = []
            for movie in filtered_movies:
                if not movie.radarr_id:
                    continue

                details = radarr_service.get_movie_details(movie.radarr_id)
                if 'tags' in details:
                    tag_names = radarr_service.get_tag_names(details['tags'])
                    if tag in tag_names:
                        tagged_movies.append(movie)
            filtered_movies = tagged_movies

        # Display the results
        if not filtered_movies:
            click.echo("No movies match the specified filters.")
            return

        click.echo(f"\nFound {len(filtered_movies)} movies to delete:")
        for idx, movie in enumerate(filtered_movies, 1):
            click.echo(f"{idx}. {movie.title}")
            if movie.tmdb_id:
                click.echo(f"   TMDB ID: {movie.tmdb_id}")
            if movie.file_path:
                click.echo(f"   Path: {movie.file_path}")
            if movie.file_size:
                click.echo(f"   Size: {format_file_size(movie.file_size)}")
            if movie.watch_status == WatchStatus.WATCHED:
                click.echo(f"   Watched: {movie.watch_date.strftime('%Y-%m-%d')}")

        # Check if we should execute deletions
        if not execute:
            click.echo("\nThis was a dry run. Use --execute to actually delete these movies.")
            return

        # Confirm one more time before proceeding
        if not click.confirm(f"\nAre you sure you want to delete {len(filtered_movies)} movies from Radarr?", default=False):
            click.echo("Operation cancelled.")
            return

        # Process each movie for deletion
        click.echo("\nStarting deletion process...")
        deleted_count = 0
        skipped_count = 0

        for movie in filtered_movies:
            if not movie.radarr_id:
                click.echo(f"Skipping {movie.title} - No Radarr ID found.")
                skipped_count += 1
                continue

            action_message = f"Deleting {movie.title} from Radarr (including files)"

            # If confirmation is required, ask user
            if confirm:
                if not click.confirm(f"{action_message}. Proceed?", default=False):
                    click.echo("Skipped.")
                    skipped_count += 1
                    continue
            else:
                click.echo(action_message)

            try:
                # Delete the movie from Radarr
                if verbose:
                    logger.debug(f"Deleting movie ID {movie.radarr_id}")

                radarr_service.delete_movie(movie.radarr_id)
                deleted_count += 1
                click.echo(f"Successfully deleted {movie.title} from Radarr")

                # Small delay to prevent overwhelming the API
                time.sleep(0.5)
            except Exception as e:
                error_msg = f"Error deleting {movie.title} from Radarr: {str(e)}"
                click.echo(error_msg, err=True)
                if verbose:
                    logger.exception("Detailed error information:")

        # Summary
        click.echo(f"\nDeletion completed:")
        click.echo(f"- {deleted_count} movies deleted from Radarr")
        click.echo(f"- {skipped_count} movies skipped")

        if verbose:
            logger.debug("Deletion process completed successfully")

    except Exception as e:
        error_msg = f"Error: {str(e)}"
        click.echo(error_msg, err=True)
        if verbose:
            logger.exception("Detailed error information:")

def format_file_size(size_bytes):
    """Format file size in human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} PB"
