from minio import Minio
from minio.error import S3Error

def test_minio(endpoint, access_key, secret_key):
    print(f"Testing MinIO: {endpoint} with {access_key}")
    try:
        client = Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=False
        )
        # List buckets to test auth
        buckets = client.list_buckets()
        print("Success! Buckets:")
        for bucket in buckets:
            print(bucket.name, bucket.creation_date)
        return True
    except S3Error as e:
        print(f"Failed: {e}")
        return False
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    # Test 1: User provided
    print("--- Test 1: User provided ---")
    test_minio("localhost:9000", "admin", "123321")
    
    # Test 2: Default
    print("\n--- Test 2: Default (minioadmin) ---")
    test_minio("localhost:9000", "minioadmin", "minioadmin")
