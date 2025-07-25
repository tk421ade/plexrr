import click
from datetime import datetime
from tabulate import tabulate
from ..services.plex_service import PlexService
from ..services.radarr_service import RadarrService
from ..services.sonarr_service import SonarrService
from ..services.merger_service import merge_movies
from ..services.merger_service_tvshows import merge_tv_shows
from ..models.movie import WatchStatus, Availability
from ..models.tvshow import TVShow
from ..utils.config_loader import get_config

@click.command(name='list')
@click.option('--sort-by', type=click.Choice(['title', 'date']), default='title',
              help='Sort results by title or date')
@click.option('--has-size/--no-size', default=None, help='Filter for media with/without file size')
@click.option('--days', type=int, help='Filter for media older than N days')
@click.option('--watchlist/--no-watchlist', default=None, help='Filter for media in/not in watchlist')
@click.option('--availability', type=click.Choice(['plex', 'radarr', 'sonarr', 'both']), 
              help='Filter by availability (plex/radarr/sonarr/both)')
@click.option('--status', type=click.Choice(['watched', 'not_watched', 'in_progress']), 
              help='Filter by watch status')
@click.option('--tag', help='Filter by Radarr/Sonarr tag')
@click.option('--type', type=click.Choice(['movies', 'shows', 'all']), default='all',
              help='Filter by media type (movies/shows/all)')
