import click
from tabulate import tabulate
from ..services.plex_service import PlexService
from ..services.radarr_service import RadarrService
from ..services.merger_service import merge_movies
from ..utils.config_loader import get_config

@click.command(name='list')
@click.option('--sort-by', type=click.Choice(['title', 'date']), default='title',
              help='Sort results by title or date')
def list_movies(sort_by):
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

        # Sort results
        if sort_by == 'title':
            all_movies.sort(key=lambda x: x.title.lower())
        else:  # sort by date
            # Sort by watch_date or progress_date if available, otherwise by added_date
            # Handle None dates by placing them at the end
            all_movies.sort(
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
        ] for movie in all_movies]

        click.echo(tabulate(table, headers=headers, tablefmt='grid'))
        click.echo(f"Total: {len(all_movies)} movies")

    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
