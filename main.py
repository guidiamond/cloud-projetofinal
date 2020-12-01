import boto3
from botocore.exceptions import ClientError


# Create ohio instance
client_ohio = boto3.client("ec2", region_name="us-east-2")
resource_ohio = boto3.resource("ec2", region_name="us-east-2")
# -> instances
instance_tag_ohio = {"Key": "Name", "Value": "instance_tag_guitb"}

vpc_id_ohio = client_ohio.describe_vpcs().get("Vpcs", [{}])[0].get("VpcId", "")
intern_security_group_oh = [
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
]


security_group_name = "postgres"
security_group_tag = {"Key": "Name", "Value": "security_guilhermetb"}


print("\nCreating security group %s" % (security_group_name))
try:
    response = client_ohio.create_security_group(
        GroupName=security_group_name,
        Description="pf_security_group",
        VpcId=vpc_id_ohio,
        TagSpecifications=[
            {
                "ResourceType": "security-group",
                "Tags": [security_group_tag],
            }
        ],
    )

    security_group_id = response["GroupId"]

    data = client_ohio.authorize_security_group_ingress(
        GroupId=security_group_id, IpPermissions=intern_security_group_oh
    )
    print("Ingress Successfully Set")

except ClientError as e:
    print("Error", e)


print("\nCreating instance")
postgress_script = """#!/bin/bash
     sudo apt update
     sudo apt install postgresql postgresql-contrib -y
     sudo -u postgres sh -c "psql -c \\"CREATE USER cloud WITH PASSWORD 'cloud';\\" && createdb -O cloud tasks"
     sudo sed -i "/#listen_addresses/ a\listen_addresses = '*'" /etc/postgresql/10/main/postgresql.conf
     sudo sed -i "a\host all all 0.0.0.0/0 md5" /etc/postgresql/10/main/pg_hba.conf
     sudo systemctl restart postgresql
"""

try:
    waiter = client_ohio.get_waiter("instance_status_ok")
    # create a new EC2 instance
    instance = resource_ohio.create_instances(
        ImageId="ami-0dd9f0e7df0f0a138",
        MinCount=1,
        MaxCount=1,
        InstanceType="t2.micro",
        SecurityGroupIds=[security_group_id],
        UserData=postgress_script,
        KeyName="ohio-key",
        TagSpecifications=[{"ResourceType": "instance", "Tags": [instance_tag_ohio]}],
    )

    waiter.wait(
        InstanceIds=[instance[0].id]
    )  # esperar a instancia ser criada para ir para o proximo passo
    public_ip = client_ohio.describe_instances(InstanceIds=[instance[0].id])[
        "Reservations"
    ][0]["Instances"][0]["NetworkInterfaces"][0]["PrivateIpAddresses"][0][
        "Association"
    ][
        "PublicIp"
    ]
    print("Instance %s created and checked, public_ip=%s" % (instance[0].id, public_ip))

    instance_id = instance[0].id

except ClientError as e:
    print("Error", e)
