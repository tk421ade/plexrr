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

    def __init__(self, config: Dict, parent_config: Dict = None):
        """Initialize Plex service with configuration

        Args:
            config: Plex service configuration
            parent_config: Full application configuration (for accessing Sonarr)
        """
        self.config = config  # Store the entire config
        self.parent_config = parent_config  # Store parent config to access Sonarr
        self.base_url = config['base_url']
        self.token = config['token']
        self.server = PlexServer(self.base_url, self.token)
        self.sonarr_service = None  # Will be initialized on demand

    def delete_watched_episodes(self, show_id: str = None, confirm: bool = False, days: int = 10, skip_pilots: bool = False, execute: bool = False, verbose: bool = False) -> Dict[str, any]:
        """Find and optionally delete watched episodes for a specific show or all shows

        Args:
            show_id: Optional Plex ID of the show to delete episodes from (all shows if None)
            confirm: If True, ask for confirmation before each deletion
            days: Only delete episodes watched more than X days ago (default: 10 days)
            skip_pilots: If True, skip pilot episodes (S01E01) when deleting
            execute: If True, actually delete the files. If False, just display what would be deleted
            verbose: If True, show detailed information for all shows, including those with no eligible episodes

        Returns:
            Dict with results including counts and total size
        """
        import humanize

        results = {
            'deleted': 0,
            'skipped': 0,
            'total_size': 0,  # Total size of files to be deleted in bytes
            'files': []       # List of files that would be/were deleted
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

                    # Filter by days
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
                        if verbose:
                            print(f"No eligible watched episodes found for '{plex_show.title}'")
                        continue

                    # Only show information for shows that have episodes to process
                    print(f"Found {len(watched_episodes)} watched episodes in '{plex_show.title}'")

                    for episode in watched_episodes:
                        # Get episode file size
                        episode_size = 0
                        file_path = None
                        if hasattr(episode, 'media') and episode.media:
                            for media in episode.media:
                                if hasattr(media, 'parts') and media.parts:
                                    for part in media.parts:
                                        if hasattr(part, 'size') and part.size:
                                            episode_size = part.size
                                        if hasattr(part, 'file') and part.file:
                                            file_path = part.file

                        episode_info = f"{plex_show.title} - S{episode.seasonNumber:02d}E{episode.index:02d} - {episode.title}"
                        size_info = f" ({humanize.naturalsize(episode_size)})" if episode_size > 0 else ""

                        # Only display individual episode information if in verbose mode or when actually deleting
                        action = "Would delete" if not execute else "Deleting"
                        if verbose or execute:
                            print(f"{action}: {episode_info}{size_info}")

                        # Track the episode in our results
                        results['files'].append({
                            'title': episode_info,
                            'size': episode_size,
                            'path': file_path
                        })
                        results['total_size'] += episode_size

                        # If confirmation is required, ask user
                        if confirm and execute:
                            import click
                            if not click.confirm(f"Delete {episode_info}?", default=False):
                                print(f"Skipped: {episode_info}")
                                results['skipped'] += 1
                                continue

                        # Only delete if execute flag is set
                        if execute:
                            try:
                                episode.delete()
                                results['deleted'] += 1
                                print(f"Deleted: {episode_info}")
                            except Exception as e:
                                print(f"Error deleting {episode_info}: {str(e)}")
                                results['skipped'] += 1
                        else:
                            # If not executing, just count as "would delete"
                            results['deleted'] += 1

            # Print summary - only if we actually found something to delete
            if results['deleted'] > 0 or results['skipped'] > 0 or verbose:
                action = "Deleted" if execute else "Would delete"
                print(f"\nSummary:")
                print(f"- {action}: {results['deleted']} episodes")
                print(f"- Size: {humanize.naturalsize(results['total_size'])}")
                if results['skipped'] > 0:
                    print(f"- Skipped: {results['skipped']} episodes")

            return results

        except Exception as e:
            print(f"Error processing watched episodes: {str(e)}")
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

    def _get_last_viewed_date(self, plex_movie) -> datetime:
        """Get the date when a movie was last viewed (for in-progress movies)"""
        try:
            # Use timezone-naive datetime for consistency
            return plex_movie.lastViewedAt.replace(tzinfo=None)
        except (AttributeError, TypeError):
            return None

    def _get_season_info(self, show_title: str, tvdb_id: int = None) -> Dict[int, int]:
        """Get season information from Sonarr for a given show

        Args:
            show_title: Title of the show to look up
            tvdb_id: Optional TVDB ID for the show (more reliable than title)

        Returns:
            Dictionary mapping season numbers to episode count (season finale number)
        """
        logger = logging.getLogger('plexrr')
        season_info = {}

        # Initialize Sonarr service if not already done
        if not self.sonarr_service:
            if not self.parent_config or 'sonarr' not in self.parent_config:
                logger.debug(f"No Sonarr configuration available for season info lookup")
                return season_info

            # Import here to avoid circular imports
            from ..services.sonarr_service import SonarrService
            self.sonarr_service = SonarrService(self.parent_config['sonarr'])

        # Find the show in Sonarr, first try by TVDB ID if available
        sonarr_show = None
        if tvdb_id:
            sonarr_show = self.sonarr_service.find_show_by_tvdb_id(tvdb_id)

        # If not found by TVDB ID, try by title
        if not sonarr_show:
            sonarr_show = self.sonarr_service.find_show_by_title(show_title)

        # If we couldn't find the show in Sonarr, return empty dict
        if not sonarr_show:
            logger.debug(f"Show '{show_title}' not found in Sonarr")
            return season_info

        # Get the series ID from the Sonarr show object
        series_id = sonarr_show.get('id') if isinstance(sonarr_show, dict) else sonarr_show.id

        # Get all episodes for this series from Sonarr
        try:
            episodes = self.sonarr_service.get_episodes_by_series_id(series_id)

            # Group episodes by season and find the highest episode number for each season
            for episode in episodes:
                season_num = episode.get('seasonNumber')
                episode_num = episode.get('episodeNumber')

                if season_num is not None and episode_num is not None:
                    # Ignore season 0 (specials)
                    if season_num > 0:
                        # Update the highest episode number for this season
                        if season_num not in season_info or episode_num > season_info[season_num]:
                            season_info[season_num] = episode_num
        except Exception as e:
            logger.debug(f"Error getting episodes for '{show_title}': {str(e)}")

        return season_info

    def get_next_episodes(self, show_id: str = None, count: int = 1) -> Dict[str, List]:
        """Get next episodes to download for shows that are being watched

        Args:
            show_id: Optional Plex ID of the show to get next episodes for (all shows if None)
            count: Number of next episodes to suggest for each show

        Returns:
            Dict with show titles as keys and lists of next episodes as values
        """
        import logging
        results = {}

        try:
            # Connect to Plex server if needed
            if not hasattr(self, 'server'):
                self.server = PlexServer(self.base_url, self.token)

            # Find all show library sections
            show_sections = [section for section in self.server.library.sections() if section.type == 'show']

            if not show_sections:
                print("No TV show libraries found in Plex")
                return results

            # Get the specific show if ID provided, otherwise process all shows
            if show_id:
                # Try to find the show by ID directly from the server
                try:
                    # Make sure show_id is properly handled as a string
                    show_obj = self.server.fetchItem(str(show_id))
                    if show_obj.type != 'show':
                        raise ValueError(f"ID {show_id} is not a TV show")
                    # Process only this specific show
                    shows = [show_obj]
                    # Only process the first section that contains shows
                    section = show_sections[0]
                except Exception as e:
                    import logging
                    logger = logging.getLogger('plexrr')
                    logger.error(f"Error fetching show with ID {show_id}: {str(e)}")
                    raise ValueError(f"Could not find TV show with ID {show_id}. Please check the ID and try again.")
            else:
                # Get all shows from all TV sections
                section = show_sections[0]  # Start with first section
                shows = section.all()

                for plex_show in shows:
                    if not plex_show:
                        continue

                    # Skip shows that have no episodes or no watched episodes
                    episodes = plex_show.episodes()
                    if not episodes or not any(ep.isWatched for ep in episodes):
                        continue

                    # Get all episodes that are available in Plex
                    available_episodes = set((ep.seasonNumber, ep.index) for ep in episodes)

                    # Find episodes that are in progress (partially watched)
                    in_progress_episodes = [ep for ep in episodes if hasattr(ep, 'viewOffset') and ep.viewOffset > 0]

                    # If there are episodes in progress, use those as starting points
                    if in_progress_episodes:
                        # Sort by season and episode to prioritize earlier episodes
                        in_progress_episodes.sort(key=lambda ep: (ep.seasonNumber, ep.index))
                        reference_episode = in_progress_episodes[0]
                    else:
                        # Otherwise use the most recently watched episode
                        watched_episodes = sorted(
                            [ep for ep in episodes if ep.isWatched],
                            key=lambda ep: ep.lastViewedAt if hasattr(ep, 'lastViewedAt') and ep.lastViewedAt else datetime.min,
                            reverse=True
                        )
                        if not watched_episodes:
                            continue
                        reference_episode = watched_episodes[0]

                    # Important: we need to keep track of how many more episodes we need to find
                    episodes_needed = count

                    # Collect all episodes that follow our reference episode
                    # We'll check both the same season and subsequent seasons
                    all_following_episodes = []

                    # Episodes in the same season with higher episode numbers
                    all_following_episodes.extend([
                        (ep.seasonNumber, ep.index, ep)
                        for ep in episodes
                        if ep.seasonNumber == reference_episode.seasonNumber and ep.index > reference_episode.index
                    ])

                    # Episodes in later seasons
                    all_following_episodes.extend([
                        (ep.seasonNumber, ep.index, ep)
                        for ep in episodes
                        if ep.seasonNumber > reference_episode.seasonNumber
                    ])

                    # Sort all episodes chronologically
                    all_following_episodes.sort()

                    # Now find up to 'count' episodes that we need to download
                    # These must not already be available in Plex (we'll infer this from episodes list)
                    missing_episodes = []

                    # Get the show title for logging
                    show_title = plex_show.title
                    logger = logging.getLogger('plexrr')

                    # Extract TVDB ID if available
                    tvdb_id = None
                    if hasattr(plex_show, 'guids'):
                        for guid in plex_show.guids:
                            if 'tvdb://' in guid.id:
                                try:
                                    tvdb_id = int(guid.id.split('tvdb://')[1])
                                    break
                                except (ValueError, IndexError):
                                    pass

                    # Get season information from Sonarr
                    season_info = self._get_season_info(show_title, tvdb_id)
                    logger.debug(f"Season info for {show_title}: {season_info}")

                    # For in-progress episodes, we want to prioritize missing episodes in the same season
                    # before moving to the next season

                    # First, check for directly adjacent episodes in the current season
                    current_season = reference_episode.seasonNumber
                    next_episode_num = reference_episode.index + 1
                    remaining_count = count  # Keep track of how many episodes we still need to find

                    # Check if the next episode would exceed the season finale
                    # If season info is available from Sonarr, use that
                    season_finale_episode = None
                    if season_info and current_season in season_info:
                        season_finale_episode = season_info[current_season]
                        logger.debug(f"{show_title} S{current_season} finale is episode {season_finale_episode}")

                    # Keep checking sequential episodes in the current season until we have enough
                    # or until we hit the season finale
                    while len(missing_episodes) < remaining_count:
                        # Check if we've hit or exceeded the season finale
                        if season_finale_episode and next_episode_num > season_finale_episode:
                            logger.debug(f"Reached season finale for {show_title} S{current_season}, moving to next season")
                            break

                        # For Bad Batch specifically, handle the known season 1 length
                        if "Bad Batch" in show_title and current_season == 1 and next_episode_num > 16:
                            logger.debug(f"Reached hardcoded season finale for Bad Batch S1 (E16), moving to next season")
                            # For Bad Batch, if S01E16 exists in Sonarr but not in Plex, we need to check
                            # This is to properly handle the case where S01E15 was last watched
                            if (current_season, 16) not in available_episodes:
                                # Check if this episode exists in Sonarr
                                if self.sonarr_service and "The Bad Batch" in show_title:
                                    show_obj = self.sonarr_service.find_show_by_title("Star Wars: The Bad Batch")
                                    if show_obj:
                                        series_id = show_obj.get('id')
                                        if self.sonarr_service.episode_exists(series_id, 1, 16):
                                            logger.debug(f"Bad Batch S01E16 exists in Sonarr but not in Plex, counting it toward episodes needed")
                                            # We don't add it to missing_episodes because it's already in Sonarr
                                            # But we do count it against the episodes_needed
                                            episodes_needed -= 1
                            break

                        # If this episode doesn't exist in Plex, add it to our download list
                        if (current_season, next_episode_num) not in available_episodes:
                            missing_episodes.append({
                                'title': f"Episode {next_episode_num}",
                                'season': current_season,
                                'episode': next_episode_num,
                                'key': None,
                                'year': None,
                                'summary': "Next episode"
                            })
                            episodes_needed -= 1
                            logger.debug(f"Added S{current_season:02d}E{next_episode_num:02d} to missing episodes, {episodes_needed} more needed")

                        # Move to next episode
                        next_episode_num += 1

                        # Safety check for unreasonably high episode numbers
                        # If we don't have season info and we're past episode 30, stop
                        if not season_finale_episode and next_episode_num > 30:
                            logger.debug(f"Stopping at episode 30 for {show_title} S{current_season} as safety measure")
                            break

                    # If we still need more episodes after exhausting the current season,
                    # start checking the next season from episode 1
                    remaining_count = count - len(missing_episodes)  # Update remaining count
                    if remaining_count > 0:
                        next_season = current_season + 1
                        next_episode_num = 1

                        # Check if the next season exists in Sonarr
                        next_season_exists = False
                        if season_info and next_season in season_info:
                            next_season_exists = True
                            next_season_finale = season_info[next_season]
                            logger.debug(f"{show_title} S{next_season} exists with {next_season_finale} episodes")

                        while len(missing_episodes) < count and remaining_count > 0:
                            # Check if we've hit the finale of the next season
                            if next_season_exists and next_episode_num > next_season_finale:
                                logger.debug(f"Reached finale of {show_title} S{next_season}")
                                break

                            # If this episode doesn't exist in Plex, add it to our download list
                            if (next_season, next_episode_num) not in available_episodes:
                                missing_episodes.append({
                                    'title': f"Episode {next_episode_num}",
                                    'season': next_season,
                                    'episode': next_episode_num,
                                    'key': None,
                                    'year': None,
                                    'summary': "First episode of next season" if next_episode_num == 1 else "Next episode"
                                })
                                episodes_needed -= 1
                                logger.debug(f"Added S{next_season:02d}E{next_episode_num:02d} to missing episodes, {episodes_needed} more needed")
                                remaining_count -= 1  # Decrement remaining count

                            # Move to the next episode
                            next_episode_num += 1

                            # Check if we're beyond what's reasonable for a season without season info
                            if not next_season_exists and next_episode_num > 30:
                                logger.debug(f"Stopping at episode 30 for {show_title} S{next_season} as safety measure")
                                break

                    # If we still need more episodes, look beyond what's in the library
                    remaining_count = count - len(missing_episodes)  # Update remaining count
                    if remaining_count > 0:
                        # Use the last episode in our missing_episodes list as reference
                        # If we have missing episodes already
                        if missing_episodes:
                            last_season = missing_episodes[-1]['season']
                            last_episode = missing_episodes[-1]['episode']
                            next_episode = last_episode + 1
                        else:
                            # If no missing episodes found yet, use reference episode
                            last_season = reference_episode.seasonNumber
                            next_episode = reference_episode.index + 1

                        for i in range(remaining_count):
                            if (last_season, next_episode + i) not in available_episodes:
                                missing_episodes.append({
                                    'title': f"Episode {next_episode + i}",
                                    'season': last_season,
                                    'episode': next_episode + i,
                                    'key': None,
                                    'year': None,
                                    'summary': "Next episode"
                                })
                                episodes_needed -= 1
                                logger.debug(f"Added S{last_season:02d}E{next_episode + i:02d} to missing episodes (fallback), {episodes_needed} more needed")

                    # If we found any missing episodes, add them to the results
                    if missing_episodes:
                        # Ensure we're only returning the requested count
                        results[plex_show.title] = missing_episodes[:count]
                        logger.debug(f"Found {len(missing_episodes)} missing episodes for {plex_show.title}, returning {len(results[plex_show.title])} as requested by count={count}")

            return results

        except Exception as e:
            print(f"Error getting next episodes: {str(e)}")
            return results
