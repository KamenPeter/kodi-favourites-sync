# HTTP(S) generic driver — GET/PUT with optional auth header
import urllib.request
import urllib.error
import ssl
from typing import Dict, Optional


class Driver:
    """Generic HTTP(S) driver for GET/PUT operations with optional authentication"""
    
    def __init__(self, cfg: Dict[str, str]):
        """
        cfg should contain:
        - 'http_get': URL for GET requests (download)
        - 'http_put': URL for PUT requests (upload)
        - 'http_auth_header': Optional auth header (e.g., "Bearer token123")
        - 'tls_verify': Boolean for TLS certificate validation
        - 'custom_ca': Optional path to custom CA bundle
        - 'timeout_sec': Network timeout
        """
        self.get_url = cfg.get("http_get", "")
        self.put_url = cfg.get("http_put", "")
        self.auth_header = cfg.get("http_auth_header", "")
        self.tls_verify = bool(cfg.get("tls_verify", True))
        self.custom_ca = cfg.get("custom_ca") or None
        self.timeout = int(cfg.get("timeout_sec", 15) or 15)
        
        if not self.get_url:
            raise IOError("HTTP GET URL not configured")
        if not self.put_url:
            raise IOError("HTTP PUT URL not configured")
        
        # Require HTTPS for security
        if not self.get_url.lower().startswith("https://"):
            raise IOError("HTTP GET URL must use HTTPS")
        if not self.put_url.lower().startswith("https://"):
            raise IOError("HTTP PUT URL must use HTTPS")
        
        # Setup SSL context
        if self.custom_ca:
            self.context = ssl.create_default_context(cafile=self.custom_ca)
        elif self.tls_verify:
            self.context = ssl.create_default_context()
        else:
            self.context = ssl._create_unverified_context()
    
    def _headers(self) -> Dict[str, str]:
        """Build headers with optional authentication"""
        headers = {"Accept": "*/*", "User-Agent": "Kodi-Favourites-Sync/1.0"}
        
        if self.auth_header:
            # Support both "Bearer token" and just "token" formats
            if self.auth_header.startswith("Bearer ") or self.auth_header.startswith("Basic "):
                headers["Authorization"] = self.auth_header
            else:
                headers["Authorization"] = f"Bearer {self.auth_header}"
        
        return headers
    
    def stat(self) -> dict:
        """Get file metadata via HEAD request"""
        req = urllib.request.Request(self.get_url, method="HEAD", headers=self._headers())
        try:
            with urllib.request.urlopen(req, context=self.context, timeout=self.timeout) as resp:
                etag = resp.headers.get("ETag") or resp.headers.get("Etag") or ""
                length = int(resp.headers.get("Content-Length") or 0)
                modified = resp.headers.get("Last-Modified") or ""
                
                return {
                    "etag": etag,
                    "modified_at": modified,
                    "size": length,
                    "exists": True
                }
        except urllib.error.HTTPError as e:
            if e.code == 404:
                # File doesn't exist yet
                return {"etag": "", "modified_at": "", "size": 0, "exists": False}
            raise IOError(f"HTTP stat failed: {e.code} {e.reason}")
        except Exception as e:
            raise IOError(f"HTTP stat error: {str(e)}")
    
    def download(self) -> bytes:
        """Download file via GET request"""
        req = urllib.request.Request(self.get_url, method="GET", headers=self._headers())
        try:
            with urllib.request.urlopen(req, context=self.context, timeout=self.timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                # Return empty favourites XML
                return b'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n<favourites>\n</favourites>\n'
            raise IOError(f"HTTP download failed: {e.code} {e.reason}")
        except Exception as e:
            raise IOError(f"HTTP download error: {str(e)}")
    
    def upload(self, data: bytes, metadata: dict = None) -> None:
        """Upload file via PUT request"""
        headers = self._headers()
        headers["Content-Type"] = "application/xml"
        
        # Add If-Match header if etag is provided (for concurrency control)
        if metadata and metadata.get("etag"):
            headers["If-Match"] = metadata["etag"]
        
        req = urllib.request.Request(self.put_url, data=data, method="PUT", headers=headers)
        try:
            with urllib.request.urlopen(req, context=self.context, timeout=self.timeout) as resp:
                if resp.status not in (200, 201, 204):
                    raise IOError(f"HTTP upload returned unexpected status: {resp.status}")
        except urllib.error.HTTPError as e:
            if e.code == 412:
                raise IOError("HTTP upload failed: ETag mismatch (412 Precondition Failed)")
            raise IOError(f"HTTP upload failed: {e.code} {e.reason}")
        except Exception as e:
            raise IOError(f"HTTP upload error: {str(e)}")
    
    def copy_backup(self, backup_name: str) -> None:
        """
        Optional backup operation - not supported by basic HTTP
        Would require custom endpoint support
        """
        # HTTP GET/PUT doesn't have a standard backup mechanism
        # Server would need to implement its own versioning
        pass
