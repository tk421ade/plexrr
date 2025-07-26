import click
from .commands.list_command import list_movies
from .commands.sync_command import sync_movies
from .commands.profiles_command import list_profiles
from .commands.folders_command import list_folders
from .commands.clean_command import clean_movies
from .commands.delete_command import delete_movies
from .commands.delete_watched_command import delete_watched_episodes
from .commands.download_next_command import download_next_episodes
from .commands.config_command import config_group
from .commands.webhook_command import webhook_group

@click.group()
def cli():
    """PlexRR - A tool to manage media across Plex, Radarr, and Sonarr"""
    pass

cli.add_command(list_movies)
cli.add_command(sync_movies)
cli.add_command(list_profiles)
cli.add_command(list_folders)
cli.add_command(clean_movies)
cli.add_command(delete_movies)
cli.add_command(delete_watched_episodes)
cli.add_command(download_next_episodes)
cli.add_command(config_group)
cli.add_command(webhook_group)

    # Handle common errors with helpful messages
@cli.result_callback()
def process_result(result, **kwargs):
    return result

if __name__ == '__main__':
    cli()