def list_movies(sort_by, has_size, days, watchlist, availability, status, tag, type):
    """List all media from Plex, Radarr, and Sonarr with merged information"""
    try:
        config = get_config()

        # Initialize services
        plex_service = PlexService(config['plex'])
        radarr_service = RadarrService(config['radarr'])

        # Initialize sonarr service if configured and needed
        sonarr_service = None
        if 'sonarr' in config and (type == 'shows' or type == 'all'):
            try:
                sonarr_service = SonarrService(config['sonarr'])
            except Exception as e:
                click.echo(f"Warning: Could not initialize Sonarr service: {str(e)}", err=True)
                if type == 'shows':
                    click.echo("Cannot list shows without Sonarr configuration.", err=True)
                    return

        # Initialize lists
        all_movies = []
        all_shows = []

        # Get movies if requested
        if type == 'movies' or type == 'all':
            click.echo("Fetching movies from Plex...")
            plex_movies = plex_service.get_movies()
            click.echo(f"Found {len(plex_movies)} movies in Plex")

            plex_watchlist = plex_service.get_watchlist()
            click.echo(f"Found {len(plex_watchlist)} movies in Plex Watchlist")

            click.echo("Fetching movies from Radarr...")
            radarr_movies = radarr_service.get_movies()
            click.echo(f"Found {len(radarr_movies)} movies in Radarr")

            # Merge the movie results
            click.echo("Merging movie results...")
            all_movies = merge_movies(plex_movies, radarr_movies, plex_watchlist)

        # Get TV shows if requested
        if (type == 'shows' or type == 'all') and sonarr_service:
            click.echo("Fetching TV shows from Plex...")
            plex_shows = plex_service.get_tv_shows()
            click.echo(f"Found {len(plex_shows)} TV shows in Plex")

            plex_show_watchlist = plex_service.get_tv_watchlist()
            click.echo(f"Found {len(plex_show_watchlist)} TV shows in Plex Watchlist")

            click.echo("Fetching TV shows from Sonarr...")
            sonarr_shows = sonarr_service.get_shows()
            click.echo(f"Found {len(sonarr_shows)} TV shows in Sonarr")

            # Merge the TV show results
            click.echo("Merging TV show results...")
            all_shows = merge_tv_shows(plex_shows, sonarr_shows, plex_show_watchlist)

        # Apply filters to movies
        click.echo("Applying filters...")
        filtered_movies = []
        filtered_shows = []

        # Filter movies if we have any
        if all_movies:
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
                if tag is not None and not _has_tag(movie, tag, radarr_service, is_movie=True):
                    continue

                filtered_movies.append(movie)

        # Filter TV shows if we have any
        if all_shows and sonarr_service:
            for show in all_shows:
                # Skip if filtered by size
                if has_size is not None:
                    if has_size and show.file_size is None:
                        continue
                    if not has_size and show.file_size is not None:
                        continue

                # Skip if filtered by days
                if days is not None:
                    relevant_date = show.watch_date or show.progress_date or show.added_date
                    if relevant_date is None or (datetime.now() - relevant_date).days < days:
                        continue

                # Skip if filtered by watchlist
                if watchlist is not None and show.in_watchlist != watchlist:
                    continue

                # Skip if filtered by availability
                if availability is not None:
                    avail_value = availability.upper()
                    if show.availability.name != avail_value:
                        continue

                # Skip if filtered by status
                if status is not None:
                    if status == 'watched' and show.watch_status != WatchStatus.WATCHED:
                        continue
                    if status == 'not_watched' and show.watch_status != WatchStatus.NOT_WATCHED:
                        continue
                    if status == 'in_progress' and show.watch_status != WatchStatus.IN_PROGRESS:
                        continue

                # Skip if filtered by Sonarr tag
                if tag is not None and show.availability != Availability.SONARR and show.availability != Availability.BOTH:
                    continue
                if tag is not None and not _has_tag(show, tag, sonarr_service, is_movie=False):
                    continue

                filtered_shows.append(show)

        # Determine which results to display based on type filter
        display_items = []
        if type == 'movies':
            display_items = filtered_movies
        elif type == 'shows':
            display_items = filtered_shows
        else:  # type == 'all'
            display_items = filtered_movies + filtered_shows

        # Sort results
        if sort_by == 'title':
            display_items.sort(key=lambda x: x.title.lower())
        else:  # sort by date
            # Sort by watch_date or progress_date if available, otherwise by added_date
            # Handle None dates by placing them at the end
            display_items.sort(
                key=lambda x: (x.watch_date or x.progress_date or x.added_date or datetime(1900, 1, 1)), 
                reverse=True
            )

        # Display results
        if not display_items:
            if type == 'shows':
                click.echo("No TV shows found matching the specified filters.")
            elif type == 'movies':
                click.echo("No movies found matching the specified filters.")
            else:
                click.echo("No media found matching the specified filters.")
            return

        # Different headers for TV shows (include episode count)
        headers = ['Title', 'Available In', 'Size', 'Date', 'Status', 'Watchlist']

        # Build table rows
        table = []
        for item in display_items:
            # Check if this is a TV show or movie
            is_show = isinstance(item, TVShow)

            row = [
                item.title,
                item.availability.value,
                item.get_formatted_size() if not is_show else item.get_formatted_episodes(),
                item.get_formatted_date(),
                item.watch_status.value,
                'Yes' if item.in_watchlist else 'No'
            ]
            table.append(row)

        click.echo(tabulate(table, headers=headers, tablefmt='grid'))

        # Count by type for summary
        movie_count = len([item for item in display_items if not isinstance(item, TVShow)])
        show_count = len([item for item in display_items if isinstance(item, TVShow)])

        if type == 'movies':
            click.echo(f"Total: {movie_count} movies")
        elif type == 'shows':
            click.echo(f"Total: {show_count} TV shows")
        else:
            click.echo(f"Total: {len(display_items)} items ({movie_count} movies, {show_count} TV shows)")

    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)

def _has_tag(media, tag_name, service, is_movie=True):
    """Check if a media item has the specified tag

    Args:
        media: Movie or TVShow object
        tag_name: Tag name to look for
        service: RadarrService or SonarrService instance
        is_movie: True if checking a movie, False if checking a TV show

    Returns:
        True if the media has the specified tag, False otherwise
    """
    # Check for appropriate ID
    if is_movie and not media.radarr_id:
        return False
    elif not is_movie and not media.sonarr_id:
        return False

    try:
        # Get media details with tags
        if is_movie:
            details = service.get_movie_details(media.radarr_id)
        else:
            details = service.get_show_details(media.sonarr_id)

        if not details or 'tags' not in details:
            return False

        # Get tag names
        tag_ids = details['tags']
        tags = service.get_tag_names(tag_ids)

        # Check if requested tag is in the list
        return tag_name.lower() in [t.lower() for t in tags]
    except Exception:
        return False
