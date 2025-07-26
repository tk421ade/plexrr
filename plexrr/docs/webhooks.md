# PlexRR Webhook Setup Guide
# PlexRR Webhook Documentation

## Overview

PlexRR includes a webhook server that can receive events from Plex Media Server and trigger automated actions based on those events. This feature allows you to automate tasks like downloading the next episodes of a show after you've watched an episode, or cleaning up old watched content.

## Requirements

- A Plex Pass subscription (required for Plex webhook functionality)
- Network connectivity between your Plex server and the device running PlexRR

## Configuration

Webhooks are configured in your `config.yml` file. You can define different actions for various Plex events.

### Configuration Format

```yaml
webhooks:
  # Event triggered when an episode is marked as watched
  after-watched:
    - download-next --count 2 --execute
    - delete-watched --days 0 --execute

  # Event triggered when playback starts
  on-play: []

  # Event triggered when playback is paused
  on-pause: []

  # Event triggered when playback resumes after pause
  on-resume: []

  # Event triggered when playback stops before completion
  on-stop: []

  # Event triggered when a user rates media
  on-rate: []

  # Event triggered when new content is added to the library
  on-added: []
```

### Supported Events

| Config Key | Plex Event | Description |
|------------|------------|--------------|
| `after-watched` | `media.scrobble` | Triggered when media is marked as watched |
| `on-play` | `media.play` | Triggered when media playback starts |
| `on-pause` | `media.pause` | Triggered when media playback is paused |
| `on-resume` | `media.resume` | Triggered when media playback resumes after pause |
| `on-stop` | `media.stop` | Triggered when media playback stops before completion |
| `on-rate` | `media.rate` | Triggered when a user rates media |
| `on-added` | `library.new` | Triggered when new content is added to the library |
| `on-deck` | `library.on.deck` | Triggered when media is added to On Deck |

### Command Variables

When defining commands for webhook events, you can use dynamic variables that will be replaced with values from the webhook payload:

| Variable | Description | Example |
|----------|-------------|--------|
| `${show_rating_key}` | Unique identifier for the TV show | `download-next --show-id ${show_rating_key} --count 2` |
| `${rating_key}` | Unique identifier for the specific media item | `delete-watched --media-id ${rating_key}` |
| `${library_title}` | Name of the library containing the media | `sync --library "${library_title}"` |
| `${title}` | Title of the media | `echo "Played: ${title}"` |
| `${type}` | Type of media (movie, episode, etc.) | `if-command ${type} == "episode" delete-watched` |

## Running the Webhook Server

### Starting the Server

```bash
# Start as a background daemon
plexrr webhook start

# Start in the foreground (useful for debugging)
plexrr webhook start --foreground

# Start with debug logging
plexrr webhook start --foreground --debug

# Use a custom port (default is 9876)
plexrr webhook start --port 8080
```

### Managing the Server

```bash
# Check if the webhook server is running
plexrr webhook status

# Stop the webhook server
plexrr webhook stop
```

### Setting Up as a System Service

For a permanent setup, use the provided systemd service:

```bash
sudo cp /path/to/plexrr/resources/plexrr-webhook.service /etc/systemd/system/plexrr-webhook@<username>.service
sudo systemctl daemon-reload
sudo systemctl enable plexrr-webhook@<username>.service
sudo systemctl start plexrr-webhook@<username>.service
```

## Configuring Plex

1. Log in to your Plex account at https://app.plex.tv
2. Go to Settings → Account
3. Scroll down to find the "Webhooks" section
4. Click "Add Webhook"
5. Enter the URL of your webhook server: `http://YOUR_SERVER_IP:9876/webhook`
   (Replace YOUR_SERVER_IP with the IP address where plexrr is running)
6. Click "Save Changes"

## Testing

To test if your webhook setup is working correctly:

```bash
# Start the webhook server in debug mode
plexrr webhook start --foreground --debug

# In another terminal, send a test webhook
curl -X POST -H "Content-Type: application/json" \
  -d '{"event":"media.scrobble", "Account":{"title":"test"}, "Metadata":{"type":"episode"}}' \
  http://localhost:9876/webhook
```

You should see the webhook being received and any configured commands being executed.

Alternatively, play something in Plex and mark it as watched, and you should see the events in the debug output.

## Troubleshooting

If webhooks are not working:

1. Run `plexrr config validate --verbose` to check that your webhook configuration is correct
2. Verify the webhook server is running with `plexrr webhook status`
3. Check logs:
   - When running in foreground mode: look at terminal output
   - When running as a systemd service: `sudo journalctl -u plexrr-webhook@<username>.service -f`
4. Make sure your Plex server can reach the webhook server:
   - Check firewall settings
   - Verify the IP address is correct
   - Try the `curl` test command above from the same machine as your Plex server
5. Confirm you have a Plex Pass subscription
6. Check that the webhooks are properly configured in your Plex account
This guide explains how to set up and use webhooks with PlexRR to automate actions based on Plex events.

## What are Webhooks?

Webhooks are a way for Plex to send real-time notifications to external applications when certain events occur, such as when a video starts playing, when it's been watched completely, or when new media is added to your library.

PlexRR can receive these webhook events and trigger configured commands automatically.

## Configuration

### 1. Edit Your Config File

Add a `webhooks` section to your PlexRR configuration file (`~/.config/plexrr/config.ini`):

```ini
[webhooks]
# Event triggered when an episode is marked as watched
after-watched = download-next --count 2 --execute, delete-watched --days 0 --execute

# Event triggered when playback starts
on-play = 

# Event triggered when playback stops
on-stop = 

# Event triggered when new content is added to library
on-added = 
```

