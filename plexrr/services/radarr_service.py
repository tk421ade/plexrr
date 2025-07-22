import os
from datetime import datetime, timezone
from typing import List, Dict, Optional

import requests
from dateutil import parser

from ..models.movie import Movie, WatchStatus, Availability

class RadarrService:
    """Service for interacting with Radarr API"""

    def __init__(self, config: Dict):
        """Initialize Radarr service with configuration"""
        self.base_url = config['base_url']
        self.api_key = config['api_key']
        self.headers = {
            'X-Api-Key': self.api_key,
            'Content-Type': 'application/json'
        }

    def get_movie_details(self, movie_id) -> Dict:
        """Get detailed information about a specific movie from Radarr"""
        try:
            response = requests.get(
                f"{self.base_url}/api/v3/movie/{movie_id}", 
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error fetching movie details from Radarr: {str(e)}")
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
            print(f"Error fetching tags from Radarr: {str(e)}")
            return []

    def get_movies(self) -> List[Movie]:
        """Get all movies from Radarr"""
        try:
            response = requests.get(
                f"{self.base_url}/api/v3/movie", 
                headers=self.headers
            )
            response.raise_for_status()

            movies = []
            for radarr_movie in response.json():
                added_date = self._parse_date(radarr_movie.get('added'))

                # Get file path and size if available
                file_path = None
                file_size = None

                # Check if movie has file information
                if 'movieFile' in radarr_movie and radarr_movie['movieFile']:
                    movie_file = radarr_movie['movieFile']

                    # Get path from movie file
                    if 'path' in movie_file and movie_file['path']:
                        file_path = movie_file['path']

                    # Get size directly from Radarr API if available
                    if 'size' in movie_file and movie_file['size']:
                        file_size = movie_file['size']
                    # Otherwise try to get size from file system
                    elif file_path and os.path.exists(file_path):
                        file_size = os.path.getsize(file_path)


                # Create movie object
                movie = Movie(
                    title=radarr_movie.get('title'),
                    availability=Availability.RADARR,
                    watch_date=None,  # Radarr doesn't track watch status
                    progress_date=None,  # Radarr doesn't track progress
                    added_date=added_date,
                    watch_status=WatchStatus.NOT_WATCHED,  # Radarr doesn't track watch status
                    in_watchlist=False,  # Will be updated with watchlist data
                    file_size=file_size,
                    file_path=file_path,
                    radarr_id=radarr_movie.get('id'),
                    tmdb_id=radarr_movie.get('tmdbId'),
                    imdb_id=radarr_movie.get('imdbId')
                )

                movies.append(movie)

            return movies

        except requests.RequestException as e:
            print(f"Error fetching movies from Radarr: {str(e)}")
            return []

    def _parse_date(self, date_str) -> Optional[datetime]:
        """Parse date string from Radarr API"""
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

    def add_movie(self, movie: Movie, quality_profile_id: int) -> Dict:
        """Add a movie to Radarr

        Args:
            movie: Movie object with tmdb_id or imdb_id
            quality_profile_id: ID of the quality profile to use

        Returns:
            Dict with the response from Radarr API

        Raises:
            ValueError: If movie has no valid ID
            requests.RequestException: If API request fails
        """
        if not movie.tmdb_id and not movie.imdb_id:
            raise ValueError("Movie must have either TMDB ID or IMDB ID to be added to Radarr")

        # Get root folders to use the first one
        root_folders = self.get_root_folders()
        if not root_folders:
            raise ValueError("No root folders found in Radarr. Please configure at least one root folder.")

        root_folder_path = root_folders[0]['path']

        # Prepare the request data
        data = {
            "title": movie.title,
            "qualityProfileId": quality_profile_id,
            "monitored": True,
            "minimumAvailability": "released",
            "rootFolderPath": root_folder_path,
            "addOptions": {
                "searchForMovie": True
            }
        }

        # Add the appropriate ID
        if movie.tmdb_id:
            data["tmdbId"] = movie.tmdb_id
        elif movie.imdb_id:
            data["imdbId"] = movie.imdb_id

        try:
            response = requests.post(
                f"{self.base_url}/api/v3/movie", 
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
            print(f"Error adding movie to Radarr: {str(e)}")
            print(f"Request data: {data}")
            raise

    def get_quality_profiles(self) -> List[Dict]:
        """Get all quality profiles from Radarr

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
            print(f"Error fetching quality profiles from Radarr: {str(e)}")
            raise

    def get_root_folders(self) -> List[Dict]:
        """Get all root folders from Radarr

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
            print(f"Error fetching root folders from Radarr: {str(e)}")
            raise
