# PlexRR

A Python command-line tool to manage media across Plex, Radarr, and Sonarr.

## Features

- List all movies from Plex and Radarr with merged information
- List all TV shows from Plex and Sonarr with merged information
- View media availability across platforms
- Track watch status and history
- See which movies and TV shows are in your Plex Watchlist
- Manage watched episodes by finding and deleting old content
- Automate actions using Plex webhooks (e.g., auto-download next episodes when finishing a show)

## Installation

### For Development
```bash
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

### For Prod [coming soon]
```bash
pip install plexrr
```

### Bash Auto-Completion

To enable tab completion in Bash:

```bash
# Generate and install the completion script
plexrr completion

# Or if you want to save it to a specific location
plexrr completion --path /path/to/your/completion/script

# Print the script to stdout (for manual installation)
plexrr completion --print > ~/plexrr-completion.bash
source ~/plexrr-completion.bash
```

You can add the source command to your `~/.bashrc` or `~/.bash_profile` to enable completion automatically when you start a new shell:

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
  base_url: http://localhost:32400
  token: your-plex-token

  # Option 1: Use Plex account credentials for watchlist
  # username: your-plex-username
  # password: your-plex-password

  # Option 2: Use RSS feed URL for watchlist (recommended)
  watchlist_rss: https://rss.plex.tv/your-unique-watchlist-id

radarr:
  base_url: http://localhost:7878
  api_key: your-radarr-api-key

# Optional: Configure Sonarr for TV shows
sonarr:
  base_url: http://localhost:8989
  api_key: your-sonarr-api-key

# Optional: Configure webhooks for automated actions
webhooks:
  # Event triggered when an episode is marked as watched
  after-watched:
    - download-next --count 2 --execute
    - delete-watched --days 0 --execute
```

3. Validate your configuration:

```bash
plexrr config validate
```

### Webhook Setup

To use the webhook functionality for automating actions based on Plex events:

1. Configure webhook actions in your `config.yml`:

```yaml
webhooks:
  after-watched:
    - download-next --count 2 --execute
    - delete-watched --days 0 --execute
```

2. Start the webhook server:

```bash
plexrr webhook start
```

3. Configure Plex to send webhooks:
   - Log in to your Plex account at https://app.plex.tv
   - Go to Settings → Account
   - Scroll down to find the "Webhooks" section
   - Click "Add Webhook"
   - Enter the URL of your webhook server: `http://YOUR_SERVER_IP:9876/webhook`
     (Replace YOUR_SERVER_IP with the IP address where plexrr is running)
   - Click "Save Changes"

   Note: You need a Plex Pass subscription to use webhooks feature in Plex.

   ![Plex Webhook Configuration](https://support.plex.tv/wp-content/uploads/sites/4/2018/02/webhook-1-en.png)

4. Test the webhook is working:
   - Start the webhook server with debug mode: `plexrr webhook start --foreground --debug`
   - Play and then finish watching something in Plex
   - You should see events logged and the configured commands executed

5. For a permanent setup, use the provided systemd service:

```bash
sudo cp /path/to/plexrr/resources/plexrr-webhook.service /etc/systemd/system/plexrr-webhook@<username>.service
sudo systemctl daemon-reload
sudo systemctl enable plexrr-webhook@<username>.service
sudo systemctl start plexrr-webhook@<username>.service
```

   The contents of the service file should look like this:

```ini
[Unit]
Description=PlexRR Webhook Server for Plex automation
After=network.target

[Service]
Type=simple
User=%i
ExecStart=/usr/bin/env plexrr webhook start --foreground
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

   Note: The service file uses `/usr/bin/env` to find the plexrr executable automatically, regardless of where pip installed it. If you need to specify the exact path, you can find it by running:

```bash
which plexrr
```

5. Monitor the service logs using journalctl:

```bash
# Follow logs in real-time
sudo journalctl -u plexrr-webhook@<username>.service -f

# View last 100 log entries
sudo journalctl -u plexrr-webhook@<username>.service -n 100
```

See the full documentation in `plexrr/docs/webhooks.md` for more details on available events and advanced configuration.

### Configuration Details

- **Plex token**: To find your Plex token, follow the instructions at [Plex Support](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/)
- **Radarr/Sonarr API keys**: Find these in the settings of your Radarr/Sonarr web interface under Settings → General → Security

### Troubleshooting

If you get a configuration error:

1. Run `plexrr config validate` to check your configuration
2. Ensure that all servers are running and accessible
3. Check for typos in URLs and API keys
4. Make sure the required `radarr` section is present

### Webhook Troubleshooting

If webhooks are not working:

1. Run `plexrr config validate --verbose` to check that your webhook configuration is being loaded correctly
2. Verify the webhook server is running with `plexrr webhook status`
3. Enable debug logging to see detailed information including request payloads:
   ```bash
   # Run in foreground with debug logging to a file
   plexrr webhook start --foreground --debug --log-file webhook.log

   # Or to see everything in the terminal:
   plexrr webhook start --foreground --debug
   ```
4. Check the webhook server logs:
   - When running in foreground mode: output appears in terminal
   - When running as systemd service: `sudo journalctl -u plexrr-webhook@<username>.service`
   - When using log file: `tail -f webhook.log`
5. Ensure your server is accessible from the internet (or from your Plex server)
6. Verify port 9876 is open in your firewall
7. Confirm you have a Plex Pass subscription (required for webhooks)
8. Try testing the webhook manually with various content types:

```bash
# Test with JSON content type
curl -X POST -H "Content-Type: application/json" \
  -d '{"event":"media.scrobble", "Account":{"title":"test"}, "Metadata":{"type":"episode"}}' \
  http://localhost:9876/webhook

# Test with form-encoded data (how Plex sometimes sends it)
curl -X POST -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode 'payload={"event":"media.scrobble", "Account":{"title":"test"}, "Metadata":{"type":"episode"}}' \
  http://localhost:9876/webhook
```

9. Common error codes:
   - `415 Unsupported Media Type`: The webhook server couldn't parse your request. Enable debug logging to see the actual request content.
   - `400 Bad Request`: The webhook payload is missing required fields.
   - `500 Internal Server Error`: An exception occurred while processing the webhook. Check logs for details.

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

# Find and suggest next episodes to download for shows you're watching
plexrr download-next                   # Suggest next episodes to download
plexrr download-next --count 3         # Suggest 3 next episodes per show (default: 1)
plexrr download-next --show-id 123     # Only suggest for a specific show
plexrr download-next --confirm --quality-profile 1  # Actually request downloads in Sonarr

# Webhook server for automating actions from Plex events
plexrr webhook start                        # Start the webhook server as a daemon
plexrr webhook start --foreground           # Start the webhook server in the foreground
plexrr webhook start --port 9876            # Specify a custom port (default: 9876)
plexrr webhook start --debug                # Enable debug logging with full request/response details
plexrr webhook start --log-file /path/to/log # Log to file instead of console
plexrr webhook stop                         # Stop the webhook server
plexrr webhook status                       # Check if the webhook server is running
```

## License

MIT
