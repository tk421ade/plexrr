import click
import logging
import os
import signal
import sys
from pathlib import Path

from ..services.webhook_service import run_webhook_server
from ..utils.config_loader import get_config

@click.group(name='webhook')
def webhook_group():
    """Manage the Plex webhook server"""
    pass

@webhook_group.command(name='start')
@click.option('--host', default='0.0.0.0', help='Host address to listen on')
@click.option('--port', default=9876, type=int, help='Port to listen on')
@click.option('--foreground', is_flag=True, help='Run in foreground instead of as a daemon')
@click.option('--debug', is_flag=True, help='Enable debug mode')
def start_webhook(host, port, foreground, debug):
    """Start the webhook server to receive Plex notifications

    This command starts a web server that listens for webhook events from Plex.
    Configure webhooks in your config.yml file under the 'webhooks' section.

    Example config:

    webhooks:
      after-watched:
        - "download-next --count 2 --execute"
        - "delete-watched --days 0 --execute"

    By default, the server runs as a daemon process. Use --foreground to run
    in the terminal or when using systemd.
    """
    # Print Python environment information for debugging
    if debug:
        import sys
        click.echo(f"Python executable: {sys.executable}")
        click.echo(f"Python version: {sys.version}")
        # Print path information
        click.echo("Python path:")
        for p in sys.path:
            click.echo(f"  {p}")
    try:
        # Make sure config exists and has webhook section
        config = get_config()
        if 'webhooks' not in config:
            click.echo("Warning: No 'webhooks' section found in your config file.")
            click.echo("Add a 'webhooks' section to define actions for Plex events.")
            if not click.confirm("Continue anyway?", default=True):
                return

        if foreground:
            # Run directly in the current process
            click.echo(f"Starting webhook server on {host}:{port} in foreground mode")
            run_webhook_server(host, port, debug)
        else:
            # Run as a daemon
            click.echo(f"Starting webhook server on {host}:{port} as a daemon")

            # Create PID directory if it doesn't exist
            pid_dir = Path.home() / ".config" / "plexrr"
            pid_dir.mkdir(parents=True, exist_ok=True)
            pid_file = pid_dir / "webhook.pid"

            # Check if already running
            if pid_file.exists():
                with open(pid_file, 'r') as f:
                    old_pid = f.read().strip()
                click.echo(f"Webhook server may already be running (PID: {old_pid})")
                if not click.confirm("Start anyway?", default=False):
                    return

            # Fork the process
            pid = os.fork()
            if pid > 0:
                # Parent process
                click.echo(f"Webhook server started with PID: {pid}")
                with open(pid_file, 'w') as f:
                    f.write(str(pid))
                return

            # Child process continues here
            # Detach from parent environment
            os.chdir('/')
            os.setsid()
            os.umask(0)

            # Close all file descriptors
            for fd in range(3, 1024):
                try:
                    os.close(fd)
                except OSError:
                    pass

            # Redirect standard file descriptors to /dev/null
            with open(os.devnull, 'r') as null_in:
                os.dup2(null_in.fileno(), sys.stdin.fileno())

            # Set up logging to file
            log_file = pid_dir / "webhook.log"
            with open(log_file, 'a') as log_out:
                os.dup2(log_out.fileno(), sys.stdout.fileno())
                os.dup2(log_out.fileno(), sys.stderr.fileno())

            # Run the webhook server
            run_webhook_server(host, port, debug)

    except Exception as e:
        click.echo(f"Error starting webhook server: {str(e)}", err=True)
        if debug:
            import traceback
            click.echo(traceback.format_exc())

@webhook_group.command(name='stop')
def stop_webhook():
    """Stop the running webhook server"""
    pid_file = Path.home() / ".config" / "plexrr" / "webhook.pid"

    if not pid_file.exists():
        click.echo("No webhook server appears to be running")
        return

    try:
        with open(pid_file, 'r') as f:
            pid = int(f.read().strip())

        # Send SIGTERM to the process
        click.echo(f"Stopping webhook server (PID: {pid})...")
        try:
            os.kill(pid, signal.SIGTERM)
            click.echo("Webhook server stopped successfully")
        except ProcessLookupError:
            click.echo("Webhook server was not running (stale PID file)")
        except PermissionError:
            click.echo("Permission denied. Try running with sudo or as the server owner")

        # Remove the PID file
        pid_file.unlink(missing_ok=True)

    except Exception as e:
        click.echo(f"Error stopping webhook server: {str(e)}", err=True)

@webhook_group.command(name='status')
def webhook_status():
    """Check if the webhook server is running"""
    pid_file = Path.home() / ".config" / "plexrr" / "webhook.pid"

    if not pid_file.exists():
        click.echo("Webhook server is not running")
        return

    try:
        with open(pid_file, 'r') as f:
            pid = int(f.read().strip())

        # Check if process exists
        try:
            # Sending signal 0 checks if process exists without sending a signal
            os.kill(pid, 0)
            click.echo(f"Webhook server is running (PID: {pid})")

            # Show log file path
            log_file = pid_file.parent / "webhook.log"
            if log_file.exists():
                click.echo(f"Log file: {log_file}")

        except ProcessLookupError:
            click.echo("Webhook server is not running (stale PID file found)")
            if click.confirm("Remove stale PID file?", default=True):
                pid_file.unlink(missing_ok=True)
        except PermissionError:
            click.echo(f"Webhook server appears to be running (PID: {pid})")
            click.echo("(Cannot verify process due to permission restrictions)")

    except Exception as e:
        click.echo(f"Error checking webhook status: {str(e)}", err=True)
