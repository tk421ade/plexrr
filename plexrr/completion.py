#!/usr/bin/env python3

import click
import os
from plexrr.cli import cli

def get_completion_script():
    """Generate the bash completion script content"""
    return '''
# plexrr bash completion script
_plexrr_completion() {
    local IFS=$'\'\n'
    local response

    response=$(env COMP_WORDS="${COMP_WORDS[*]}" COMP_CWORD=$COMP_CWORD _PLEXRR_COMPLETE=bash_complete $1)

    for completion in $response; do
        IFS=',' read type value <<< "$completion"
        if [[ $type == 'dir' ]]; then
            COMPREPLY=( "$value" )
            return 0
        elif [[ $type == 'file' ]]; then
            COMPREPLY=( "$value" )
            return 0
        elif [[ $type == 'plain' ]]; then
            COMPREPLY+=($value)
        fi
    done

    return 0
}

complete -o nosort -F _plexrr_completion plexrr
'''

def write_completion_script(path=None):
    """Write the bash completion script to the specified path"""
    if path is None:
        # Default path for bash completion scripts
        bash_completion_dir = '/etc/bash_completion.d'
        user_completion_dir = os.path.expanduser('~/.bash_completion.d')

        # Create user directory if it doesn't exist
        if not os.path.exists(user_completion_dir):
            try:
                os.makedirs(user_completion_dir)
                path = os.path.join(user_completion_dir, 'plexrr')
            except OSError:
                # Fall back to current directory
                path = 'plexrr-completion.bash'
        else:
            path = os.path.join(user_completion_dir, 'plexrr')

    script_content = get_completion_script()

    try:
        with open(path, 'w') as f:
            f.write(script_content)
        os.chmod(path, 0o755)  # Make executable
        print(f"Bash completion script written to: {path}")
        print("To use it, either:")
        print(f"1. Source it directly: source {path}")
        print(f"2. Or restart your shell session")
        return True
    except Exception as e:
        print(f"Error writing completion script: {str(e)}")
        return False

@click.command('completion')
@click.option('--path', help='Path to write the completion script (default: ~/.bash_completion.d/plexrr)')
@click.option('--print', 'print_script', is_flag=True, help='Print the script to stdout instead of writing to file')
def completion_command(path, print_script):
    """Generate bash completion script for plexrr."""
    if print_script:
        click.echo(get_completion_script())
    else:
        write_completion_script(path)

if __name__ == '__main__':
    completion_command()
