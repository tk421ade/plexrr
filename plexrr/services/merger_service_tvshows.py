from typing import List
from ..models.tvshow import TVShow
from ..models.movie import Availability, WatchStatus
from .utils import normalize_title

def _generate_show_key(show: TVShow) -> str:
    """Generate a unique key for a TV show for merging purposes"""
    # Use the most specific ID available
    if show.tvdb_id:
        return f"tvdb:{show.tvdb_id}"
    elif show.imdb_id:
        return f"imdb:{show.imdb_id}"
    elif show.plex_id:
        return f"plex:{show.plex_id}"
    elif show.sonarr_id:
        return f"sonarr:{show.sonarr_id}"
    else:
        # Normalize title to improve matching
        normalized_title = show.title.lower()
        return f"title:{normalized_title}"

def merge_tv_shows(plex_shows: List[TVShow], sonarr_shows: List[TVShow], 
                 watchlist_shows: List[TVShow]) -> List[TVShow]:
    """Merge TV shows from Plex, Sonarr, and Plex Watchlist"""
    merged_shows = {}

    # Process Plex shows first
    for show in plex_shows:
        key = _generate_show_key(show)
        merged_shows[key] = show

    # Process Sonarr shows and merge with existing Plex shows
    for show in sonarr_shows:
        key = _generate_show_key(show)

        if key in merged_shows:
            # Show exists in both Plex and Sonarr
            existing_show = merged_shows[key]
            existing_show.availability = Availability.BOTH
            existing_show.sonarr_id = show.sonarr_id

            # Use file size from either source, prioritizing the larger one for better accuracy
            if show.file_size is not None:
                if existing_show.file_size is None:
                    existing_show.file_size = show.file_size
                else:
                    # If both have file size, use the larger one (which likely includes more episodes)
                    existing_show.file_size = max(existing_show.file_size, show.file_size)

            # Use episode and season counts from Sonarr if Plex doesn't have them
            if existing_show.episode_count is None and show.episode_count is not None:
                existing_show.episode_count = show.episode_count
            if existing_show.season_count is None and show.season_count is not None:
                existing_show.season_count = show.season_count

            # Use Sonarr's added date if Plex doesn't have one
            if existing_show.added_date is None and show.added_date is not None:
                existing_show.added_date = show.added_date
        else:
            # Show only exists in Sonarr
            merged_shows[key] = show

    # Process watchlist and update existing shows or add new ones
    for show in watchlist_shows:
        key = _generate_show_key(show)

        if key in merged_shows:
            # Update existing show's watchlist status
            merged_shows[key].in_watchlist = True
        else:
            # Add new show from watchlist
            merged_shows[key] = show

    return list(merged_shows.values())

def merge_tv_shows(plex_shows: List[TVShow], sonarr_shows: List[TVShow], watchlist_shows: List[TVShow]) -> List[TVShow]:
    """Merge TV shows from Plex, Sonarr, and Watchlist

    Args:
        plex_shows: List of TV shows from Plex
        sonarr_shows: List of TV shows from Sonarr
        watchlist_shows: List of TV shows from Plex Watchlist

    Returns:
        List of merged TV shows
    """
    # Create a dictionary to store merged shows by TVDB ID, IMDB ID, and title
    merged_by_tvdb = {}
    merged_by_imdb = {}
    merged_by_title = {}

    # First, add all Plex shows to the merged dictionaries
    for show in plex_shows:
        if show.tvdb_id:
            merged_by_tvdb[show.tvdb_id] = show
        elif show.imdb_id:
            merged_by_imdb[show.imdb_id] = show
        else:
            # Normalize title for matching
            title_key = normalize_title(show.title)
            merged_by_title[title_key] = show

    # Add Sonarr shows, merging with existing Plex shows when possible
    for show in sonarr_shows:
        # Try to match by TVDB ID first
        if show.tvdb_id and show.tvdb_id in merged_by_tvdb:
            # Update existing show
            existing = merged_by_tvdb[show.tvdb_id]
            existing.availability = Availability.BOTH
            existing.sonarr_id = show.sonarr_id
            # Keep other Sonarr-specific data if needed
        elif show.imdb_id and show.imdb_id in merged_by_imdb:
            # Update existing show
            existing = merged_by_imdb[show.imdb_id]
            existing.availability = Availability.BOTH
            existing.sonarr_id = show.sonarr_id
            # Keep other Sonarr-specific data if needed
        else:
            # Try to match by title
            title_key = normalize_title(show.title)
            if title_key in merged_by_title:
                # Update existing show
                existing = merged_by_title[title_key]
                existing.availability = Availability.BOTH
                existing.sonarr_id = show.sonarr_id
                # Keep other Sonarr-specific data if needed
            else:
                # No match found, add as Sonarr-only show
                show.availability = Availability.SONARR
                # Add to merged dictionaries
                if show.tvdb_id:
                    merged_by_tvdb[show.tvdb_id] = show
                elif show.imdb_id:
                    merged_by_imdb[show.imdb_id] = show
                merged_by_title[title_key] = show

    # Update watchlist status
    for show in watchlist_shows:
        # Try to match by TVDB ID first
        if show.tvdb_id and show.tvdb_id in merged_by_tvdb:
            merged_by_tvdb[show.tvdb_id].in_watchlist = True
        elif show.imdb_id and show.imdb_id in merged_by_imdb:
            merged_by_imdb[show.imdb_id].in_watchlist = True
        else:
            # Try to match by title
            title_key = normalize_title(show.title)
            if title_key in merged_by_title:
                merged_by_title[title_key].in_watchlist = True
            else:
                # No match found, add as watchlist-only show
                show.in_watchlist = True
                # Set as Plex-only since it's in the Plex watchlist
                show.availability = Availability.PLEX
                # Add to merged dictionaries
                if show.tvdb_id:
                    merged_by_tvdb[show.tvdb_id] = show
                elif show.imdb_id:
                    merged_by_imdb[show.imdb_id] = show
                merged_by_title[title_key] = show

    # Collect all unique shows from the dictionaries
    all_shows = set()
    all_shows.update(merged_by_tvdb.values())
    all_shows.update(merged_by_imdb.values())
    all_shows.update(merged_by_title.values())

    return list(all_shows)