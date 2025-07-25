"""Commands package for PlexRR"""
# Initialize commands package
# This ensures all command modules can be properly imported
from .list_command import list_movies
from .sync_command import sync_movies
from .profiles_command import list_profiles
from .folders_command import list_folders
from .clean_command import clean_movies
from .delete_command import delete_movies
from .delete_watched_command import delete_watched_episodes

__all__ = ['list_movies', 'sync_movies', 'list_profiles', 'list_folders', 'clean_movies', 'delete_movies', 'delete_watched_episodes']
