import click
from datetime import datetime
from tabulate import tabulate
from ..services.plex_service import PlexService
from ..services.radarr_service import RadarrService
from ..services.merger_service import merge_movies
from ..models.movie import WatchStatus, Availability
from ..utils.config_loader import get_config

@click.command(name='list')
@click.option('--sort-by', type=click.Choice(['title', 'date']), default='title',
              help='Sort results by title or date')
@click.option('--has-size/--no-size', default=None, help='Filter for movies with/without file size')
@click.option('--days', type=int, help='Filter for movies older than N days')
@click.option('--watchlist/--no-watchlist', default=None, help='Filter for movies in/not in watchlist')
@click.option('--availability', type=click.Choice(['plex', 'radarr', 'both']), 
              help='Filter by availability (plex/radarr/both)')
@click.option('--status', type=click.Choice(['watched', 'not_watched', 'in_progress']), 
              help='Filter by watch status')
@click.option('--tag', help='Filter by Radarr tag')
def list_movies(sort_by, has_size, days, watchlist, availability, status, tag):
    """List all movies from Plex and Radarr with merged information"""
    try:
        config = get_config()

        # Initialize services
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
        click.echo("Applying filters...")
        filtered_movies = []
        for movie in all_movies:
            # Skip if filtered by size
            if has_size is not None:
                if has_size and movie.file_size is None:
                    continue
                if not has_size and movie.file_size is not None:
                    continue

            # Skip if filtered by days
            if days is not None:
                relevant_date = movie.watch_date or movie.progress_date or movie.added_date
                if relevant_date is None or (datetime.now() - relevant_date).days < days:
                    continue

            # Skip if filtered by watchlist
            if watchlist is not None and movie.in_watchlist != watchlist:
                continue

            # Skip if filtered by availability
            if availability is not None:
                avail_value = availability.upper()
                if movie.availability.name != avail_value:
                    continue

            # Skip if filtered by status
            if status is not None:
                if status == 'watched' and movie.watch_status != WatchStatus.WATCHED:
                    continue
                if status == 'not_watched' and movie.watch_status != WatchStatus.NOT_WATCHED:
                    continue
                if status == 'in_progress' and movie.watch_status != WatchStatus.IN_PROGRESS:
                    continue

            # Skip if filtered by Radarr tag
            if tag is not None and movie.availability != Availability.RADARR and movie.availability != Availability.BOTH:
                continue
            if tag is not None and not _has_tag(movie, tag, radarr_service):
                continue

            filtered_movies.append(movie)

        # Sort results
        if sort_by == 'title':
            filtered_movies.sort(key=lambda x: x.title.lower())
        else:  # sort by date
            # Sort by watch_date or progress_date if available, otherwise by added_date
            # Handle None dates by placing them at the end
            filtered_movies.sort(
                key=lambda x: (x.watch_date or x.progress_date or x.added_date or datetime(1900, 1, 1)), 
                reverse=True
            )

        # Display results
        headers = ['Title', 'Available In', 'Size', 'Date', 'Status', 'Watchlist']
        table = [[
            movie.title,
            movie.availability.value,
            movie.get_formatted_size(),
            movie.get_formatted_date(),
            movie.watch_status.value,
            'Yes' if movie.in_watchlist else 'No'
        ] for movie in filtered_movies]

        click.echo(tabulate(table, headers=headers, tablefmt='grid'))
        click.echo(f"Total: {len(filtered_movies)} movies")

    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)

def _has_tag(movie, tag_name, radarr_service):
    """Check if a movie has the specified Radarr tag"""
    if not movie.radarr_id:
        return False

    try:
        # Get movie details with tags from Radarr
        movie_details = radarr_service.get_movie_details(movie.radarr_id)
        if not movie_details or 'tags' not in movie_details:
            return False

        # Get tag names
        tag_ids = movie_details['tags']
        tags = radarr_service.get_tag_names(tag_ids)

        # Check if requested tag is in the list
        return tag_name.lower() in [t.lower() for t in tags]
    except Exception:
        return False
