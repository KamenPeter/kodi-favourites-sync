# SFTP driver — requires paramiko library
from typing import Dict


class Driver:
    """
    SFTP driver using paramiko for SSH file transfer
    Requires: pip install paramiko
    """
    
    def __init__(self, cfg: Dict[str, str]):
        """
        cfg should contain:
        - 'sftp_host': SFTP server hostname
        - 'sftp_port': SFTP port (default 22)
        - 'sftp_user': Username
        - 'sftp_password': Password (optional if using key)
        - 'sftp_keyfile': Path to private key file (optional)
        - 'sftp_path': Remote path to favourites.xml
        - 'timeout_sec': Connection timeout
        """
        self.host = cfg.get("sftp_host", "")
        self.port = int(cfg.get("sftp_port", 22))
        self.user = cfg.get("sftp_user", "")
        self.password = cfg.get("sftp_password", "")
        self.keyfile = cfg.get("sftp_keyfile", "")
        self.remote_path = cfg.get("sftp_path", "")
        self.timeout = int(cfg.get("timeout_sec", 15) or 15)
        
        if not self.host:
            raise IOError("SFTP host not configured")
        if not self.user:
            raise IOError("SFTP username not configured")
        if not self.remote_path:
            raise IOError("SFTP remote path not configured")
        
        # Try to import paramiko
        try:
            import paramiko
            self.paramiko = paramiko
        except ImportError:
            raise IOError("SFTP requires 'paramiko' library. Install with: pip install paramiko")
        
        self._client = None
        self._sftp = None
    
    def _connect(self):
        """Establish SFTP connection"""
        if self._sftp is not None:
            return self._sftp
        
        try:
            # Create SSH client
            self._client = self.paramiko.SSHClient()
            self._client.set_missing_host_key_policy(self.paramiko.AutoAddPolicy())
            
            # Connect with password or key
            if self.keyfile:
                self._client.connect(
                    hostname=self.host,
                    port=self.port,
                    username=self.user,
                    key_filename=self.keyfile,
                    timeout=self.timeout
                )
            else:
                self._client.connect(
                    hostname=self.host,
                    port=self.port,
                    username=self.user,
                    password=self.password,
                    timeout=self.timeout
                )
            
            # Open SFTP session
            self._sftp = self._client.open_sftp()
            return self._sftp
            
        except Exception as e:
            self._close()
            raise IOError(f"SFTP connection failed: {str(e)}")
    
    def _close(self):
        """Close SFTP connection"""
        if self._sftp:
            try:
                self._sftp.close()
            except:
                pass
            self._sftp = None
        
        if self._client:
            try:
                self._client.close()
            except:
                pass
            self._client = None
    
    def stat(self) -> dict:
        """Get remote file statistics"""
        sftp = self._connect()
        try:
            stat_info = sftp.stat(self.remote_path)
            
            import time
            mtime = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(stat_info.st_mtime))
            
            return {
                "etag": str(stat_info.st_mtime),
                "modified_at": mtime,
                "size": stat_info.st_size,
                "exists": True
            }
        except IOError:
            # File doesn't exist
            return {"etag": "", "modified_at": "", "size": 0, "exists": False}
        except Exception as e:
            raise IOError(f"SFTP stat failed: {str(e)}")
        finally:
            self._close()
    
    def download(self) -> bytes:
        """Download file from SFTP server"""
        sftp = self._connect()
        try:
            # Download to memory
            import io
            buffer = io.BytesIO()
            sftp.getfo(self.remote_path, buffer)
            return buffer.getvalue()
            
        except IOError:
            # File doesn't exist, return empty favourites
            return b'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n<favourites>\n</favourites>\n'
        except Exception as e:
            raise IOError(f"SFTP download failed: {str(e)}")
        finally:
            self._close()
    
    def upload(self, data: bytes, metadata: dict = None) -> None:
        """Upload file to SFTP server"""
        sftp = self._connect()
        try:
            # Create parent directory if needed
            import os
            parent = os.path.dirname(self.remote_path)
            if parent:
                try:
                    sftp.stat(parent)
                except IOError:
                    # Directory doesn't exist, create it
                    self._mkdir_p(sftp, parent)
            
            # Upload from memory
            import io
            buffer = io.BytesIO(data)
            sftp.putfo(buffer, self.remote_path)
            
        except Exception as e:
            raise IOError(f"SFTP upload failed: {str(e)}")
        finally:
            self._close()
    
    def _mkdir_p(self, sftp, remote_dir):
        """Create directory and parents recursively"""
        import os
        if not remote_dir or remote_dir == '/':
            return
        
        try:
            sftp.stat(remote_dir)
        except IOError:
            # Directory doesn't exist, create parent first
            parent = os.path.dirname(remote_dir)
            if parent and parent != remote_dir:
                self._mkdir_p(sftp, parent)
            sftp.mkdir(remote_dir)
    
    def copy_backup(self, backup_name: str) -> None:
        """Create backup copy on SFTP server"""
        sftp = self._connect()
        try:
            import os
            parent = os.path.dirname(self.remote_path)
            backup_path = os.path.join(parent, backup_name).replace('\\', '/')
            
            # Read and write to create backup
            data = sftp.open(self.remote_path, 'rb').read()
            with sftp.open(backup_path, 'wb') as f:
                f.write(data)
        except Exception:
            # Backup is optional
            pass
        finally:
            self._close()
