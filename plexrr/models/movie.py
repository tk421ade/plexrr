from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

class WatchStatus(Enum):
    NOT_WATCHED = "Not Watched"
    IN_PROGRESS = "In Progress"
    WATCHED = "Watched"

class Availability(Enum):
    PLEX = "Plex"
    RADARR = "Radarr"
    BOTH = "Both"

@dataclass
class Movie:
    """Movie data model with information from both Plex and Radarr"""
    title: str
    availability: Availability
    watch_date: Optional[datetime] = None
    added_date: datetime = None
    watch_status: WatchStatus = WatchStatus.NOT_WATCHED
    in_watchlist: bool = False

    # IDs to help with merging
    plex_id: Optional[str] = None
    radarr_id: Optional[int] = None
    tmdb_id: Optional[int] = None
    imdb_id: Optional[str] = None
