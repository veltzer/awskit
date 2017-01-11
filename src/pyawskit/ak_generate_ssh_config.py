"""
This script will update ~/.aws/config file with the names of your machines.
Notice that you must hold all of your .pem files in ~/.aws/keys
"""

from pyawskit.common import update_file

pattern = """Host {host}
\tHostName {ip}
\tIdentityFile ~/.aws/keys/{key_name}.pem
\tIdentitiesOnly yes
\tUser ubuntu
"""


def main():
    update_file(filename="~/.ssh/config", pattern=pattern)

if __name__ == "__main__":
    main()
