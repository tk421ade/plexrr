from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from .movie import WatchStatus, Availability

@dataclass(eq=False)
class TVShow:
    """TV Show data model with information from both Plex and Sonarr"""
    title: str
    availability: Availability
    watch_date: Optional[datetime] = None  # For WATCHED shows
    progress_date: Optional[datetime] = None  # For IN_PROGRESS shows
    added_date: Optional[datetime] = None  # When added to Plex/Sonarr
    watch_status: WatchStatus = WatchStatus.NOT_WATCHED
    in_watchlist: bool = False
    file_size: Optional[int] = None  # Total size of all episodes
    episode_count: Optional[int] = None  # Number of episodes
    season_count: Optional[int] = None  # Number of seasons

    # IDs to help with merging
    plex_id: Optional[str] = None
    sonarr_id: Optional[int] = None
    tvdb_id: Optional[int] = None
    imdb_id: Optional[str] = None

    def __hash__(self):
        """Make TVShow hashable for use in sets and as dictionary keys"""
        # Create a hashable tuple of identifying attributes
        # Use the most specific ID available, fall back to title if no IDs
        if self.tvdb_id:
            return hash(('tvdb', self.tvdb_id))
        elif self.imdb_id:
            return hash(('imdb', self.imdb_id))
        elif self.plex_id:
            return hash(('plex', self.plex_id))
        elif self.sonarr_id:
            return hash(('sonarr', self.sonarr_id))
        else:
            # Fall back to title-based hash
            # Normalize title to improve matching
            normalized_title = self.title.lower()
            return hash(('title', normalized_title))

    def __eq__(self, other):
        """Compare TVShows for equality"""
        if not isinstance(other, TVShow):
            return False

        # If both have TVDB ID, compare those
        if self.tvdb_id and other.tvdb_id:
            return self.tvdb_id == other.tvdb_id

        # If both have IMDB ID, compare those
        if self.imdb_id and other.imdb_id:
            return self.imdb_id == other.imdb_id

        # If we have matching Plex IDs
        if self.plex_id and other.plex_id:
            return self.plex_id == other.plex_id

        # If we have matching Sonarr IDs
        if self.sonarr_id and other.sonarr_id:
            return self.sonarr_id == other.sonarr_id

        # Fall back to title comparison
        return self.title.lower() == other.title.lower()

    def get_formatted_size(self) -> str:
        """Return formatted file size (KB, MB, GB) or 'N/A' if not available"""
        if self.file_size is None:
            return "N/A"

        # Convert to appropriate unit
        kb = 1024
        mb = kb * 1024
        gb = mb * 1024
        tb = gb * 1024

        if self.file_size >= tb:
            return f"{self.file_size / tb:.2f} TB"
        elif self.file_size >= gb:
            return f"{self.file_size / gb:.2f} GB"
        elif self.file_size >= mb:
            return f"{self.file_size / mb:.2f} MB"
        elif self.file_size >= kb:
            return f"{self.file_size / kb:.2f} KB"
        else:
            return f"{self.file_size} B"

    def get_formatted_date(self) -> str:
        """Return formatted date with relative time"""
        # Priority based on watch status
        if self.watch_status == WatchStatus.WATCHED and self.watch_date:
            date = self.watch_date
            date_type = "watched"
        elif self.watch_status == WatchStatus.IN_PROGRESS and self.progress_date:
            date = self.progress_date
            date_type = "in progress"
        elif self.added_date:
            date = self.added_date
            date_type = "added"
        else:
            return "Unknown"

        # Format as absolute date and relative time
        absolute_date = date.strftime('%Y-%m-%d')

        # Make sure both datetimes are timezone-naive for comparison
        now = datetime.now()
        if date.tzinfo is not None:
            # If date has timezone, use a timezone-aware now
            now = now.astimezone(date.tzinfo)
        else:
            # If date is naive, make sure now is also naive
            now = now.replace(tzinfo=None)

        import humanize
        relative_time = humanize.naturaltime(now - date)

        # Show both date and whether it's a watch date or added date
        return f"{absolute_date} [{date_type}] ({relative_time})"

    def get_formatted_episodes(self) -> str:
        """Return formatted episode and season count"""
        if self.episode_count is None or self.season_count is None:
            return "N/A"
        return f"{self.episode_count} eps, {self.season_count} seasons"
