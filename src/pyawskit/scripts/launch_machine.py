#!/usr/bin/python3

"""
This script launches a new machine via boto3

References:
- http://boto3.readthedocs.io/en/latest/reference/services/ec2.html#EC2.Client.run_instances
- http://boto3.readthedocs.io/en/latest/reference/services/ec2.html#EC2.Client.request_spot_instances
- https://stackoverflow.com/questions/35721557/boto3-spot-instance-creation
- https://github.com/abdul/ec2-spot-instance-launcher
- https://peteris.rocks/blog/script-to-launch-amazon-ec2-spot-instances/
"""

import boto3

from pyawskit.aws import ProcessData, request_spot_instances, tag_resources, poll_instances_till_done, wait_for_ssh
from pyawskit.common import setup, update_ssh_config


def main(
):

    setup()

    client = boto3.client('ec2')
    ec2 = boto3.resource('ec2')
    pd = ProcessData()

    r_request_spot_instances = request_spot_instances(client, pd)
    request_ids = [r['SpotInstanceRequestId'] for r in r_request_spot_instances['SpotInstanceRequests']]
    tag_resources(client, request_ids, pd.p_spot_request_tags)
    # wait_using_waiter(client, pd, request_ids)
    # poll_requests_till_done(client, pd, request_ids)
    instances = poll_instances_till_done(ec2, pd, request_ids)
    instance_ids = [i.id for i in instances]
    tag_resources(client, instance_ids, pd.p_instance_tags)
    wait_for_ssh(instances)

    # TODO: we just need to add the instances we created
    update_ssh_config(all_hosts=False)


if __name__ == "__main__":
    main()

