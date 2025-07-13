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
```

## License

MIT
