# NFS driver — treats NFS paths as local mounted paths or NFS URLs
import os
import shutil
import time
from typing import Dict


class Driver:
    """
    Driver for NFS network shares
    Supports both mounted paths and nfs:// URLs (if accessible via OS)
    """
    
    def __init__(self, cfg: Dict[str, str]):
        """
        cfg should contain:
        - 'nfs_path': Path to the favourites.xml file
          Examples:
            - Mounted: /mnt/nfs/kodi/favourites/favourites.xml
            - NFS URL: nfs://nas.local/export/kodi/favourites/favourites.xml
        
        Note: This driver assumes NFS share is already mounted or accessible
        For nfs:// URLs, OS must support direct NFS access
        """
        self.path = cfg.get("nfs_path", "")
        
        if not self.path:
            raise IOError("NFS path not configured")
        
        # Handle nfs:// URLs by converting to local path if possible
        # This assumes Kodi has mounted NFS shares
        if self.path.startswith("nfs://"):
            # For now, treat as unsupported - would need nfs-client library
            raise IOError("Direct nfs:// URLs not yet supported. Please mount NFS share and use local path")
        
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
            raise IOError(f"Permission denied accessing NFS path {self.path}")
        except Exception as e:
            raise IOError(f"Cannot access NFS path {self.path}: {str(e)}")
    
    def download(self) -> bytes:
        """Read the file from NFS share"""
        try:
            if not os.path.exists(self.path):
                # Return empty favourites if file doesn't exist
                return b'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n<favourites>\n</favourites>\n'
            
            with open(self.path, 'rb') as f:
                return f.read()
        except PermissionError:
            raise IOError(f"Permission denied reading from NFS path {self.path}")
        except Exception as e:
            raise IOError(f"Cannot read from NFS path {self.path}: {str(e)}")
    
    def upload(self, data: bytes, metadata: dict = None) -> None:
        """Write data to the NFS share atomically"""
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
            
        except PermissionError:
            # Clean up temp file if it exists
            tmp_path = self.path + ".tmp"
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except:
                    pass
            raise IOError(f"Permission denied writing to NFS path {self.path}")
        except Exception as e:
            # Clean up temp file if it exists
            tmp_path = self.path + ".tmp"
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except:
                    pass
            raise IOError(f"Cannot write to NFS path {self.path}: {str(e)}")
    
    def copy_backup(self, backup_name: str) -> None:
        """Create a backup copy of the file on the NFS share"""
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
