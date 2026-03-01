from minio import Minio
from minio.error import S3Error
from app.core.config import settings
import io
import os
import shutil

class StorageService:
    def __init__(self):
        self.use_local_storage = False
        self.local_storage_path = "uploads"

        if not settings.MINIO_ENDPOINT:
            self.use_local_storage = True
            if not os.path.exists(self.local_storage_path):
                os.makedirs(self.local_storage_path)
            return

        try:
            self.client = Minio(
                settings.MINIO_ENDPOINT,
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                secure=settings.MINIO_SECURE,
            )
            self._ensure_bucket()
        except Exception as e:
            print(f"MinIO connection failed, switching to local storage: {e}")
            self.use_local_storage = True
            if not os.path.exists(self.local_storage_path):
                os.makedirs(self.local_storage_path)

    def _ensure_bucket(self):
        try:
            if not self.client.bucket_exists(settings.MINIO_BUCKET_NAME):
                self.client.make_bucket(settings.MINIO_BUCKET_NAME)
        except Exception as e:
            # Re-raise to trigger fallback in __init__
            raise e

    def upload_file(self, file_name: str, file_data: bytes, content_type: str):
        if self.use_local_storage:
            try:
                file_path = os.path.join(self.local_storage_path, file_name)
                with open(file_path, "wb") as f:
                    f.write(file_data)
                return file_name
            except Exception as e:
                print(f"Local Upload Error: {e}")
                return None
        
        try:
            result = self.client.put_object(
                settings.MINIO_BUCKET_NAME,
                file_name,
                io.BytesIO(file_data),
                len(file_data),
                content_type=content_type
            )
            return result.object_name
        except S3Error as e:
            print(f"Upload Error: {e}")
            return None

    def list_files(self):
        if self.use_local_storage:
            files = []
            if os.path.exists(self.local_storage_path):
                for f in os.listdir(self.local_storage_path):
                    path = os.path.join(self.local_storage_path, f)
                    stat = os.stat(path)
                    files.append({
                        "name": f,
                        "size": stat.st_size,
                        "last_modified": stat.st_mtime
                    })
            return files

        try:
            objects = self.client.list_objects(settings.MINIO_BUCKET_NAME)
            return [{"name": obj.object_name, "size": obj.size, "last_modified": obj.last_modified} for obj in objects]
        except S3Error as e:
            print(f"List Error: {e}")
            return []

    def get_file(self, object_name: str):
        if self.use_local_storage:
            try:
                file_path = os.path.join(self.local_storage_path, object_name)
                if os.path.exists(file_path):
                    with open(file_path, "rb") as f:
                        return f.read()
                return None
            except Exception as e:
                print(f"Local Get File Error: {e}")
                return None

        try:
            response = self.client.get_object(settings.MINIO_BUCKET_NAME, object_name)
            return response.read()
        except S3Error as e:
            print(f"Get File Error: {e}")
            return None

    def delete_file(self, object_name: str):
        if self.use_local_storage:
            try:
                file_path = os.path.join(self.local_storage_path, object_name)
                if os.path.exists(file_path):
                    os.remove(file_path)
                    return True
                return False
            except Exception as e:
                print(f"Local Delete Error: {e}")
                return False

        try:
            self.client.remove_object(settings.MINIO_BUCKET_NAME, object_name)
            return True
        except S3Error as e:
            print(f"Delete Error: {e}")
            return False

storage_service = StorageService()