Each event type can have a comma-separated list of PlexRR commands that will be executed when the event occurs.

### Complete Configuration Example

Here's a complete configuration file example that includes webhook settings along with Plex, Radarr, and Sonarr configuration:

```ini
; Plex server configuration
[plex]
base_url = http://192.168.1.100:32400  ; Your Plex server URL
token = YOUR_PLEX_TOKEN_HERE          ; Your Plex authentication token

; Choose ONE of these two options for watchlist access:
; Option 1: Use Plex account credentials
username = your-plex-username         ; Your Plex username
password = your-plex-password         ; Your Plex password

; Option 2: Use RSS feed URL (recommended if you don't want to store password)
; watchlist_rss = https://rss.plex.tv/your-unique-watchlist-id

; Radarr configuration for movies
[radarr]
base_url = http://192.168.1.100:7878   ; Your Radarr server URL
api_key = YOUR_RADARR_API_KEY         ; Your Radarr API key

; Sonarr configuration for TV shows
[sonarr]
base_url = http://192.168.1.100:8989   ; Your Sonarr server URL
api_key = YOUR_SONARR_API_KEY         ; Your Sonarr API key

; Webhook configuration for automating actions
[webhooks]
; When an episode is marked as watched:
; 1. Download the next 2 episodes
; 2. Delete the watched episode immediately
after-watched = download-next --show-id ${show_rating_key} --count 2 --execute, delete-watched --show-id ${show_rating_key} --days 0 --execute

; When playback starts: No actions configured
on-play = 

; When playback is paused: No actions configured
on-pause = 

; When playback resumes after pause: No actions configured
on-resume = 

; When playback stops before completion: No actions configured
on-stop = 

; When a user rates media: No actions configured
on-rate = 

; When new media is added to library:
; Sync any new movies to Radarr with quality profile ID 1
on-added = sync --quality-profile 1 --execute

; When media appears in On Deck: No actions configured
on-deck = 
```

You can customize the commands for each event type based on your needs.

### 2. Start the Webhook Server

You can start the webhook server manually:

```bash
plexrr webhook start
```

To check if the server is running:

```bash
plexrr webhook status
```

To stop the server:

```bash
plexrr webhook stop
```

### 3. Setting up as a System Service (Recommended)

For a more permanent setup, you can configure the webhook server as a systemd service:

1. Copy the service file to the systemd directory:

```bash
sudo cp /path/to/plexrr/resources/plexrr-webhook.service /etc/systemd/system/plexrr-webhook@<username>.service
```

Replace `<username>` with your username.

2. Reload systemd:

```bash
sudo systemctl daemon-reload
```

3. Enable and start the service:

```bash
sudo systemctl enable plexrr-webhook@<username>.service
sudo systemctl start plexrr-webhook@<username>.service
```

4. Check the status:

```bash
sudo systemctl status plexrr-webhook@<username>.service
```

The systemd service file should look like this:

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

Note: The service file uses `/usr/bin/env` to find the plexrr executable automatically, regardless of where pip installed it. If you need to specify the exact path, you can find it by running `which plexrr`.

### 4. Configure Plex to Send Webhooks

1. Go to your Plex settings: https://app.plex.tv/desktop/#!/settings/account
2. Click on "Webhooks" in the left sidebar
3. Click "Add Webhook"
4. Enter the URL of your webhook server: `http://your-server-ip:9876/webhook`
5. Save the webhook

## Available Event Types

- `after-watched`: Triggered when media is marked as watched (media.scrobble)
- `on-play`: Triggered when playback starts (media.play)
- `on-pause`: Triggered when playback is paused (media.pause)
- `on-resume`: Triggered when playback resumes (media.resume)
- `on-stop`: Triggered when playback stops (media.stop)
- `on-rate`: Triggered when media is rated (media.rate)
- `on-added`: Triggered when new media is added (library.new)
- `on-deck`: Triggered when media appears in On Deck (library.on.deck)

## Metadata Variables

You can use metadata from the webhook payload in your commands by using variables with the syntax `${variable_name}`.

For example:

```ini
[webhooks]
after-watched = download-next --show-id ${show_rating_key} --count 2 --execute
```

Available variables include:

- `${event}`: The event type
- `${user}`: The Plex username
- `${player}`: The player device name
- `${type}`: Media type (movie, episode, etc.)
- `${title}`: Media title
- `${rating_key}`: Plex ID for the media item

For TV shows:
- `${show_title}`: TV show title
- `${season}`: Season number
- `${episode}`: Episode number
- `${show_rating_key}`: Plex ID for the show

For movies:
- `${year}`: Release year

## Troubleshooting

- Check the webhook server logs:
  ```bash
  # When running in foreground mode:
  plexrr webhook start --foreground --debug

  # When running as systemd service:
  sudo journalctl -u plexrr-webhook@<username>.service
  ```

- Make sure your server is accessible from the Plex server
- Verify that port 9876 is open in your firewall
- Test the webhook manually using curl:
  ```bash
  curl -X POST -H "Content-Type: application/json" -d '{"event":"media.scrobble", "Account":{"title":"test"}, "Player":{"title":"test"}, "Metadata":{"type":"episode", "title":"Test Episode", "grandparentTitle":"Test Show", "parentIndex":1, "index":1, "ratingKey":"123", "grandparentRatingKey":"456"}}' http://localhost:9876/webhook
  ```
