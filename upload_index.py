import boto3
import paramiko
from scp import SCPClient

# Path to your index.html file
LOCAL_FILE_PATH = r"C:\Users\kobby\GIT_AWS_DEPLOY\aws-web-dep\index.html"

# Path to your private key file
KEY_PATH = r"C:\Users\kobby\Downloads\kobbylenz.pem"  # Replace with the actual absolute path to your .pem file

# SSH user details
SSH_USER = "ubuntu"  # Default username for Ubuntu AMI

# Function to fetch public IPs of instances
def get_instance_ips():
    ec2_client = boto3.client('ec2', region_name='us-east-2')
    response = ec2_client.describe_instances(
        Filters=[
            {"Name": "tag:Name", "Values": ["WebServerInstanceUbuntu"]},
            {"Name": "instance-state-name", "Values": ["running"]}
        ]
    )
    ips = []
    for reservation in response['Reservations']:
        for instance in reservation['Instances']:
            ips.append(instance['PublicIpAddress'])
    return ips

# Function to copy index.html to instance
def copy_file_to_instance(ip, key_path, local_path):
    print(f"Connecting to instance {ip}...")
    key = paramiko.RSAKey.from_private_key_file(key_path)
    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        # Connect to the instance
        ssh_client.connect(hostname=ip, username=SSH_USER, pkey=key)

        # SCP the file to /tmp
        with SCPClient(ssh_client.get_transport()) as scp:
            scp.put(local_path, "/tmp/index.html")
        
        # Move the file to /var/www/html
        stdin, stdout, stderr = ssh_client.exec_command("sudo mv /tmp/index.html /var/www/html/")
        stdout.channel.recv_exit_status()  # Wait for the command to complete
        print(f"File successfully moved to /var/www/html on {ip}")
    except Exception as e:
        print(f"Failed to copy file to {ip}: {e}")
    finally:
        ssh_client.close()

# Main function
def main():
    # Step 1: Fetch the public IPs of running instances
    print("Fetching public IPs of running instances...")
    instance_ips = get_instance_ips()
    print(f"Instances found: {instance_ips}")

    # Step 2: Copy the index.html file to each instance
    for ip in instance_ips:
        copy_file_to_instance(ip, KEY_PATH, LOCAL_FILE_PATH)

if __name__ == "__main__":
    main()


