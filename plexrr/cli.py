import click
from .commands.list_command import list_movies
from .commands.sync_command import sync_movies
from .commands.profiles_command import list_profiles
from .commands.folders_command import list_folders
from .commands.clean_command import clean_movies

@click.group()
def cli():
    """PlexRR - A tool to manage movies across Plex and Radarr"""
    pass

cli.add_command(list_movies)
cli.add_command(sync_movies)
cli.add_command(list_profiles)
cli.add_command(list_folders)
cli.add_command(clean_movies)

if __name__ == '__main__':
    cli()
