import boto3
from botocore.exceptions import ClientError
from time import time


class bcolors:
    HEADER = "\033[95m"
    OK = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"


# used to stop code exec while async action is running
def await_timer(time_s):
    t0 = time()
    t1 = time()
    while t1 - t0 <= time_s:
        t1 = time()


postgress_script = """#!/bin/bash
         sudo apt update
         sudo apt install postgresql postgresql-contrib -y
         sudo -u postgres sh -c "psql -c \\"CREATE USER cloud WITH PASSWORD 'cloud';\\" && createdb -O cloud tasks"
         sudo sed -i "/#listen_addresses/ a\listen_addresses = '*'" /etc/postgresql/10/main/postgresql.conf
         sudo sed -i "a\host all all 0.0.0.0/0 md5" /etc/postgresql/10/main/pg_hba.conf
         sudo systemctl restart postgresql
"""

ohio_region = "us-east-2"
ohio_client = boto3.client("ec2", region_name=ohio_region)

ohio = {
    "region": ohio_region,
    "name": "psql ami",
    "ami": {"id": None},
    "img_id": "ami-0dd9f0e7df0f0a138",  # Ubuntu 18.04
    "client": ohio_client,
    "key": "ohio-key",
    "resource": boto3.resource("ec2", region_name=ohio_region),
    "instance": {
        "tag": {"Key": "Name", "Value": "instance_tag_guitb"},
        "id": None,  # Reasigned in create_instance
        "ip": None,  # Reasigned in create_instance
    },
    "script": postgress_script,
    "vpc": ohio_client.describe_vpcs().get("Vpcs", [{}])[0].get("VpcId", ""),
    "security_group": {
        "name": "postgres",
        "id": None,
        "tag": {"Key": "Name", "Value": "security_guilhermetb"},
        "value": [
            {
                "IpProtocol": "tcp",
                "FromPort": 22,
                "ToPort": 22,
                "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
            },
            {
                "IpProtocol": "tcp",
                "FromPort": 5432,
                "ToPort": 5432,
                "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
            },
        ],
    },
}

oregon_region = "us-west-2"
oregon_client = boto3.client("ec2", region_name=oregon_region)
oregon = {
    "region": oregon_region,
    "name": "django ami",
    "img_id": "ami-0ac73f33a1888c64a",  # Ubuntu 18.04
    "ami": {"id": None},
    "client": oregon_client,
    "key": "oregon-key",
    "resource": boto3.resource("ec2", region_name=oregon_region),
    "instance": {
        "tag": {"Key": "Name", "Value": "instance_tag_guitb"},
        "id": None,  # Reasigned in create_instance
        "ip": None,  # Reasigned in create_instance
    },
    "script": None,
    "vpc": oregon_client.describe_vpcs().get("Vpcs", [{}])[0].get("VpcId", ""),
    "security_group": {
        "name": "django",
        "id": None,
        "tag": {"Key": "Name", "Value": "security_guilhermetb"},
        "value": [
            {
                "IpProtocol": "tcp",
                "FromPort": 22,
                "ToPort": 22,
                "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
            },
            {
                "IpProtocol": "tcp",
                "FromPort": 8080,
                "ToPort": 8080,
                "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
            },
        ],
    },
}
elb_client = boto3.client("elb", region_name=oregon_region)
elb = {
    "region": oregon_region,
    "name": "lb",
    "ami": {"id": None},
    "img_id": "ami-0dd9f0e7df0f0a138",  # Ubuntu 18.04
    "client": elb_client,
    "key": "oregon-key",
    "resource": boto3.resource("ec2", region_name=oregon_region),
    "instance": {
        "tag": {"Key": "Name", "Value": "instance_loadbalencer"},
        "id": None,  # Reasigned in create_instance
        "ip": None,  # Reasigned in create_instance
    },
    "script": postgress_script,
    "vpc": ohio_client.describe_vpcs().get("Vpcs", [{}])[0].get("VpcId", ""),
    "security_group": {
        "name": "postgres",
        "id": None,
        "tag": {"Key": "Name", "Value": "security_guilhermetb"},
        "value": [
            {
                "IpProtocol": "tcp",
                "FromPort": 22,
                "ToPort": 22,
                "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
            },
            {
                "IpProtocol": "tcp",
                "FromPort": 5432,
                "ToPort": 5432,
                "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
            },
        ],
    },
}


