import click
import logging
import json
from typing import Dict, List, Tuple
from tabulate import tabulate
from ..services.radarr_service import RadarrService
from ..utils.config_loader import get_config
from ..models.movie import Movie

@click.command(name='clean')
@click.option('--dry-run', is_flag=True, help='Show what would be done without making changes')
@click.option('--confirm', is_flag=True, help='Prompt for confirmation before each action')
@click.option('--verbose', is_flag=True, help='Enable verbose debug output')
def clean_movies(dry_run, confirm, verbose):
    """Clean duplicate movie versions by keeping only the best quality for each movie"""
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

        # Get all movies from Radarr
        click.echo("Fetching movies from Radarr...")
        movies = radarr_service.get_movies()
        click.echo(f"Found {len(movies)} movies in Radarr")

        # Initialize counters
        movies_with_duplicates = 0
        files_to_remove = 0
        removed_files = 0
        skipped_files = 0

        # Track movies with multiple files
        duplicate_movies = []

        # Check each movie for multiple versions
        click.echo("Checking for movies with multiple versions...")
        for movie in movies:
            if not movie.radarr_id:
                continue

            if verbose:
                logger.debug(f"Checking movie: {movie.title} (ID: {movie.radarr_id})")

            try:
                # Get all files for this movie
                movie_files = radarr_service.get_movie_files(movie.radarr_id)

                if len(movie_files) > 1:
                    movies_with_duplicates += 1
                    files_to_remove += len(movie_files) - 1  # We'll keep the best one

                    # Process the movie files to determine which to keep/remove
                    best_file, files_to_delete = get_files_to_clean(movie_files, radarr_service, verbose, logger)

                    duplicate_movies.append({
                        'movie': movie,
                        'best_file': best_file,
                        'files_to_delete': files_to_delete
                    })

                    if verbose:
                        logger.debug(f"Found {len(movie_files)} versions for {movie.title}")
                        logger.debug(f"Best version: {best_file['relativePath']} ({best_file['quality'].get('quality', {}).get('name', 'Unknown')})")
            except Exception as e:
                if verbose:
                    logger.exception(f"Error processing movie {movie.title}: {str(e)}")

        # Display summary of what was found
        click.echo(f"\nFound {movies_with_duplicates} movies with multiple versions")
        click.echo(f"Total of {files_to_remove} files can be removed")

        if movies_with_duplicates == 0:
            click.echo("No movies with multiple versions found. Nothing to clean.")
            return

        # Display files to be removed
        click.echo("\nMovies with multiple versions:")
        for item in duplicate_movies:
            movie = item['movie']
            best_file = item['best_file']
            files_to_delete = item['files_to_delete']

            click.echo(f"\n{movie.title}:")
            click.echo(f"  Keeping: {best_file['relativePath']} ({best_file['quality'].get('quality', {}).get('name', 'Unknown')})")
            click.echo("  Removing:")
            for file in files_to_delete:
                click.echo(f"    - {file['relativePath']} ({file['quality'].get('quality', {}).get('name', 'Unknown')})")

        # If dry run, just show what would be done
        if dry_run:
            click.echo("\nDRY RUN MODE - No changes will be made")
            return

        # Process each movie to clean duplicates
        click.echo("\nStarting cleanup process...")

        for item in duplicate_movies:
            movie = item['movie']
            best_file = item['best_file']
            files_to_delete = item['files_to_delete']

            click.echo(f"\nProcessing {movie.title}:")
            click.echo(f"  Keeping: {best_file['relativePath']}")

            for file in files_to_delete:
                action_message = f"  Remove: {file['relativePath']} ({file['quality'].get('quality', {}).get('name', 'Unknown')})"

                # If confirmation is required, ask user
                if confirm:
                    if not click.confirm(f"{action_message}. Proceed?", default=True):
                        click.echo("  Skipped.")
                        skipped_files += 1
                        continue
                else:
                    click.echo(action_message)

                try:
                    # Delete the movie file
                    if verbose:
                        logger.debug(f"Deleting file ID: {file['id']}")

                    radarr_service.delete_movie_file(file['id'])
                    removed_files += 1
                    click.echo(f"  Successfully removed {file['relativePath']}")
                except Exception as e:
                    click.echo(f"  Error removing file: {str(e)}", err=True)
                    if verbose:
                        logger.exception("Detailed error information:")

        # Summary
        click.echo(f"\nCleanup completed:")
        click.echo(f"- {removed_files} files removed")
        click.echo(f"- {skipped_files} files skipped")

        if verbose:
            logger.debug("Cleanup process completed successfully")

    except Exception as e:
        error_msg = f"Error: {str(e)}"
        click.echo(error_msg, err=True)
        if verbose:
            logger.exception("Detailed error information:")

def get_files_to_clean(movie_files: List[Dict], radarr_service: RadarrService, verbose: bool, logger) -> Tuple[Dict, List[Dict]]:
    """Determine which files to keep and which to remove based on quality

    Args:
        movie_files: List of movie files for a single movie
        radarr_service: RadarrService instance
        verbose: Whether to log verbose details
        logger: Logger instance

    Returns:
        Tuple containing (best_file, list_of_files_to_delete)
    """
    if len(movie_files) <= 1:
        return movie_files[0], []

    # First, sort by quality score (higher is better)
    # Each movie file has a quality object with a quality.id and a quality.name
    # We need to get the quality definition for each to determine the ranking

    # Create a dictionary to cache quality definitions
    quality_scores = {}

    for file in movie_files:
        quality_id = file.get('quality', {}).get('quality', {}).get('id')
        if quality_id and quality_id not in quality_scores:
            try:
                # Get the quality definition with weight/score
                definition = radarr_service.get_quality_definition(quality_id)
                if definition and 'weight' in definition:
                    quality_scores[quality_id] = definition['weight']
                else:
                    quality_scores[quality_id] = 0
            except Exception as e:
                if verbose:
                    logger.warning(f"Could not get quality definition for ID {quality_id}: {str(e)}")
                quality_scores[quality_id] = 0

    if verbose:
        logger.debug(f"Quality scores: {quality_scores}")

    # Sort files by quality score (highest first), then by size (largest first)
    sorted_files = sorted(
        movie_files,
        key=lambda f: (
            quality_scores.get(f.get('quality', {}).get('quality', {}).get('id'), 0),
            f.get('size', 0)
        ),
        reverse=True
    )

    # The first file is the best quality
    best_file = sorted_files[0]
    files_to_delete = sorted_files[1:]

    return best_file, files_to_delete
