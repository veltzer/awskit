import json
import os
import subprocess

import ujson
from typing import List

import stat
import boto3
import sys

import pylogconf
import requests
import socket
import errno
import time

from pyfakeuse.pyfakeuse import fake_use


def load_json_config(
        name: str,
) -> object:
    path = os.path.join(
        os.getenv('HOME'),
        ".pyawskit",
        name+".json",
    )
    with open(path, "rt") as input_handle:
        obj = json.load(input_handle)
    return obj


def wait_net_service(
        server: str,
        port: int,
        timeout: int=300,
) -> bool:
    """
        Wait for network service to appear
        http://code.activestate.com/recipes/576655-wait-for-network-service-to-appear/
        :param port:
        :param server:
        :param timeout
    """
    s = socket.socket()
    end = None
    if timeout:
        from time import time as now
        # time module is needed to calc timeout shared between two exceptions
        end = now() + timeout

    while True:
        try:
            if timeout:
                next_timeout = end - time.time()
                if next_timeout < 0:
                    return False
                else:
                    s.settimeout(next_timeout)

            s.connect((server, port))

        except socket.timeout as _:
            # this exception occurs only if timeout is set
            if timeout:
                return False

        except socket.error as err:
            # catch timeout exception from underlying network library
            # this one is different from socket.timeout
            if err.errno != errno.ETIMEDOUT:
                raise
        else:
            s.close()
            return True


def get_disks() -> List[str]:
    # another option is to take the output of lsblk(1)
    # which is not amazon specific and has nice format of data.
    url = "http://169.254.169.254/latest/meta-data/block-device-mapping"
    r = requests.get(url)
    disks = []
    for line in r.content.decode().split("\n"):
        if not line.startswith('ephemeral'):
            continue
        ephemeral_url = 'http://169.254.169.254/latest/meta-data/block-device-mapping/{}'.format(line)
        r = requests.get(ephemeral_url)
        assert r.status_code == 200
        content = r.content.decode()
        assert content.startswith('sd')
        assert len(content) == 3
        letter = content[2]
        device = '/dev/xvd{}'.format(letter)
        mode = os.stat(device).st_mode
        if not stat.S_ISBLK(mode):
            continue
        disks.append(device)
    return disks


def erase_partition_table(disk: str) -> None:
    logger.info("erasing partition table on disk [%s]", disk)
    subprocess.check_call([
        "/bin/dd",
        "if=/dev/zero",
        "of={}".format(disk),
        "bs=4096",
        "count=1024",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def reread_partition_table() -> None:
    logger.info("making OS re-read partition tables...")
    subprocess.check_call([
        "/sbin/partprobe",
    ])


def format_device(disk: str, label: str=None) -> None:
    logger.info("formatting the new device [%s]", disk)
    args = [
        "/sbin/mkfs.ext4",
        disk,
    ]
    if label is not None:
        args.extend([
            "-L",
            label,
        ])
    subprocess.check_call(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def update_file(filename=None, pattern=None, do_all=False):
    assert filename is not None
    assert pattern is not None

    config_file = os.path.expanduser(filename)
    if os.path.isfile(config_file):
        with open(config_file) as file_handle:
            lines = file_handle.readlines()
    else:
        lines = []

    # cut down auto generated lines if they exist...
    comment_line = "# DO NOT EDIT BEYOND THIS LINE - LEAVE THIS LINE AS IS\n"
    try:
        location_of_comment_line = lines.index(comment_line)
        lines = lines[:location_of_comment_line]
    except ValueError:
        pass

    filter_file = os.path.expanduser("~/.aws/aws_filter")
    if os.path.isfile(filter_file):
        print('reading [{0}]...'.format(filter_file))
        with open(filter_file) as file_handle:
            filters = ujson.loads(file_handle.read())
    else:
        print('no filter file [{0}] exists...'.format(filter_file))
        filters = []

    # look for servers matching the query
    ec2 = boto3.resource('ec2')
    if do_all:
        instances = list(ec2.instances.all())
    else:
        instances = list(ec2.instances.filter(Filters=filters))
    num_of_instances = len(instances)
    print("Found {} instances".format(num_of_instances), file=sys.stderr)
    # assert num_of_instances > 0

    # add the comment line
    lines.append(comment_line)

    # add bunch of lines for each server
    added = 0
    for instance in instances:
        if instance.tags is None:
            continue
        tags_dict = {}
        for tag in instance.tags:
            tags_dict[tag["Key"]] = tag["Value"]
        if "Name" not in tags_dict:
            continue
        host = tags_dict["Name"]
        if host == "":
            continue
        new_host = host.replace(' ', '')
        if new_host != host:
            print('Name [{0}] for host is bad. Try names without spaces...'.format(host))
        host = new_host
        # public_ip = instance.public_dns_name
        # if public_ip == "":
        #    continue
        # print(dir(instance))
        private_ip = instance.private_ip_address
        if private_ip == "":
            continue
        pattern_to_add = pattern.format(
            host=host,
            ip=private_ip,
            key_name=instance.key_name,
        )
        lines.extend(pattern_to_add)
        added += 1

    # print the final lines to the config file
    with open(config_file, "wt") as file_handle:
        file_handle.writelines(lines)
    print("Added {} instances".format(added), file=sys.stderr)
    print("written {}".format(config_file))


def mount_disk(disk: str, folder: str) -> None:
    logger.info("mounting the new device [%s, %s]", disk, folder)
    if not os.path.isdir(folder):
        os.makedirs(folder)
    subprocess.check_call([
        "/bin/mount",
        disk,
        folder,
    ])


def _excepthook(p_type, p_value, p_traceback):
    # we do not do anything with the traceback
    fake_use(p_traceback)
    # this loop will drill to the core of the problem
    # use only if this is what you want to show...
    while p_value.__cause__:
        p_value = p_value.__cause__
    logger.error("Exception occurred")
    logger.error("Exception type is [%s]" % p_type)
    logger.error("Exception value is [%s]" % p_value)


def setup_exceptions():
    """ Only print the heart of the exception and not the stack trace """
    sys.excepthook = _excepthook


def setup():
    """ Setup stuff for execution """
    setup_exceptions()
    pylogconf.setup()
