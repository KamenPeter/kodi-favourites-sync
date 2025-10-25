# S3 driver (AWS/MinIO/Wasabi) — implement with boto3 or signed requests
# Backend driver stub. Implement: stat(), download(), upload(), copy_backup()
class BackendBase:
    def stat(self) -> dict: raise NotImplementedError
    def download(self) -> bytes: raise NotImplementedError
    def upload(self, data: bytes, metadata: dict) -> None: raise NotImplementedError
    def copy_backup(self, backup_name: str) -> None: pass
