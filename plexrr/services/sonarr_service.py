import os
import requests
from typing import Dict, List, Optional
from datetime import datetime
from dateutil import parser
from ..models.tvshow import TVShow
from ..models.movie import WatchStatus, Availability

class SonarrService:
    """Service for interacting with Sonarr API"""

    def __init__(self, config: Dict):
        """Initialize Sonarr service with configuration"""
        self.base_url = config['base_url']
        self.api_key = config['api_key']
        self.headers = {
            'X-Api-Key': self.api_key,
            'Content-Type': 'application/json'
        }

    def get_show_details(self, show_id) -> Dict:
        """Get detailed information about a specific TV show from Sonarr"""
        try:
            response = requests.get(
                f"{self.base_url}/api/v3/series/{show_id}", 
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error fetching show details from Sonarr: {str(e)}")
            return {}

    def get_tag_names(self, tag_ids) -> List[str]:
        """Get tag names from tag IDs"""
        if not tag_ids:
            return []

        try:
            # Get all tags
            response = requests.get(
                f"{self.base_url}/api/v3/tag", 
                headers=self.headers
            )
            response.raise_for_status()
            all_tags = response.json()

            # Filter to just the tags we need
            tag_names = []
            for tag in all_tags:
                if tag['id'] in tag_ids:
                    tag_names.append(tag['label'])

            return tag_names
        except requests.RequestException as e:
            print(f"Error fetching tags from Sonarr: {str(e)}")
            return []

    def get_shows(self) -> List[TVShow]:
        """Get all TV shows from Sonarr"""
        try:
            response = requests.get(
                f"{self.base_url}/api/v3/series", 
                headers=self.headers
            )
            response.raise_for_status()

            shows = []
            for sonarr_show in response.json():
                added_date = self._parse_date(sonarr_show.get('added'))

                # Get episode count and season count
                season_count = len(sonarr_show.get('seasons', []))
                episode_count = sum(season.get('statistics', {}).get('episodeCount', 0) 
                                   for season in sonarr_show.get('seasons', []))

                # Get total size information
                file_size = sum(season.get('statistics', {}).get('sizeOnDisk', 0) 
                              for season in sonarr_show.get('seasons', []))

                # Create TV show object
                show = TVShow(
                    title=sonarr_show.get('title'),
                    availability=Availability.SONARR,
                    watch_date=None,  # Sonarr doesn't track watch status
                    progress_date=None,  # Sonarr doesn't track progress
                    added_date=added_date,
                    watch_status=WatchStatus.NOT_WATCHED,  # Sonarr doesn't track watch status
                    in_watchlist=False,  # Will be updated with watchlist data
                    file_size=file_size,
                    episode_count=episode_count,
                    season_count=season_count,
                    sonarr_id=sonarr_show.get('id'),
                    tvdb_id=sonarr_show.get('tvdbId'),
                    imdb_id=sonarr_show.get('imdbId')
                )

                shows.append(show)

            return shows

        except requests.RequestException as e:
            print(f"Error fetching TV shows from Sonarr: {str(e)}")
            return []

    def _parse_date(self, date_str) -> Optional[datetime]:
        """Parse date string from Sonarr API"""
        if not date_str:
            return None

        try:
            # Parse date and ensure it's timezone-naive for consistency
            dt = parser.parse(date_str)
            if dt.tzinfo is not None:
                dt = dt.replace(tzinfo=None)
            return dt
        except (ValueError, TypeError):
            return None

    def add_show(self, show: TVShow, quality_profile_id: int) -> Dict:
        """Add a TV show to Sonarr

        Args:
            show: TVShow object with tvdb_id or imdb_id
            quality_profile_id: ID of the quality profile to use

        Returns:
            Dict with the response from Sonarr API
        """
        if not show.tvdb_id and not show.imdb_id:
            raise ValueError("TV show must have either TVDB ID or IMDB ID to be added to Sonarr")

        # Get root folders to use the first one
        root_folders = self.get_root_folders()
        if not root_folders:
            raise ValueError("No root folders found in Sonarr. Please configure at least one root folder.")

        root_folder_path = root_folders[0]['path']

        # Prepare the request data
        data = {
            "title": show.title,
            "qualityProfileId": quality_profile_id,
            "monitored": True,
            "rootFolderPath": root_folder_path,
            "addOptions": {
                "searchForMissingEpisodes": True
            }
        }

        # Add the appropriate ID
        if show.tvdb_id:
            data["tvdbId"] = show.tvdb_id
        elif show.imdb_id:
            data["imdbId"] = show.imdb_id

        try:
            response = requests.post(
                f"{self.base_url}/api/v3/series", 
                headers=self.headers,
                json=data
            )

            # If there's an error, get more detailed information
            if not response.ok:
                error_msg = f"{response.status_code} {response.reason} for url: {response.url}"
                try:
                    error_detail = response.json()
                    error_msg += f"\nAPI Error: {error_detail}"
                except:
                    error_msg += f"\nResponse text: {response.text[:200]}"
                error_msg += f"\nRequest data: {data}"
                raise requests.HTTPError(error_msg, response=response)

            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error adding TV show to Sonarr: {str(e)}")
            print(f"Request data: {data}")
            raise

    def get_quality_profiles(self) -> List[Dict]:
        """Get all quality profiles from Sonarr

        Returns:
            List of quality profiles with id and name

        Raises:
            requests.RequestException: If API request fails
        """
        try:
            response = requests.get(
                f"{self.base_url}/api/v3/qualityprofile", 
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error fetching quality profiles from Sonarr: {str(e)}")
            raise

    def get_root_folders(self) -> List[Dict]:
        """Get all root folders from Sonarr

        Returns:
            List of root folders with path and id

        Raises:
            requests.RequestException: If API request fails
        """
        try:
            response = requests.get(
                f"{self.base_url}/api/v3/rootfolder", 
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error fetching root folders from Sonarr: {str(e)}")
            raise

    def delete_show(self, show_id: int, delete_files: bool = True) -> bool:
        """Delete a TV show from Sonarr and optionally its files

        Args:
            show_id: Sonarr show ID to delete
            delete_files: Whether to also delete files

        Returns:
            True if successful, False otherwise

        Raises:
            requests.RequestException: If API request fails
        """
        try:
            response = requests.delete(
                f"{self.base_url}/api/v3/series/{show_id}?deleteFiles={str(delete_files).lower()}", 
                headers=self.headers
            )
            response.raise_for_status()
            return True
        except requests.RequestException as e:
            print(f"Error deleting TV show from Sonarr: {str(e)}")
            raise

    def find_show_by_title(self, title: str) -> Optional[Dict]:
        """Find a show in Sonarr by its title

        Args:
            title: The show title to search for

        Returns:
            Show information or None if not found
        """
        try:
            # Get all shows from Sonarr
            response = requests.get(
                f"{self.base_url}/api/v3/series", 
                headers=self.headers
            )
            response.raise_for_status()
            shows = response.json()

            # Find matching show (case-insensitive)
            for show in shows:
                if show['title'].lower() == title.lower():
                    return show

            # If no exact match, try partial match
            for show in shows:
                if title.lower() in show['title'].lower():
                    return show

            return None
        except requests.RequestException as e:
            print(f"Error searching for show in Sonarr: {str(e)}")
            return None

    def get_episodes_by_series_id(self, series_id: int) -> List[Dict]:
        """Get all episodes for a specific series

        Args:
            series_id: Sonarr series ID

        Returns:
            List of episode information
        """
        try:
            response = requests.get(
                f"{self.base_url}/api/v3/episode?seriesId={series_id}", 
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error getting episodes from Sonarr: {str(e)}")
            return []

    def find_episode(self, series_id: int, season_number: int, episode_number: int) -> Optional[Dict]:
        """Find a specific episode by series ID, season and episode number

        Args:
            series_id: Sonarr series ID
            season_number: Season number
            episode_number: Episode number

        Returns:
            Episode information or None if not found
        """
        try:
            episodes = self.get_episodes_by_series_id(series_id)
            for episode in episodes:
                if (episode.get('seasonNumber') == season_number and 
                    episode.get('episodeNumber') == episode_number):
                    return episode
            return None
        except Exception as e:
            print(f"Error finding episode: {str(e)}")
            return None

    def request_episode_download(self, series_id: int, season_number: int, episode_number: int) -> bool:
        """Request download for a specific episode

        Args:
            series_id: Sonarr series ID
            season_number: Season number
            episode_number: Episode number

        Returns:
            True if successful, False otherwise
        """
        try:
            # First find the episode to get its ID
            episode = self.find_episode(series_id, season_number, episode_number)
            if not episode:
                print(f"Episode S{season_number:02d}E{episode_number:02d} not found for series ID {series_id}")
                return False

            episode_id = episode.get('id')

            # Request a search for this episode
            response = requests.post(
                f"{self.base_url}/api/v3/command", 
                headers=self.headers,
                json={"name": "EpisodeSearch", "episodeIds": [episode_id]}
            )
            response.raise_for_status()

            # Also set the episode to monitored if it isn't already
            if not episode.get('monitored', False):
                episode['monitored'] = True
                update_response = requests.put(
                    f"{self.base_url}/api/v3/episode/{episode_id}",
                    headers=self.headers,
                    json=episode
                )
                update_response.raise_for_status()

            return True
        except Exception as e:
            print(f"Error requesting episode download: {str(e)}")
            return False

    def search_episode(self, episode_id: int) -> bool:
        """Request a search for a specific episode

        Args:
            episode_id: Sonarr episode ID to search for

        Returns:
            True if search was initiated successfully
        """
        try:
            data = {"episodeIds": [episode_id]}
            response = requests.post(
                f"{self.base_url}/api/v3/command", 
                headers=self.headers,
                json={"name": "EpisodeSearch", "episodeIds": [episode_id]}
            )
            response.raise_for_status()
            return True
        except requests.RequestException as e:
            print(f"Error initiating episode search in Sonarr: {str(e)}")
            return False


    def search_season_episodes(self, series_id: int, season_number: int) -> bool:
        """Request a search for all episodes in a specific season

        Args:
            series_id: Sonarr series ID
            season_number: Season number to search for

        Returns:
            True if search was initiated successfully
        """
        try:
            response = requests.post(
                f"{self.base_url}/api/v3/command", 
                headers=self.headers,
                json={"name": "SeasonSearch", "seriesId": series_id, "seasonNumber": season_number}
            )
            response.raise_for_status()
            return True
        except requests.RequestException as e:
            print(f"Error initiating season search in Sonarr: {str(e)}")
            return False

