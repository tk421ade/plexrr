import os
import re
import logging
import feedparser
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import List, Dict, Optional

from plexapi.server import PlexServer
from plexapi.myplex import MyPlexAccount

from ..models.movie import Movie, WatchStatus, Availability
from ..models.tvshow import TVShow

class PlexService:
    """Service for interacting with Plex API"""

    def __init__(self, config: Dict):
        """Initialize Plex service with configuration"""
        self.config = config  # Store the entire config
        self.base_url = config['base_url']
        self.token = config['token']
        self.server = PlexServer(self.base_url, self.token)

    def delete_watched_episodes(self, show_id: str = None, confirm: bool = False, days: int = None, skip_pilots: bool = False) -> Dict[str, int]:
        """Delete all watched episodes for a specific show or all shows

        Args:
            show_id: Optional Plex ID of the show to delete episodes from (all shows if None)
            confirm: If True, ask for confirmation before each deletion
            days: Only delete episodes watched more than X days ago
            skip_pilots: If True, skip pilot episodes (S01E01) when deleting

        Returns:
            Dict with count of deleted and skipped episodes
        """
        results = {
            'deleted': 0,
            'skipped': 0
        }

        try:
            # Find all show library sections
            show_sections = [section for section in self.server.library.sections() if section.type == 'show']

            if not show_sections:
                print("No TV show libraries found in Plex")
                return results

            # Get the specific show if ID provided, otherwise process all shows
            for section in show_sections:
                shows = [section.fetchItem(show_id)] if show_id else section.all()

                for plex_show in shows:
                    if not plex_show:
                        continue

                    # Process each watched episode
                    watched_episodes = [ep for ep in plex_show.episodes() if ep.isWatched and (not hasattr(ep, 'viewOffset') or ep.viewOffset == 0)]

                    # Filter by days if specified
                    if days is not None:
                        from datetime import datetime, timedelta
                        cutoff_date = datetime.now() - timedelta(days=days)
                        watched_episodes = [
                            ep for ep in watched_episodes 
                            if hasattr(ep, 'lastViewedAt') and ep.lastViewedAt 
                            and ep.lastViewedAt.replace(tzinfo=None) < cutoff_date
                        ]

                    # Skip pilot episodes if specified
                    if skip_pilots:
                        watched_episodes = [
                            ep for ep in watched_episodes
                            if not (ep.seasonNumber == 1 and ep.index == 1)
                        ]

                    if not watched_episodes:
                        print(f"No watched episodes found for '{plex_show.title}'")
                        continue

                    print(f"Found {len(watched_episodes)} watched episodes in '{plex_show.title}'")

                    for episode in watched_episodes:
                        episode_info = f"{plex_show.title} - S{episode.seasonNumber:02d}E{episode.index:02d} - {episode.title}"

                        # If confirmation is required, ask user
                        if confirm:
                            import click
                            if not click.confirm(f"Delete {episode_info}?", default=False):
                                print(f"Skipped: {episode_info}")
                                results['skipped'] += 1
                                continue

                        # Delete the episode
                        try:
                            episode.delete()
                            print(f"Deleted: {episode_info}")
                            results['deleted'] += 1
                        except Exception as e:
                            print(f"Error deleting {episode_info}: {str(e)}")
                            results['skipped'] += 1

            return results

        except Exception as e:
            print(f"Error deleting watched episodes: {str(e)}")
            return results

    def get_movies(self) -> List[Movie]:
        """Get all movies from Plex library"""
        movies = []
        for section in self.server.library.sections():
            if section.type == 'movie':
                for plex_movie in section.all():
                    # Determine watch status
                    if plex_movie.isWatched:
                        status = WatchStatus.WATCHED
                        watch_date = self._get_last_watched_date(plex_movie)
                        progress_date = None
                    elif plex_movie.viewOffset > 0:
                        status = WatchStatus.IN_PROGRESS
                        watch_date = None
                        # For IN_PROGRESS, use lastViewedAt as the progress date
                        progress_date = self._get_last_viewed_date(plex_movie)
                    else:
                        status = WatchStatus.NOT_WATCHED
                        watch_date = None
                        progress_date = None

                    # Extract external IDs
                    imdb_id = None
                    tmdb_id = None

                    if plex_movie.guid:
                        for guid in plex_movie.guids:
                            if 'imdb://' in guid.id:
                                imdb_id = guid.id.split('imdb://')[1]
                            elif 'tmdb://' in guid.id:
                                tmdb_id = int(guid.id.split('tmdb://')[1])

                    # Get file path and size if available
                    file_path = None
                    file_size = None
                    if hasattr(plex_movie, 'media') and plex_movie.media:
                        for media in plex_movie.media:
                            if hasattr(media, 'parts') and media.parts:
                                for part in media.parts:
                                    if hasattr(part, 'file') and part.file:
                                        file_path = part.file
                                        if file_size is None:
                                            file_size = part.size
                                        else:
                                            file_size += part.size
                                        break

                    # Get actual added date from Plex
                    added_date = self._get_added_date(plex_movie)

                    # Create movie object
                    movie = Movie(
                        title=plex_movie.title,
                        availability=Availability.PLEX,
                        watch_date=watch_date,
                        progress_date=progress_date,
                        added_date=added_date,
                        watch_status=status,
                        in_watchlist=False,  # Will be updated with watchlist data
                        file_size=file_size,
                        file_path=file_path,
                        plex_id=plex_movie.ratingKey,
                        imdb_id=imdb_id,
                        tmdb_id=tmdb_id
                    )

                    movies.append(movie)

        return movies

    def get_watchlist(self) -> List[Movie]:
        """Get all movies from Plex watchlist"""
        # Check if RSS feed URL is provided
        if 'watchlist_rss' in self.config:
            return self._get_watchlist_from_rss(self.config['watchlist_rss'])
        # Otherwise try to use account credentials
        elif 'username' in self.config and 'password' in self.config:
            return self._get_watchlist_from_account()
        else:
            print("Warning: No valid watchlist configuration found. "
                  "Please add either 'watchlist_rss' URL or Plex credentials to your config.")
            return []

    def get_tv_shows(self) -> List[TVShow]:
        """Get TV shows from Plex"""
        tv_shows = []

        try:
            # Find all show library sections
            show_sections = [section for section in self.server.library.sections() if section.type == 'show']

            if not show_sections:
                print("No TV show libraries found in Plex")
                return []

            # Get all shows from each section
            for section in show_sections:
                for plex_show in section.all():
                    # Determine watch status
                    if plex_show.isWatched:
                        status = WatchStatus.WATCHED
                        watch_date = self._get_last_watched_date(plex_show)
                        progress_date = None
                    elif hasattr(plex_show, 'viewedLeafCount') and plex_show.viewedLeafCount > 0:
                        status = WatchStatus.IN_PROGRESS
                        watch_date = None
                        progress_date = self._get_last_viewed_date(plex_show)
                    else:
                        status = WatchStatus.NOT_WATCHED
                        watch_date = None
                        progress_date = None

                    # Extract external IDs
                    tvdb_id = None
                    imdb_id = None

                    if hasattr(plex_show, 'guids') and plex_show.guids:
                        for guid in plex_show.guids:
                            if 'tvdb://' in guid.id:
                                try:
                                    tvdb_id = int(guid.id.split('tvdb://')[1])
                                except (ValueError, IndexError):
                                    pass
                            elif 'imdb://' in guid.id:
                                try:
                                    imdb_id = guid.id.split('imdb://')[1]
                                except IndexError:
                                    pass

                    # Get season and episode counts
                    season_count = 0
                    episode_count = 0

                    if hasattr(plex_show, 'seasons'):
                        season_count = len(plex_show.seasons())

                    if hasattr(plex_show, 'episodes'):
                        episode_count = len(plex_show.episodes())

                    # Get file sizes (total for all episodes)
                    file_size = None
                    if hasattr(plex_show, 'episodes'):
                        for episode in plex_show.episodes():
                            if hasattr(episode, 'media') and episode.media:
                                for media in episode.media:
                                    if hasattr(media, 'parts') and media.parts:
                                        for part in media.parts:
                                            if hasattr(part, 'size') and part.size:
                                                if file_size is None:
                                                    file_size = part.size
                                                else:
                                                    file_size += part.size

                    # Get actual added date from Plex
                    added_date = self._get_added_date(plex_show)

                    # Create TV show object
                    tv_show = TVShow(
                        title=plex_show.title,
                        availability=Availability.PLEX,
                        watch_date=watch_date,
                        progress_date=progress_date,
                        added_date=added_date,
                        watch_status=status,
                        in_watchlist=False,  # Will be updated with watchlist data
                        file_size=file_size,
                        plex_id=plex_show.ratingKey,
                        tvdb_id=tvdb_id,
                        imdb_id=imdb_id,
                        season_count=season_count,
                        episode_count=episode_count
                    )

                    tv_shows.append(tv_show)


        except Exception as e:
            print(f"Error fetching TV shows from Plex: {str(e)}")

        return tv_shows

    def get_tv_watchlist(self) -> List[TVShow]:
        """Get TV shows from Plex watchlist"""
        watchlist_shows = []

        # Check if RSS feed URL is provided
        if 'watchlist_rss' in self.config:
            try:
                feed = feedparser.parse(self.config['watchlist_rss'])
                for entry in feed.entries:
                    # Check if it's a TV show (has season/episode info)
                    title = entry.title
                    if ('tv' in entry.get('plex_itemtype', '').lower() or
                        'season' in title.lower() or
                        'episode' in title.lower() or
                        re.search(r'\s*\(S\d+.*\)\s*', title)):

                        # Remove season/episode info from title
                        title = re.sub(r'\s*\(S\d+.*\)\s*', '', title)

                        # Try to extract TVDB/IMDB IDs from guid
                        tvdb_id = None
                        imdb_id = None
                        if hasattr(entry, 'plex_guid'):
                            for guid in entry.plex_guid:
                                if 'tvdb' in guid.lower():
                                    try:
                                        tvdb_id = int(re.search(r'tvdb://(\d+)', guid).group(1))
                                    except (AttributeError, ValueError, TypeError):
                                        pass
                                elif 'imdb' in guid.lower():
                                    try:
                                        imdb_id = re.search(r'imdb://(tt\d+)', guid).group(1)
                                    except (AttributeError, ValueError, TypeError):
                                        pass

                        # Create TV show object for watchlist
                        show = TVShow(
                            title=title,
                            availability=Availability.PLEX,  # Will be updated in merging
                            watch_status=WatchStatus.NOT_WATCHED,
                            in_watchlist=True,
                            tvdb_id=tvdb_id,
                            imdb_id=imdb_id
                        )

                        watchlist_shows.append(show)

            except Exception as e:
                print(f"Error fetching TV watchlist from RSS: {str(e)}")

            # Fallback to username/password if available
            if not watchlist_shows and 'username' in self.config and 'password' in self.config:
                try:
                    # Connect to MyPlex account
                    account = MyPlexAccount(self.config['username'], self.config['password'])
                    watchlist_items = account.watchlist()

                    for item in watchlist_items:
                        if item.type == 'show':
                            # Extract external IDs
                            tvdb_id = None
                            imdb_id = None

                            if hasattr(item, 'guids') and item.guids:
                                for guid in item.guids:
                                    if 'tvdb://' in guid.id:
                                        try:
                                            tvdb_id = int(guid.id.split('tvdb://')[1])
                                        except (ValueError, IndexError):
                                            pass
                                    elif 'imdb://' in guid.id:
                                        try:
                                            imdb_id = guid.id.split('imdb://')[1]
                                        except IndexError:
                                            pass

                            # Create TV show object for watchlist
                            show = TVShow(
                                title=item.title,
                                availability=Availability.PLEX,  # Will be updated in merging
                                watch_status=WatchStatus.NOT_WATCHED,
                                in_watchlist=True,
                                tvdb_id=tvdb_id,
                                imdb_id=imdb_id
                            )

                            watchlist_shows.append(show)

                except Exception as e:
                    print(f"Error fetching TV watchlist from Plex account: {str(e)}")

        return watchlist_shows

    def _get_watchlist_from_rss(self, rss_url: str) -> List[Movie]:
        """Get watchlist movies from RSS feed URL"""
        try:
            import requests
            import xml.etree.ElementTree as ET

            response = requests.get(rss_url)
            response.raise_for_status()

            # Parse the RSS XML
            root = ET.fromstring(response.content)

            # Find all items in the feed
            watchlist_movies = []

            # XML namespace for media content
            ns = {'media': 'http://search.yahoo.com/mrss/'}

            for item in root.findall('.//item'):
                title_elem = item.find('title')
                if title_elem is not None:
                    title = title_elem.text

                    # Try to extract TMDB or IMDB ID from guid
                    guid_elem = item.find('guid')
                    guid = guid_elem.text if guid_elem is not None else None

                    imdb_id = None
                    tmdb_id = None

                    # Try to extract TMDB ID from media:content
                    media_content = item.find('.//media:content', ns)
                    if media_content is not None:
                        # Try to get TMDB ID from media attributes
                        tmdb_id_str = media_content.get('tmdbid')
                        if tmdb_id_str and tmdb_id_str.isdigit():
                            tmdb_id = int(tmdb_id_str)

                    # Create movie object for watchlist item
                    movie = Movie(
                        title=title,
                        availability=Availability.PLEX,  # May be adjusted during merging
                        watch_date=None,
                        progress_date=None,
                        added_date=None,  # RSS doesn't provide added date
                        in_watchlist=True,
                        imdb_id=imdb_id,
                        tmdb_id=tmdb_id
                    )

                    watchlist_movies.append(movie)

            return watchlist_movies

        except Exception as e:
            print(f"Error fetching watchlist from RSS: {str(e)}")
            return []

    def _get_watchlist_from_account(self) -> List[Movie]:
        """Get watchlist using Plex account credentials"""
        try:
            # Connect to MyPlex account
            account = MyPlexAccount(self.config['username'], self.config['password'])
            watchlist_items = account.watchlist()

            watchlist_movies = []
            for item in watchlist_items:
                if item.type == 'movie':
                    # Extract external IDs
                    imdb_id = None
                    tmdb_id = None

                    if hasattr(item, 'guid') and item.guid:
                        for guid in item.guids:
                            if 'imdb://' in guid.id:
                                imdb_id = guid.id.split('imdb://')[1]
                            elif 'tmdb://' in guid.id:
                                tmdb_id = int(guid.id.split('tmdb://')[1])

                    # Create movie object for watchlist item
                    movie = Movie(
                        title=item.title,
                        availability=Availability.PLEX,  # May be adjusted during merging
                        watch_date=None,
                        progress_date=None,
                        added_date=None,  # Watchlist doesn't provide added date
                        in_watchlist=True,
                        imdb_id=imdb_id,
                        tmdb_id=tmdb_id
                    )

                    watchlist_movies.append(movie)

            return watchlist_movies
        except Exception as e:
            print(f"Error fetching watchlist from Plex account: {str(e)}")
            return []
        except Exception as e:
            print(f"Error fetching watchlist: {str(e)}")
            return []

    def _get_added_date(self, plex_movie) -> Optional[datetime]:
        """Get the date when a movie was added to Plex"""
        try:
            if hasattr(plex_movie, 'addedAt') and plex_movie.addedAt:
                # Handle both datetime objects and timestamps
                if isinstance(plex_movie.addedAt, (int, float)):
                    return datetime.fromtimestamp(plex_movie.addedAt).replace(tzinfo=None)
                else:
                    return plex_movie.addedAt.replace(tzinfo=None)
            return None
        except (AttributeError, TypeError):
            return None

    def _get_last_watched_date(self, plex_movie) -> datetime:
        """Get the date when a movie was last watched (for fully watched movies)"""
        try:
            # Use timezone-naive datetime for consistency
            return plex_movie.lastViewedAt.replace(tzinfo=None)
        except (AttributeError, TypeError):
            return None

    def _get_last_viewed_date(self, plex_movie) -> Optional[datetime]:
        """Get the date when a movie was last viewed (for in-progress movies)"""
        try:
            # Use timezone-naive datetime for consistency
            return plex_movie.lastViewedAt.replace(tzinfo=None)
        except (AttributeError, TypeError):
            return None

    def get_next_episodes(self, show_id: str = None, count: int = 1) -> Dict[str, List]:
        """Get next episodes to download for shows that are being watched

        Args:
            show_id: Optional Plex ID of the show to get next episodes for (all shows if None)
            count: Number of next episodes to suggest for each show

        Returns:
            Dict with show titles as keys and lists of next episodes as values
        """
        results = {}

        try:
            # Find all show library sections
            show_sections = [section for section in self.server.library.sections() if section.type == 'show']

            if not show_sections:
                print("No TV show libraries found in Plex")
                return results

            # Get the specific show if ID provided, otherwise process all shows
            for section in show_sections:
                shows = [section.fetchItem(show_id)] if show_id else section.all()

                for plex_show in shows:
                    if not plex_show:
                        continue

                    # Skip shows that have no episodes or no watched episodes
                    episodes = plex_show.episodes()
                    if not episodes or not any(ep.isWatched for ep in episodes):
                        continue

                    # Find the most recently watched episode
                    watched_episodes = sorted(
                        [ep for ep in episodes if ep.isWatched],
                        key=lambda ep: ep.lastViewedAt if hasattr(ep, 'lastViewedAt') and ep.lastViewedAt else datetime.min,
                        reverse=True
                    )

                    if not watched_episodes:
                        continue

                    latest_watched = watched_episodes[0]

                    # Find next episodes after the most recently watched one
                    next_episodes = []

                    # First check episodes in the same season
                    same_season_episodes = sorted(
                        [ep for ep in episodes 
                         if ep.seasonNumber == latest_watched.seasonNumber and ep.index > latest_watched.index],
                        key=lambda ep: ep.index
                    )

                    next_episodes.extend(same_season_episodes[:count])

                    # If we don't have enough episodes, check the next season(s)
                    if len(next_episodes) < count:
                        later_season_episodes = sorted(
                            [ep for ep in episodes 
                             if ep.seasonNumber > latest_watched.seasonNumber],
                            key=lambda ep: (ep.seasonNumber, ep.index)
                        )

                        next_episodes.extend(later_season_episodes[:count - len(next_episodes)])

                    # If we found any next episodes, add them to the results
                    if next_episodes:
                        next_episodes_info = []
                        for ep in next_episodes:
                            next_episodes_info.append({
                                'title': ep.title,
                                'season': ep.seasonNumber,
                                'episode': ep.index,
                                'key': ep.key,
                                'year': ep.year if hasattr(ep, 'year') else None,
                                'summary': ep.summary if hasattr(ep, 'summary') else None
                            })

                        results[plex_show.title] = next_episodes_info

            return results

        except Exception as e:
            print(f"Error getting next episodes: {str(e)}")
            return results
