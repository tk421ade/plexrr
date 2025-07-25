from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional
import humanize

class WatchStatus(Enum):
    NOT_WATCHED = "Not Watched"
    IN_PROGRESS = "In Progress"
    WATCHED = "Watched"

class Availability(Enum):
    PLEX = "Plex"
    RADARR = "Radarr"
    SONARR = "Sonarr"
    BOTH = "Both"

@dataclass
class Movie:
    """Movie data model with information from both Plex and Radarr"""
    title: str
    availability: Availability
    watch_date: Optional[datetime] = None  # For WATCHED movies
    progress_date: Optional[datetime] = None  # For IN_PROGRESS movies
    added_date: Optional[datetime] = None  # When added to Plex/Radarr
    watch_status: WatchStatus = WatchStatus.NOT_WATCHED
    in_watchlist: bool = False
    file_size: Optional[int] = None  # File size in bytes
    file_path: Optional[str] = None  # Path to the movie file

    # IDs to help with merging
    plex_id: Optional[str] = None
    radarr_id: Optional[int] = None
    tmdb_id: Optional[int] = None
    imdb_id: Optional[str] = None

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

        relative_time = humanize.naturaltime(now - date)

        # Show both date and whether it's a watch date or added date
        return f"{absolute_date} [{date_type}] ({relative_time})"
