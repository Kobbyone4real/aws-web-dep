import boto3
import json
import time

# AWS configuration
REGION = 'us-east-2'
STACK_NAME = 'WebServerStack'
TEMPLATE_BODY = {
    "AWSTemplateFormatVersion": "2010-09-09",
    "Description": "CloudFormation template to set up Auto Scaling with a Launch Template",
    "Resources": {
        "WebServerLaunchTemplate": {
            "Type": "AWS::EC2::LaunchTemplate",
            "Properties": {
                "LaunchTemplateName": "WebServerTemplateCF",
                "LaunchTemplateData": {
                    "InstanceType": "t2.micro",
                    "KeyName": "kobbylenz",  # Your key pair name
                    "ImageId": "ami-0ea3c35c5c3284d82",  # Replace with your Ubuntu AMI
                    "SecurityGroupIds": ["sg-0982a5903abd8ca0d"],  # Replace with your SG ID
                    "UserData": {
                        "Fn::Base64": {
                            "Fn::Join": [
                                "",
                                [
                                    "#!/bin/bash\n",
                                    "apt update -y\n",
                                    "apt install -y apache2 git\n",
                                    "systemctl start apache2\n",
                                    "systemctl enable apache2\n",
                                    f"git clone https://<username>:<personal_access_token>@github.com/<username>/<repository>.git /tmp/repo\n",
                                    "mv /tmp/repo/index.html /var/www/html/index.html\n"
                                ]
                            ]
                        }
                    }
                }
            }
        },
        "WebServerAutoScalingGroup": {
            "Type": "AWS::AutoScaling::AutoScalingGroup",
            "Properties": {
                "MinSize": "2",
                "MaxSize": "3",
                "DesiredCapacity": "2",
                "LaunchTemplate": {
                    "LaunchTemplateName": {
                        "Ref": "WebServerLaunchTemplate"
                    },
                    "Version": {
                        "Fn::GetAtt": ["WebServerLaunchTemplate", "LatestVersionNumber"]
                    }
                },
                "VPCZoneIdentifier": ["subnet-0db8d41a2840d19e4", "subnet-06f2562018a96f3fa"],  # Replace with your subnet IDs
                "Tags": [
                    {
                        "Key": "Name",
                        "Value": "WebServerInstance",
                        "PropagateAtLaunch": True
                    }
                ]
            }
        }
    },
    "Outputs": {
        "AutoScalingGroupName": {
            "Description": "Name of the Auto Scaling Group",
            "Value": {
                "Ref": "WebServerAutoScalingGroup"
            }
        },
        "LaunchTemplateName": {
            "Description": "Name of the Launch Template",
            "Value": {
                "Ref": "WebServerLaunchTemplate"
            }
        }
    }
}

def deploy_cloudformation_stack(cf_client):
    """Creates or updates a CloudFormation stack."""
    try:
        print(f"Checking if stack '{STACK_NAME}' exists...")
        existing_stacks = cf_client.describe_stacks(StackName=STACK_NAME)
        print(f"Stack '{STACK_NAME}' found. Updating...")
        cf_client.update_stack(
            StackName=STACK_NAME,
            TemplateBody=json.dumps(TEMPLATE_BODY),
            Capabilities=['CAPABILITY_IAM', 'CAPABILITY_NAMED_IAM']
        )
        print(f"Stack '{STACK_NAME}' updated successfully.")
    except cf_client.exceptions.ClientError as e:
        if "does not exist" in str(e):
            print(f"Stack '{STACK_NAME}' does not exist. Creating a new one...")
            cf_client.create_stack(
                StackName=STACK_NAME,
                TemplateBody=json.dumps(TEMPLATE_BODY),
                Capabilities=['CAPABILITY_IAM', 'CAPABILITY_NAMED_IAM']
            )
            print(f"Stack '{STACK_NAME}' creation initiated.")
        else:
            raise

def monitor_stack_deployment(cf_client):
    """Monitors the deployment of the CloudFormation stack."""
    print(f"Monitoring stack '{STACK_NAME}' deployment...")
    while True:
        response = cf_client.describe_stacks(StackName=STACK_NAME)
        stack_status = response['Stacks'][0]['StackStatus']
        print(f"Current stack status: {stack_status}")
        if stack_status in ["CREATE_COMPLETE", "UPDATE_COMPLETE"]:
            print(f"Stack '{STACK_NAME}' deployed successfully.")
            break
        elif stack_status in ["ROLLBACK_IN_PROGRESS", "ROLLBACK_COMPLETE", "DELETE_FAILED"]:
            print(f"Stack '{STACK_NAME}' deployment failed. Status: {stack_status}")
            break
        time.sleep(30)

def list_running_instances(ec2_client, asg_client):
    """Lists running instances in the Auto Scaling Group."""
    print(f"Fetching running instances in the Auto Scaling Group...")
    response = asg_client.describe_auto_scaling_groups(AutoScalingGroupNames=[STACK_NAME])
    instances = response['AutoScalingGroups'][0]['Instances']
    running_instances = []

    for instance in instances:
        instance_id = instance['InstanceId']
        details = ec2_client.describe_instances(InstanceIds=[instance_id])
        state = details['Reservations'][0]['Instances'][0]['State']['Name']
        if state == 'running':
            public_ip = details['Reservations'][0]['Instances'][0].get('PublicIpAddress')
            running_instances.append({'InstanceId': instance_id, 'PublicIpAddress': public_ip})

    print(f"Running instances: {running_instances}")
    return running_instances

def main():
    cf_client = boto3.client('cloudformation', region_name=REGION)
    ec2_client = boto3.client('ec2', region_name=REGION)
    asg_client = boto3.client('autoscaling', region_name=REGION)

    # Step 1: Deploy or update the CloudFormation stack
    deploy_cloudformation_stack(cf_client)

    # Step 2: Monitor the stack deployment
    monitor_stack_deployment(cf_client)

    # Step 3: Verify running instances in the Auto Scaling Group
    running_instances = list_running_instances(ec2_client, asg_client)
    for instance in running_instances:
        print(f"Instance ID: {instance['InstanceId']}, Public IP: {instance['PublicIpAddress']}")

if __name__ == "__main__":
    main()
