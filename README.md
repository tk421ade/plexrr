# PlexRR

A Python command-line tool to manage media across Plex, Radarr, and Sonarr.

## Features

- List all movies from Plex and Radarr with merged information
- List all TV shows from Plex and Sonarr with merged information
- View media availability across platforms
- Track watch status and history
- See which movies and TV shows are in your Plex Watchlist
- Manage watched episodes by finding and deleting old content

## Installation

```bash
pip install plexrr
```

## Configuration

You can create a configuration file in several ways:

1. Generate a template configuration with the built-in command:

```bash
# Create a default configuration file in the default location
plexrr config create

# Create a configuration file in a specific location
plexrr config create --path ./config.yml
```

2. Manually create a `config.yml` file in the `~/.config/plexrr/` directory or in your current working directory:

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

# Optional: Configure Sonarr for TV shows
sonarr:
  base_url: "http://localhost:8989"
  api_key: "your-sonarr-api-key"
```

3. Validate your configuration:

```bash
plexrr config validate
```

### Configuration Details

- **Plex token**: To find your Plex token, follow the instructions at [Plex Support](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/)
- **Radarr/Sonarr API keys**: Find these in the settings of your Radarr/Sonarr web interface under Settings → General → Security

### Troubleshooting

If you get a configuration error:

1. Run `plexrr config validate` to check your configuration
2. Ensure that all servers are running and accessible
3. Check for typos in URLs and API keys
4. Make sure the required `radarr` section is present

## Usage

```bash
# List all media (movies and TV shows)
plexrr list

# List only movies or TV shows
plexrr list --type movies
plexrr list --type shows

# Sort by date added/watched
plexrr list --sort-by date

# Use the ID column to get the show-id for use with other commands
# For example, use with delete-watched command:
plexrr delete-watched --show-id 12345

# Filter options
plexrr list --has-size             # Only media with file size
plexrr list --no-size              # Only media without file size
plexrr list --days 10              # Only media older than 10 days
plexrr list --watchlist            # Only media in watchlist
plexrr list --no-watchlist         # Only media not in watchlist
plexrr list --availability plex    # Only media available in Plex
plexrr list --availability radarr  # Only movies available in Radarr
plexrr list --availability sonarr  # Only TV shows available in Sonarr
plexrr list --availability both    # Only media available in both services
plexrr list --status watched       # Only watched media
plexrr list --status in_progress   # Only in-progress media
plexrr list --status not_watched   # Only unwatched media
plexrr list --tag auto             # Only media with specified tag

# Combine multiple filters
plexrr list --sort-by date --availability plex --status watched --type shows

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

# Delete movies from Radarr based on filters
plexrr delete                    # Show what would be deleted (dry run)
plexrr delete --execute          # Actually delete the movies and their files
plexrr delete --confirm          # Ask for confirmation before each deletion
plexrr delete --has-size         # Only delete movies with files
plexrr delete --no-size          # Only delete movies without files
plexrr delete --days 60          # Only delete movies older than 60 days
plexrr delete --watchlist        # Only delete movies in watchlist
plexrr delete --no-watchlist     # Only delete movies not in watchlist
plexrr delete --availability radarr  # Only delete movies only in Radarr
plexrr delete --status watched   # Only delete watched movies
plexrr delete --tag unwanted     # Only delete movies with specific tag

# Find and optionally delete watched TV episodes from Plex
plexrr delete-watched                # Shows what would be deleted (dry run)
plexrr delete-watched --execute      # Actually delete the watched episodes
plexrr delete-watched --confirm      # Ask for confirmation before each deletion when using --execute
plexrr delete-watched --days 30      # Only process episodes watched more than 30 days ago (default: 10)
plexrr delete-watched --show-id 123  # Only process episodes from a specific show
plexrr delete-watched --skip-pilots  # Skip the first episode (S01E01) of each series
plexrr delete-watched --verbose      # Show detailed debug information
```

## License

MIT
