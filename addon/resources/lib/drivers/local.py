r"""Local/Network path driver - supports local files and Windows UNC paths (\\server\share)"""
import os
import shutil
import time

class Driver:
    """Driver for local file system or Windows network shares (SMB/UNC paths)"""
    
    def __init__(self, cfg: dict):
        """
        cfg should contain:
        - 'local_path': Full path to the favourites.xml file
          Examples: 
            - Local: C:\\sync\\favourites.xml
            - UNC: \\\\server\\share\\kodi\\favourites.xml
        """
        self.path = cfg.get("local_path", "")
        if not self.path:
            raise IOError("Local path not configured")
        
        # Normalize path for Windows
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
        except Exception as e:
            raise IOError(f"Cannot access path {self.path}: {str(e)}")
    
    def download(self) -> bytes:
        """Read the file and return its contents"""
        try:
            if not os.path.exists(self.path):
                # Check if parent directory exists - if not, path is unavailable
                parent = os.path.dirname(self.path)
                if parent and not os.path.exists(parent):
                    # Parent directory doesn't exist - this is a configuration/availability issue
                    raise IOError(f"Path not accessible: {parent}")
                # File doesn't exist but parent does - this is first sync, return empty
                return b'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n<favourites>\n</favourites>\n'
            
            with open(self.path, 'rb') as f:
                return f.read()
        except Exception as e:
            raise IOError(f"Cannot read {self.path}: {str(e)}")
    
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
        """Optional: Create a backup copy of the file"""
        try:
            if not os.path.exists(self.path):
                return
            
            backup_path = self.path + "." + backup_name
            shutil.copy2(self.path, backup_path)
        except Exception:
            # Backup is optional, don't fail if it doesn't work
            pass
