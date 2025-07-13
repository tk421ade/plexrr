import click
from .commands.list_command import list_movies

@click.group()
def cli():
    """PlexRR - A tool to manage movies across Plex and Radarr"""
    pass

cli.add_command(list_movies)

if __name__ == '__main__':
    cli()
