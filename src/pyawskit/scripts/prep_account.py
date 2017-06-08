"""
This script prepares your account on a new aws machine.

These are the types of things it does:
- copy ~/.aws ~/.ssh ~/.s3cfg ~/.gitconfig ~/.passwd-s3fs to it
- set quiet login using:
    $ touch ~/.hushlogin
- configure vim to do correct python editing and save editing positions.
- install fancy prompt on it.
- put the git repositories you want on it.
"""
import os

import click

from pyawskit.common import setup


def do_hush_login():
    filename = os.path.expanduser("~/.hushlogin")
    with open(filename, "w"):
        pass


@click.command()
def main():
    setup()
    do_hush_login()


if __name__ == '__main__':
    main()
