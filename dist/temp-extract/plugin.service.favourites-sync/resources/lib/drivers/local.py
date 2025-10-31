"""Local/Network path driver - supports local files and Windows UNC paths (\\server\share)"""
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
                # Return empty favourites if file doesn't exist
                return b'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n<favourites>\n</favourites>\n'
            
            with open(self.path, 'rb') as f:
                return f.read()
        except Exception as e:
            raise IOError(f"Cannot read {self.path}: {str(e)}")
    
    def upload(self, data: bytes, metadata: dict = None) -> None:
        """Write data to the file atomically"""
        try:
            # Create parent directory if it doesn't exist
            parent = os.path.dirname(self.path)
            if parent and not os.path.exists(parent):
                os.makedirs(parent, exist_ok=True)
            
            # Atomic write: write to temp file then move
            tmp_path = self.path + ".tmp"
            with open(tmp_path, 'wb') as f:
                f.write(data)
            
            # Replace existing file
            if os.path.exists(self.path):
                os.remove(self.path)
            os.rename(tmp_path, self.path)
            
        except Exception as e:
            # Clean up temp file if it exists
            tmp_path = self.path + ".tmp"
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except:
                    pass
            raise IOError(f"Cannot write to {self.path}: {str(e)}")
    
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

