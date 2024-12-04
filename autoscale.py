import boto3
import base64
import time

# --------------------- Launch Template and Auto Scaling --------------------- #

def setup_auto_scaling():
    ec2_client = boto3.client('ec2', region_name='us-east-2')
    autoscaling_client = boto3.client('autoscaling', region_name='us-east-2')

    # Updated User Data script to pull the custom index.html from GitHub
    user_data_script = """#!/bin/bash
    apt update -y
    apt install apache2 git -y
    systemctl start apache2
    systemctl enable apache2

    # Clone the Git repository
    cd /tmp
    git clone https://github.com/Kobbyone4real/aws-web-deployment.git

    # Move the custom index.html to Apache's web directory
    sudo mv /tmp/aws-web-deployment/index.html /var/www/html/index.html

    # Ensure proper permissions
    sudo chown -R www-data:www-data /var/www/html
    sudo chmod -R 755 /var/www/html
    """
    # Encode the User Data script to Base64
    encoded_user_data = base64.b64encode(user_data_script.encode('utf-8')).decode('utf-8')

    # Launch Template Name
    launch_template_name = 'WebServerTemplateUpdated'

    # Step 1: Delete existing Launch Template (if it exists)
    try:
        ec2_client.delete_launch_template(LaunchTemplateName=launch_template_name)
        print(f"Deleted existing Launch Template: {launch_template_name}")
    except ec2_client.exceptions.ClientError as e:
        if 'InvalidLaunchTemplateName.NotFoundException' in str(e):
            print(f"No existing Launch Template named {launch_template_name} found. Proceeding to create a new one.")
        else:
            raise

    # Step 2: Create a new Launch Template
    try:
        launch_template = ec2_client.create_launch_template(
            LaunchTemplateName=launch_template_name,
            VersionDescription='1',
            LaunchTemplateData={
                'ImageId': 'ami-0ea3c35c5c3284d82',  # Ubuntu AMI ID
                'InstanceType': 't2.micro',  # Free Tier instance type
                'KeyName': 'kobbylenz',  # Your Key Pair Name (without .pem)
                'SecurityGroupIds': ['sg-0982a5903abd8ca0d'],  # Your Security Group ID
                'UserData': encoded_user_data  # Base64-encoded User Data
            }
        )
        print(f"Launch Template '{launch_template_name}' created successfully.")
    except Exception as e:
        print(f"Failed to create Launch Template: {e}")
        return

    # Step 3: Create or Update Auto Scaling Group
    try:
        autoscaling_client.create_auto_scaling_group(
            AutoScalingGroupName='WebServerASGUpdated',
            LaunchTemplate={
                'LaunchTemplateName': launch_template_name,
                'Version': '$Default'
            },
            MinSize=2,  # Minimum number of instances
            MaxSize=3,  # Maximum number of instances
            DesiredCapacity=2,  # Desired number of instances
            VPCZoneIdentifier='subnet-0db8d41a2840d19e4,subnet-06f2562018a96f3fa',  # Your Subnet IDs
            Tags=[
                {
                    'Key': 'Name',
                    'Value': 'WebServerInstanceUpdated',
                    'PropagateAtLaunch': True
                }
            ]
        )
        print("Auto Scaling Group 'WebServerASGUpdated' created successfully.")
    except autoscaling_client.exceptions.ClientError as e:
        if 'AlreadyExists' in str(e):
            print("Auto Scaling Group 'WebServerASGUpdated' already exists. Updating configuration...")
            autoscaling_client.update_auto_scaling_group(
                AutoScalingGroupName='WebServerASGUpdated',
                LaunchTemplate={
                    'LaunchTemplateName': launch_template_name,
                    'Version': '$Default'
                },
                MinSize=2,
                MaxSize=3,
                DesiredCapacity=2
            )
            print("Auto Scaling Group 'WebServerASGUpdated' updated successfully.")
        else:
            raise

    # Step 4: Terminate an Instance and Monitor Replacement
    terminate_and_monitor(ec2_client, autoscaling_client)

# --------------------- Terminate and Monitor --------------------- #

def terminate_and_monitor(ec2_client, autoscaling_client):
    print("Fetching running instances in the Auto Scaling Group...")
    response = ec2_client.describe_instances(
        Filters=[
            {"Name": "tag:Name", "Values": ["WebServerInstanceUpdated"]},
            {"Name": "instance-state-name", "Values": ["running"]}
        ]
    )

    instances = [
        {
            "InstanceId": instance['InstanceId'],
            "PublicIpAddress": instance.get('PublicIpAddress', 'N/A')
        }
        for reservation in response['Reservations']
        for instance in reservation['Instances']
    ]

    if len(instances) < 2:
        print("Less than 2 instances running. Checking Auto Scaling activities...")
        check_scaling_activities(autoscaling_client)
        return

    print(f"Running instances found: {instances}")

    # Terminate one of the instances
    instance_to_terminate = instances[0]['InstanceId']
    print(f"Terminating instance: {instance_to_terminate}...")
    ec2_client.terminate_instances(InstanceIds=[instance_to_terminate])

    # Monitor Auto Scaling Group for new instance
    print("Monitoring Auto Scaling Group for replacement instance...")
    while True:
        time.sleep(10)  # Wait before checking again
        response = ec2_client.describe_instances(
            Filters=[
                {"Name": "tag:Name", "Values": ["WebServerInstanceUpdated"]},
                {"Name": "instance-state-name", "Values": ["running"]}
            ]
        )

        current_instances = [
            {
                "InstanceId": instance['InstanceId'],
                "PublicIpAddress": instance.get('PublicIpAddress', 'N/A')
            }
            for reservation in response['Reservations']
            for instance in reservation['Instances']
        ]

        print(f"Currently running instances: {current_instances}")

        # Check if a new instance has replaced the terminated one
        if len(current_instances) >= 2 and not any(
            inst['InstanceId'] == instance_to_terminate for inst in current_instances
        ):
            print("Replacement instance launched successfully:")
            for instance in current_instances:
                print(f"Instance ID: {instance['InstanceId']}, Public IP: {instance['PublicIpAddress']}")
            break

# --------------------- Debugging Functions --------------------- #

def check_scaling_activities(autoscaling_client):
    print("Checking Auto Scaling activities...")
    response = autoscaling_client.describe_scaling_activities(
        AutoScalingGroupName='WebServerASGUpdated'
    )

    for activity in response['Activities']:
        print(f"Description: {activity['Description']}")
        print(f"Status: {activity['StatusCode']}")
        print(f"Start Time: {activity['StartTime']}")
        print("-" * 60)

# --------------------- Main Execution --------------------- #

if __name__ == "__main__":
    setup_auto_scaling()

