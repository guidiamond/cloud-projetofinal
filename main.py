import boto3
from botocore.exceptions import ClientError

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


def get_django_script(psql_ip):
    return """#!/bin/bash
     sudo apt update
     git clone https://github.com/Gustavobb/tasks.git && mv tasks /home/ubuntu
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

        return True

    except ClientError as e:
        print("Error", e)

        return False


def main():
    # ohio
    create_security_group(ohio)  # assign ohio's security_group id
    create_instance(ohio)  # assign ohio's instance ip and id

    # wait for ohio's instance public ip to be assigned before assigning oregon['script']
    oregon["script"] = get_django_script(ohio["instance"]["ip"])
    create_security_group(oregon)  # assign oregon's security_group id
    create_instance(oregon)  # assign oregon's instance ip and id

    create_ami(oregon)


main()
