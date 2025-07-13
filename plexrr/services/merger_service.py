from typing import List
from ..models.movie import Movie, Availability

def merge_movies(plex_movies: List[Movie], radarr_movies: List[Movie], 
                watchlist_movies: List[Movie]) -> List[Movie]:
    """Merge movies from Plex, Radarr, and Plex Watchlist"""
    merged_movies = {}

    # Process Plex movies first
    for movie in plex_movies:
        key = _generate_movie_key(movie)
        merged_movies[key] = movie

    # Process Radarr movies and merge with existing Plex movies
    for movie in radarr_movies:
        key = _generate_movie_key(movie)

        if key in merged_movies:
            # Movie exists in both Plex and Radarr
            existing_movie = merged_movies[key]
            existing_movie.availability = Availability.BOTH
            existing_movie.radarr_id = movie.radarr_id
            # Keep other metadata from Plex (watch status, dates, etc)
        else:
            # Movie only exists in Radarr
            merged_movies[key] = movie

    # Process watchlist and update existing movies or add new ones
    for movie in watchlist_movies:
        key = _generate_movie_key(movie)

        if key in merged_movies:
            # Update existing movie's watchlist status
            merged_movies[key].in_watchlist = True
        else:
            # Add new movie from watchlist
            merged_movies[key] = movie

    return list(merged_movies.values())

def _generate_movie_key(movie: Movie) -> str:
    """Generate a unique key for a movie to use in merging"""
    # Try to use external IDs first for better matching
    if movie.tmdb_id:
        return f"tmdb_{movie.tmdb_id}"
    elif movie.imdb_id:
        return f"imdb_{movie.imdb_id}"
    else:
        # Fallback to title-based matching
        return f"title_{movie.title.lower()}"
