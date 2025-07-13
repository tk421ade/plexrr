import os
from datetime import datetime, timezone
from typing import List, Dict

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

    def _parse_date(self, date_str) -> datetime:
        """Parse date string from Radarr API"""
        if not date_str:
            return datetime.now().replace(tzinfo=None)

        try:
            # Parse date and ensure it's timezone-naive for consistency
            dt = parser.parse(date_str)
            if dt.tzinfo is not None:
                dt = dt.replace(tzinfo=None)
            return dt
        except (ValueError, TypeError):
            return datetime.now().replace(tzinfo=None)