def get_django_script(psql_ip):
    return """#!/bin/sh
     sudo apt update
     cd /home/ubuntu
     git clone https://github.com/guidiamond/tasks
     sudo sed -i "s/node1/{}/g" /home/ubuntu/tasks/portfolio/settings.py 
     cd tasks
     ./install.sh
     reboot
     """.format(
        psql_ip
    )


# Appends security_group_id to obj
def create_security_group(obj):
    print("\n" + bcolors.HEADER + "Creating security group")
    try:
        response = obj["client"].create_security_group(
            GroupName=obj["security_group"]["name"],
            Description="cloud",
            VpcId=obj["vpc"],
            TagSpecifications=[
                {
                    "ResourceType": "security-group",
                    "Tags": [obj["security_group"]["tag"]],
                }
            ],
        )

        security_group_id = response["GroupId"]

        obj["client"].authorize_security_group_ingress(
            GroupId=security_group_id, IpPermissions=obj["security_group"]["value"]
        )
        obj["security_group"]["id"] = security_group_id
        print("\n" + bcolors.OK + "SecurityGroup: " + security_group_id + " created")

    except ClientError as e:
        print("\n" + bcolors.FAIL + "Error" + "\n")
        print(e)


def delete_security_group(obj):
    print("\n" + bcolors.WARNING + "Deleting security group")
    try:
        security_group_id = obj["client"].describe_security_groups(
            Filters=[
                {
                    "Name": "tag:%s" % (obj["security_group"]["tag"]["Key"]),
                    "Values": [obj["security_group"]["tag"]["Value"]],
                }
            ]
        )

        if len(security_group_id["SecurityGroups"]):
            security_group_id = security_group_id["SecurityGroups"][0]["GroupId"]
            while True:
                try:
                    response = obj["client"].delete_security_group(
                        GroupId=security_group_id
                    )
                    break

                except ClientError as e:
                    await_timer(3)

            print("\n" + bcolors.OK + "Security Group Deleted " + security_group_id)

    except ClientError as e:
        print("\n" + bcolors.FAIL + "Error" + "\n")
        print(e)


# Appends instance["id"] to obj
def create_instance(obj):
    print("\n" + bcolors.HEADER + "Creating instance")

    try:
        waiter = obj["client"].get_waiter("instance_status_ok")
        # create a new EC2 instance
        instance = obj["resource"].create_instances(
            ImageId=obj["img_id"],
            MinCount=1,
            MaxCount=1,
            InstanceType="t2.micro",
            SecurityGroupIds=[obj["security_group"]["id"]],
            UserData=obj["script"],
            KeyName=obj["key"],
            TagSpecifications=[
                {"ResourceType": "instance", "Tags": [obj["instance"]["tag"]]}
            ],
        )

        waiter.wait(InstanceIds=[instance[0].id])

        public_ip = obj["client"].describe_instances(InstanceIds=[instance[0].id])[
            "Reservations"
        ][0]["Instances"][0]["NetworkInterfaces"][0]["PrivateIpAddresses"][0][
            "Association"
        ][
            "PublicIp"
        ]
        print(
            "\n"
            + bcolors.OK
            + "Instance id: "
            + instance[0].id
            + " public ip: "
            + public_ip
            + " created"
        )

        instance_id = instance[0].id
        obj["instance"]["id"] = instance_id
        obj["instance"]["ip"] = public_ip

    except ClientError as e:
        print("\n" + bcolors.FAIL + "Error" + "\n")
        print(e)


def delete_instance(obj):
    print("\n" + bcolors.WARNING + "Deleting instance")
    try:
        instance_id = obj["client"].describe_instances(
            Filters=[
                {
                    "Name": "tag:%s" % (obj["instance"]["tag"]["Key"]),
                    "Values": [obj["instance"]["tag"]["Value"]],
                },
                {"Name": "instance-state-name", "Values": ["running"]},
            ]
        )

        if len(instance_id["Reservations"]):
            instance_id = instance_id["Reservations"][0]["Instances"][0]["InstanceId"]
            waiter = obj["client"].get_waiter("instance_terminated")
            response = obj["client"].terminate_instances(InstanceIds=[instance_id])
            waiter.wait(InstanceIds=[instance_id])
            print("\n" + bcolors.OK + "Instance Deleted " + instance_id)
            obj["instance"]["id"] = None

    except ClientError as e:
        print("\n" + bcolors.FAIL + "Error" + "\n")
        print(e)


