# SMB/NAS driver — treats UNC paths as local paths (works if share is accessible)
import os
import shutil
import time
from typing import Dict


class Driver:
    """
    Driver for SMB/CIFS network shares via UNC paths
    Relies on OS-level SMB mounting or Windows UNC path support
    """
    
    def __init__(self, cfg: Dict[str, str]):
        """
        cfg should contain:
        - 'smb_path': UNC path to the favourites.xml file
          Example: \\\\NAS\\share\\kodi\\favourites\\favourites.xml
        - 'smb_user': Optional username (for mounting)
        - 'smb_password': Optional password (for mounting)
        
        Note: This driver assumes the SMB share is already accessible
        (either mounted or accessible via UNC path on Windows)
        """
        self.path = cfg.get("smb_path", "")
        self.user = cfg.get("smb_user", "")
        self.password = cfg.get("smb_password", "")
        
        if not self.path:
            raise IOError("SMB path not configured")
        
        # Normalize UNC path for Windows (convert forward slashes)
        self.path = self.path.replace("/", "\\")
        
        # Ensure it's a valid UNC path format
        if not (self.path.startswith("\\\\") or self.path.startswith("//")):
            raise IOError("SMB path must be a UNC path (e.g., \\\\server\\share\\path)")
        
        self.path = os.path.normpath(self.path)
    
    def stat(self) -> dict:
        """Return metadata about the file"""
        try:
            if not os.path.exists(self.path):
                # File doesn't exist yet - this is OK for first sync
                return {
                    "etag": "",
                    "modified_at": "",
                    "size": 0,
                    "exists": False
                }
            
            stat_info = os.stat(self.path)
            mtime = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(stat_info.st_mtime))
            
            return {
                "etag": str(stat_info.st_mtime),  # Use mtime as etag
                "modified_at": mtime,
                "size": stat_info.st_size,
                "exists": True
            }
        except PermissionError:
            raise IOError(f"Permission denied accessing SMB path {self.path} (check credentials)")
        except Exception as e:
            raise IOError(f"Cannot access SMB path {self.path}: {str(e)}")
    
    def download(self) -> bytes:
        """Read the file from SMB share"""
        try:
            if not os.path.exists(self.path):
                # Return empty favourites if file doesn't exist
                return b'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n<favourites>\n</favourites>\n'
            
            with open(self.path, 'rb') as f:
                return f.read()
        except PermissionError:
            raise IOError(f"Permission denied reading from SMB path {self.path}")
        except Exception as e:
            raise IOError(f"Cannot read from SMB path {self.path}: {str(e)}")
    
    def upload(self, data: bytes, metadata: dict = None) -> None:
        """Serialize writers and replace without deleting the previous file."""
        try:
            from ..storage import atomic_write, file_lock
        except ImportError:
            from storage import atomic_write, file_lock
        with file_lock(self.path + '.lock'):
            if metadata and metadata.get('etag'):
                current = self.stat().get('etag')
                if current != metadata['etag']:
                    raise IOError('File changed since download (ETag mismatch)')
            atomic_write(self.path, data)
    
    def copy_backup(self, backup_name: str) -> None:
        """Create a backup copy of the file on the SMB share"""
        try:
            if not os.path.exists(self.path):
                return
            
            # Create backup in same directory
            parent = os.path.dirname(self.path)
            backup_path = os.path.join(parent, backup_name)
            shutil.copy2(self.path, backup_path)
        except Exception:
            # Backup is optional, don't fail if it doesn't work
            pass
