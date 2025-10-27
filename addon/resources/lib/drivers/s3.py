# S3 driver (AWS/MinIO/Wasabi) — requires boto3 library
from typing import Dict, Optional


class Driver:
    """
    S3-compatible storage driver using boto3
    Supports: AWS S3, MinIO, Wasabi, DigitalOcean Spaces, etc.
    Requires: pip install boto3
    """
    
    def __init__(self, cfg: Dict[str, str]):
        """
        cfg should contain:
        - 's3_endpoint': S3 endpoint URL (e.g., s3.amazonaws.com, s3.us-east-1.amazonaws.com)
        - 's3_region': AWS region (e.g., us-east-1)
        - 's3_bucket': Bucket name
        - 's3_key': Object key (path to favourites.xml)
        - 's3_access': Access key ID
        - 's3_secret': Secret access key
        - 's3_versioning': Whether bucket has versioning enabled
        """
        self.endpoint = cfg.get("s3_endpoint", "")
        self.region = cfg.get("s3_region", "us-east-1")
        self.bucket = cfg.get("s3_bucket", "")
        self.key = cfg.get("s3_key", "")
        self.access_key = cfg.get("s3_access", "")
        self.secret_key = cfg.get("s3_secret", "")
        self.versioning = cfg.get("s3_versioning", "true").lower() == "true"
        
        if not self.endpoint:
            raise IOError("S3 endpoint not configured")
        if not self.bucket:
            raise IOError("S3 bucket not configured")
        if not self.key:
            raise IOError("S3 object key not configured")
        if not self.access_key:
            raise IOError("S3 access key not configured")
        if not self.secret_key:
            raise IOError("S3 secret key not configured")
        
        # Try to import boto3
        try:
            import boto3
            self.boto3 = boto3
        except ImportError:
            raise IOError("S3 requires 'boto3' library. Install with: pip install boto3")
        
        # Build endpoint URL
        if not self.endpoint.startswith("http"):
            self.endpoint = f"https://{self.endpoint}"
        
        # Create S3 client
        try:
            self.s3 = self.boto3.client(
                's3',
                endpoint_url=self.endpoint,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region
            )
        except Exception as e:
            raise IOError(f"Failed to create S3 client: {str(e)}")
        
        self._etag: Optional[str] = None
    
    def stat(self) -> dict:
        """Get object metadata"""
        try:
            response = self.s3.head_object(Bucket=self.bucket, Key=self.key)
            
            # Extract metadata
            etag = response.get('ETag', '').strip('"')
            self._etag = etag
            modified = response.get('LastModified', '')
            size = response.get('ContentLength', 0)
            
            # Format modified time
            if modified:
                modified = modified.strftime("%Y-%m-%dT%H:%M:%SZ")
            
            return {
                "etag": etag,
                "modified_at": modified,
                "size": size,
                "exists": True
            }
            
        except self.s3.exceptions.ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            if error_code == '404':
                # Object doesn't exist
                return {"etag": "", "modified_at": "", "size": 0, "exists": False}
            raise IOError(f"S3 stat failed: {str(e)}")
        except Exception as e:
            raise IOError(f"S3 stat error: {str(e)}")
    
    def download(self) -> bytes:
        """Download object from S3"""
        try:
            response = self.s3.get_object(Bucket=self.bucket, Key=self.key)
            
            # Extract ETag
            etag = response.get('ETag', '').strip('"')
            self._etag = etag
            
            # Read body
            data = response['Body'].read()
            return data
            
        except self.s3.exceptions.ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            if error_code == 'NoSuchKey':
                # Object doesn't exist, return empty favourites
                return b'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n<favourites>\n</favourites>\n'
            raise IOError(f"S3 download failed: {str(e)}")
        except Exception as e:
            raise IOError(f"S3 download error: {str(e)}")
    
    def upload(self, data: bytes, metadata: dict = None) -> None:
        """Upload object to S3"""
        try:
            extra_args = {
                'ContentType': 'application/xml'
            }
            
            # Add ETag condition if provided (for optimistic locking)
            if metadata and metadata.get("etag"):
                extra_args['IfMatch'] = metadata["etag"]
            
            # Upload
            import io
            self.s3.upload_fileobj(
                io.BytesIO(data),
                self.bucket,
                self.key,
                ExtraArgs=extra_args
            )
            
        except self.s3.exceptions.ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            if error_code == 'PreconditionFailed':
                raise IOError("S3 upload failed: ETag mismatch (PreconditionFailed)")
            raise IOError(f"S3 upload failed: {str(e)}")
        except Exception as e:
            raise IOError(f"S3 upload error: {str(e)}")
    
    def copy_backup(self, backup_name: str) -> None:
        """
        Create backup copy in S3
        If versioning is enabled, S3 handles it automatically
        Otherwise, copy to a backup key
        """
        if self.versioning:
            # S3 versioning handles backups automatically
            return
        
        try:
            # Copy object to backup key
            backup_key = self.key.rsplit('/', 1)[0] + '/' + backup_name if '/' in self.key else backup_name
            
            self.s3.copy_object(
                Bucket=self.bucket,
                CopySource={'Bucket': self.bucket, 'Key': self.key},
                Key=backup_key
            )
        except Exception:
            # Backup is optional
            pass