def create_ami(obj):
    print("\n" + bcolors.HEADER + "Creating ami")
    try:
        waiter = obj["client"].get_waiter("image_available")
        response = obj["client"].create_image(
            InstanceId=obj["instance"]["id"], NoReboot=True, Name=obj["name"]
        )
        waiter.wait(ImageIds=[response["ImageId"]])

        obj["ami"]["id"] = response["ImageId"]
        print("\n" + bcolors.OK + "AMI: " + response["ImageId"] + " created")

    except ClientError as e:
        print("\n" + bcolors.FAIL + "Error" + "\n")
        print(e)


def delete_image(obj):
    print("\n" + bcolors.WARNING + "Deleting image")
    try:
        image_id = obj["client"].describe_images(
            Filters=[{"Name": "name", "Values": [obj["name"]]}]
        )

        if len(image_id["Images"]):
            image_id = image_id["Images"][0]["ImageId"]
            response = obj["client"].deregister_image(ImageId=image_id)
            print("\n" + bcolors.OK + "Image Deleted " + image_id)

    except ClientError as e:
        print("\n" + bcolors.FAIL + "Error" + "\n")
        print(e)


def create_load_balancer(obj, subnets, security_group_id):
    print("\n" + bcolors.HEADER + "Creating load balencer")
    try:
        load_balancer = obj["client"].create_load_balancer(
            LoadBalancerName=obj["name"],
            Listeners=[
                {
                    "Protocol": "HTTP",
                    "LoadBalancerPort": 8080,
                    "InstancePort": 8080,
                },
            ],
            Subnets=subnets,
            SecurityGroups=[security_group_id],
            Tags=[
                {"Key": "string", "Value": "string"},
            ],
        )

        with open("dns.txt", "w+") as f:
            f.write(load_balancer["DNSName"])

        ok = False
        while not ok:
            lb = obj["client"].describe_load_balancers()["LoadBalancerDescriptions"]
            for l in lb:
                if l["LoadBalancerName"] == obj["name"]:
                    ok = True

            await_timer(3)

        print("\n" + bcolors.OK + "load balencer " + obj["name"] + " created")

    except ClientError as e:
        print("\n" + bcolors.FAIL + "Error" + "\n")
        print(e)


def delete_load_balancer(obj):
    print("\n" + bcolors.WARNING + "Deleting load balancer")
    try:
        load_balancers = obj["client"].describe_load_balancers()[
            "LoadBalancerDescriptions"
        ]
        exists = False

        for lb in load_balancers:
            if lb["LoadBalancerName"] == obj["name"]:
                exists = True

        if exists:
            response = obj["client"].delete_load_balancer(LoadBalancerName=obj["name"])
            ok = True
            while ok:
                lb = obj["client"].describe_load_balancers()["LoadBalancerDescriptions"]
                ok = True
                if not len(lb):
                    ok = False
                for l in lb:
                    print(l["LoadBalancerName"])
                    if l["LoadBalancerName"] == obj["name"]:
                        ok = False

                await_timer(3)

            print("\n" + bcolors.OK + "Load Balencer Deleted ")

    except ClientError as e:
        print("\n" + bcolors.FAIL + "Error" + "\n")
        print(e)


autoscale_client = boto3.client("autoscaling", region_name=oregon_region)
autoscale = {
    "name": "autoscale",
    "groupname": "oregon_group_guilhermetb1",
    "client": autoscale_client,
}


def create_launch_cfg(obj, client_img_id, security_group_id):
    print("\n" + bcolors.HEADER + "Creating launch cfg")
    try:
        response = autoscale_client.create_launch_configuration(
            LaunchConfigurationName=obj["name"],
            ImageId=client_img_id,
            KeyName="oregon-key",
            SecurityGroups=[security_group_id],
            InstanceType="t2.micro",
            InstanceMonitoring={"Enabled": True},
        )

        print("\n" + bcolors.OK + "Launch Config Created")

    except ClientError as e:
        print("\n" + bcolors.FAIL + "Error" + "\n")
        print(e)


