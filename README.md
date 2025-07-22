# PlexRR

A Python command-line tool to manage movies across Plex and Radarr.

## Features

- List all movies from Plex and Radarr with merged information
- View movie availability across platforms
- Track watch status and history
- See which movies are in your Plex Watchlist

## Installation

```bash
pip install plexrr
```

## Configuration

Create a `config.yml` file in the `~/.config/plexrr/` directory:

```yaml
plex:
  base_url: "http://localhost:32400"
  token: "your-plex-token"

  # Option 1: Use Plex account credentials for watchlist
  # username: "your-plex-username"
  # password: "your-plex-password"

  # Option 2: Use RSS feed URL for watchlist (recommended)
  watchlist_rss: "https://rss.plex.tv/your-unique-watchlist-id"

radarr:
  base_url: "http://localhost:7878"
  api_key: "your-radarr-api-key"
```

## Usage

```bash
# List all movies
plexrr list

# Sort by date added/watched
plexrr list --sort-by date

# Filter options
plexrr list --has-size             # Only movies with file size
plexrr list --no-size              # Only movies without file size
plexrr list --days 10              # Only movies older than 10 days
plexrr list --watchlist            # Only movies in watchlist
plexrr list --no-watchlist         # Only movies not in watchlist
plexrr list --availability plex    # Only movies available in Plex
plexrr list --availability radarr  # Only movies available in Radarr
plexrr list --availability both    # Only movies available in both
plexrr list --status watched       # Only watched movies
plexrr list --status in_progress   # Only in-progress movies
plexrr list --status not_watched   # Only unwatched movies
plexrr list --tag auto             # Only movies with specified Radarr tag

# Combine multiple filters
plexrr list --sort-by date --availability plex --status watched

# Get available quality profiles from Radarr
plexrr profiles

# Get available root folders from Radarr
plexrr folders

# Sync movies from Plex to Radarr
plexrr sync --quality-profile 1    # Add movies in Plex but not in Radarr
plexrr sync --quality-profile 1 --confirm  # Ask for confirmation for each movie
plexrr sync --quality-profile 1 --dry-run  # Show what would be done without changes
plexrr sync --quality-profile 1 --verbose  # Show detailed debug information

# Clean duplicate movie versions (keep only best quality)
plexrr clean                     # Remove lower quality versions automatically
plexrr clean --confirm           # Ask for confirmation before each deletion
plexrr clean --dry-run           # Show what would be removed without making changes
plexrr clean --verbose           # Show detailed debug information
```

## License

MIT
