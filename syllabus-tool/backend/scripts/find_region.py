import psycopg2
import sys

password = "Sm13773460467!!~"
project_ref = "mnsyrhielfxuyzvlkatt"
user = f"postgres.{project_ref}"
dbname = "postgres"

regions = [
    "aws-0-us-east-1",
    "aws-0-ap-southeast-1",
    "aws-0-eu-central-1",
    "aws-0-us-west-1",
    "aws-0-ap-northeast-1",
    "aws-0-ap-northeast-2",
    "aws-0-ap-south-1",
    "aws-0-sa-east-1",
    "aws-0-eu-west-1",
    "aws-0-eu-west-2",
    "aws-0-eu-west-3",
    "aws-0-ca-central-1"
]

print(f"Testing connectivity for project {project_ref}...")

for region in regions:
    host = f"{region}.pooler.supabase.com"
    dsn = f"dbname='{dbname}' user='{user}' host='{host}' password='{password}' port='6543'"
    print(f"Testing {region}...", end=" ", flush=True)
    try:
        conn = psycopg2.connect(dsn, connect_timeout=3)
        print("SUCCESS! FOUND IT!")
        print(f"HOST: {host}")
        conn.close()
        break
    except psycopg2.OperationalError as e:
        msg = str(e).strip()
        if "Tenant or user not found" in msg:
            print("Failed (Wrong Region)")
        elif "timeout" in msg:
             print("Timeout")
        elif "network unreachable" in msg:
             print("Network Unreachable")
        else:
            print(f"Error: {msg}")
    except Exception as e:
        print(f"Error: {e}")
