#!/usr/bin/env python3

import os
import sys
import configparser
from pathlib import Path

def check_config_file(file_path):
    """Directly check a config file for webhooks section"""
    if not os.path.exists(file_path):
        print(f"Error: File {file_path} does not exist")
        return False

    print(f"\nChecking configuration file: {file_path}")

    # Try to parse with configparser
    parser = configparser.ConfigParser()
    parser.read(file_path)

    print(f"Sections found: {parser.sections()}")

    if 'webhooks' not in parser.sections():
        print("No [webhooks] section found in the file")
        return False

    print("\n[webhooks] section found with the following items:")
    for key, value in parser['webhooks'].items():
        print(f"  {key} = {value}")

    # Direct file inspection
    print("\nDirect file inspection:")
    with open(file_path, 'r') as f:
        content = f.read()
        webhook_section = False
        webhook_lines = []

        for line in content.splitlines():
            if line.strip() == '[webhooks]':
                webhook_section = True
                webhook_lines.append(line)
            elif webhook_section and line.strip() and line.strip().startswith('['):
                webhook_section = False
            elif webhook_section:
                webhook_lines.append(line)

        if webhook_lines:
            print("Webhook section content:")
            for line in webhook_lines:
                print(f"  {line}")
        else:
            print("No webhook section found in direct file inspection")

    return True

def main():
    # Check the file specified as argument or try common locations
    if len(sys.argv) > 1:
        check_config_file(sys.argv[1])
        return

    # Try common locations
    config_paths = [
        Path.home() / '.netflarr' / 'config.ini',
        Path.home() / '.config' / 'plexrr' / 'config.ini',
        Path.home() / '.config' / 'plexrr' / 'config.yml',
        Path.cwd() / 'config.ini',
        Path.cwd() / 'config.yml',
    ]

    found = False
    for path in config_paths:
        if path.exists():
            check_config_file(str(path))
            found = True

    if not found:
        print("No configuration files found in common locations")
        print("Please specify the path to your config file as an argument:")
        print("  python check_webhook_config.py /path/to/your/config.ini")

if __name__ == "__main__":
    main()