def delete_launch_cfg(obj):
    print("\n" + bcolors.WARNING + "Deleting launch cfg")
    try:
        if len(
            obj["client"].describe_launch_configurations(
                LaunchConfigurationNames=[obj["name"]]
            )["LaunchConfigurations"]
        ):
            response = obj["client"].delete_launch_configuration(
                LaunchConfigurationName=obj["name"]
            )
            print("\n" + bcolors.OK + "Launch Config Deleted")

    except ClientError as e:
        print("\n" + bcolors.FAIL + "Error" + "\n")
        print(e)


def create_autoscaling(obj, load_balencer_name, availability_zones):
    print("\n" + bcolors.HEADER + "Creating autoscaling")
    try:
        response = obj["client"].create_auto_scaling_group(
            AutoScalingGroupName=obj["groupname"],
            LaunchConfigurationName=obj["name"],
            MinSize=2,
            MaxSize=3,
            LoadBalancerNames=[load_balencer_name],
            DesiredCapacity=2,
            AvailabilityZones=availability_zones,
        )

        while not len(
            autoscale["client"].describe_auto_scaling_groups(
                AutoScalingGroupNames=[obj["groupname"]]
            )["AutoScalingGroups"]
        ):
            await_timer(3)

        print("\n" + bcolors.OK + "AutoScaling Created")

    except ClientError as e:
        print("\n" + bcolors.FAIL + "Error" + "\n")
        print(e)


def delete_autoscaling(obj):
    print("\n" + bcolors.WARNING + "Deleting autoscaling")
    try:
        if len(
            obj["client"].describe_auto_scaling_groups(
                AutoScalingGroupNames=[obj["groupname"]]
            )["AutoScalingGroups"]
        ):
            response = obj["client"].delete_auto_scaling_group(
                AutoScalingGroupName=obj["groupname"], ForceDelete=True
            )

            while len(
                obj["client"].describe_auto_scaling_groups(
                    AutoScalingGroupNames=[obj["groupname"]]
                )["AutoScalingGroups"]
            ):
                await_timer(3)

            print("\n" + bcolors.OK + "AutoScaling Deleted")

    except ClientError as e:
        print("\n" + bcolors.FAIL + "Error" + "\n")
        print(e)


def main():
    # Deletion reverse order of creation
    delete_autoscaling(autoscale)
    delete_launch_cfg(autoscale)
    delete_load_balancer(elb)
    delete_image(oregon)
    delete_instance(ohio)
    delete_security_group(ohio)
    delete_security_group(oregon)

    """ OHIO SECURITY GROUP && Instance Creation """
    create_security_group(ohio)  # assign ohio's security_group id
    create_instance(ohio)  # assign ohio's instance ip and id

    """ OREGON SECURITY GROUP && Instance Creation """
    # wait for ohio's instance public ip to be assigned before assigning oregon['script']
    oregon["script"] = get_django_script(ohio["instance"]["ip"])
    create_security_group(oregon)  # assign oregon's security_group id
    create_instance(oregon)  # assign oregon's instance ip and id

    # get subnets used for the load balencer
    subnets = [
        subnet["SubnetId"] for subnet in oregon["client"].describe_subnets()["Subnets"]
    ]
    # get availability_zones for autoscaling
    availability_zones = [
        zone["ZoneName"]
        for zone in oregon["client"].describe_availability_zones()["AvailabilityZones"]
    ]

    """ AMI CREATION (USING OREGON AS MODEL) """
    # Create AMI and delete oregon instance
    create_ami(oregon)
    delete_instance(oregon)

    """ LOADBALENCER CREATION """
    create_load_balancer(elb, subnets, oregon["security_group"]["id"])

    """ AUTOSCALING CREATION (USING OREGON AS MODEL) """
    launch_cfg_name = "autoscalingcfg"
    create_launch_cfg(
        obj=autoscale,
        client_img_id=oregon["ami"]["id"],
        security_group_id=oregon["security_group"]["id"],
    )
    create_autoscaling(
        obj=autoscale,
        load_balencer_name=elb["name"],
        availability_zones=availability_zones,
    )


main()
