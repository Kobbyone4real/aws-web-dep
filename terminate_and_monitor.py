import boto3
import time

def terminate_and_monitor():
    ec2_client = boto3.client('ec2', region_name='us-east-2')
    autoscaling_client = boto3.client('autoscaling', region_name='us-east-2')

    # Step 1: Fetch running instances in the Auto Scaling Group
    print("Fetching running instances in the Auto Scaling Group...")
    response = ec2_client.describe_instances(
        Filters=[
            {"Name": "tag:Name", "Values": ["WebServerInstanceUbuntu"]},
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
        print("Less than 2 instances running. Ensure the Auto Scaling Group is properly configured.")
        return

    print(f"Running instances found: {instances}")

    # Step 2: Terminate one of the instances
    instance_to_terminate = instances[0]['InstanceId']
    print(f"Terminating instance: {instance_to_terminate}...")
    ec2_client.terminate_instances(InstanceIds=[instance_to_terminate])

    # Step 3: Monitor Auto Scaling Group for new instance
    print("Monitoring Auto Scaling Group for replacement instance...")
    while True:
        time.sleep(10)  # Wait before checking again
        response = ec2_client.describe_instances(
            Filters=[
                {"Name": "tag:Name", "Values": ["WebServerInstanceUbuntu"]},
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

if __name__ == "__main__":
    terminate_and_monitor()
