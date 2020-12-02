import boto3
from botocore.exceptions import ClientError
from time import time

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
    return """#!/bin/bash
     sudo apt update
     git clone https://github.com/guidiamond/tasks.git && mv tasks /home/ubuntu
     sudo sed -i 's/node1/{}/' /home/ubuntu/tasks/portfolio/settings.py 
     /home/ubuntu/tasks/./install.sh
     echo $? >> /home/ubuntu/aa.txt
     reboot
""".format(
        psql_ip
    )


# Appends security_group_id to obj
def create_security_group(obj):
    print("\nCreating security group")
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

        data = obj["client"].authorize_security_group_ingress(
            GroupId=security_group_id, IpPermissions=obj["security_group"]["value"]
        )
        obj["security_group"]["id"] = security_group_id
        print("\nSuccess")

        return True

    except ClientError as e:
        print("Error", e)
        return False


# Appends instance["id"] to obj
def create_instance(obj):
    print("\nCreating instance")

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
            "Instance %s created and checked, public_ip=%s"
            % (instance[0].id, public_ip)
        )

        instance_id = instance[0].id
        obj["instance"]["id"] = instance_id
        obj["instance"]["ip"] = public_ip
        return True

    except ClientError as e:
        print("Error", e)
        return False


def create_ami(obj):
    print("\nCreating AMI")
    try:
        waiter = obj["client"].get_waiter("image_available")
        response = obj["client"].create_image(
            InstanceId=obj["instance"]["id"], NoReboot=True, Name=obj["name"]
        )
        waiter.wait(ImageIds=[response["ImageId"]])
        print("AMI created")

        obj["ami"]["id"] = response["ImageId"]
        print(response["ImageId"])

        return True

    except ClientError as e:
        print("Error", e)

        return False


def delete_instances(obj):
    print("\nDeleting Instances")
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
            print("Instance %s Deleted" % (instance_id))
            obj["instance"]["id"] = None
            return True

        return False

    except ClientError as e:
        print("Error", e)
        return False


def get_timer(time_s):
    t0 = time()
    t1 = time()
    while t1 - t0 <= time_s:
        t1 = time()


def create_load_balancer(obj, subnets, security_group_id):
    print("\nCreating load_balancer")
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

        with open("loadbalancer_DNS", "w+") as f:
            f.write(load_balancer["DNSName"])

        ok = False
        while not ok:
            lb = obj["client"].describe_load_balancers()["LoadBalancerDescriptions"]
            for l in lb:
                if l["LoadBalancerName"] == obj["name"]:
                    ok = True

            get_timer(10)

        print("load_balancer created")

    except ClientError as e:
        print("Error", e)


def delete_load_balancer(obj):
    print("\nDeleting load balencer")
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

                get_timer(10)

            print("load_balancer deleted")

    except ClientError as e:
        print("Error", e)


autoscale_client = boto3.client("autoscaling", region_name=oregon_region)
autoscale = {
    "name": "autoscale",
    "groupname": "oregon_group_guilhermetb1",
    "client": autoscale_client,
}


def create_launch_cfg(obj, client_img_id, security_group_id):
    print("\ncreating launch cfg")
    try:
        response = autoscale_client.create_launch_configuration(
            LaunchConfigurationName=obj["name"],
            ImageId=client_img_id,
            KeyName="oregon-key",
            SecurityGroups=[security_group_id],
            InstanceType="t2.micro",
            InstanceMonitoring={"Enabled": True},
        )

        print("launch_configuration created")

    except ClientError as e:
        print("Error", e)


def create_autoscaling(obj, load_balencer_name, availability_zones):
    print("\nCreating autoscaling")
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
            get_timer(10)

            print("autoscaling created")

    except ClientError as e:
        print("Error", e)


def delete_autoscaling(obj):
    print("\nDeleting autoscaling")
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
                get_timer(10)

            print("autoscaling deleted")

    except ClientError as e:
        print("Error", e)


def main():
    # Deletion order : autoscale
    delete_autoscaling(autoscale)
    delete_load_balancer(elb)

    # ohio
    # create_security_group(ohio)  # assign ohio's security_group id
    # create_instance(ohio)  # assign ohio's instance ip and id
    #
    # # wait for ohio's instance public ip to be assigned before assigning oregon['script']
    # oregon["script"] = get_django_script(ohio["instance"]["ip"])
    # create_security_group(oregon)  # assign oregon's security_group id
    # create_instance(oregon)  # assign oregon's instance ip and id
    #
    # # get subnets used for the load balencer
    # availability_zones = [
    #     zone["ZoneName"]
    #     for zone in oregon["client"].describe_availability_zones()["AvailabilityZones"]
    # ]
    # subnets = [
    #     subnet["SubnetId"] for subnet in oregon["client"].describe_subnets()["Subnets"]
    # ]
    # # get availability_zones for autoscaling
    # availability_zones = [
    #     zone["ZoneName"]
    #     for zone in oregon["client"].describe_availability_zones()["AvailabilityZones"]
    # ]
    #
    # # Create AMI and delete oregon instance
    # create_ami(oregon)
    # delete_instances(oregon)
    #
    # # Create load balencer
    # create_load_balancer(elb, subnets, oregon["security_group"]["id"])
    #
    # # create autoscaling
    # launch_cfg_name = "autoscalingcfg"
    # create_launch_cfg(
    #     obj=autoscale,
    #     client_img_id=oregon["ami"]["id"],
    #     security_group_id=oregon["security_group"]["id"],
    # )
    # create_autoscaling(
    #     obj=autoscale,
    #     load_balencer_name=elb["name"],
    #     availability_zones=availability_zones,
    # )


main()
