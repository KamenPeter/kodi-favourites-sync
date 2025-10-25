# WebDAV driver implemented with urllib; supports HTTPS, Basic/Bearer auth, ETag, COPY
import base64
import ssl
import urllib.request
import urllib.error
from typing import Optional, Dict


class Driver:
    def __init__(self, cfg: Dict[str, str]):
        # cfg keys: webdav_url, webdav_path, webdav_user, webdav_password, tls_verify, custom_ca
        self.base_url = cfg.get("webdav_url", "").rstrip("/")
        path = cfg.get("webdav_path", "/favourites.xml")
        if not path.startswith("/"):
            path = "/" + path
        self.url = self.base_url + path
        self.user = cfg.get("webdav_user", "")
        self.password = cfg.get("webdav_password", "")
        self.token = cfg.get("http_auth_header", "")  # optional Bearer header from HTTP driver reuse
        self.tls_verify = bool(cfg.get("tls_verify", True))
        self.custom_ca = cfg.get("custom_ca") or None
        self._etag: Optional[str] = None
        self.timeout = int(cfg.get("timeout_sec", 15) or 15)

        if not self.base_url.lower().startswith("https://"):
            raise IOError("WebDAV must use HTTPS")

        if self.custom_ca:
            self.context = ssl.create_default_context(cafile=self.custom_ca)
        elif self.tls_verify:
            self.context = ssl.create_default_context()
        else:
            self.context = ssl._create_unverified_context()

    def _headers(self) -> Dict[str, str]:
        headers = {"Accept": "*/*"}
        if self.user or self.password:
            token = base64.b64encode(f"{self.user}:{self.password}".encode()).decode()
            headers["Authorization"] = f"Basic {token}"
        elif self.token:
            headers["Authorization"] = self.token if self.token.startswith("Bearer ") else f"Bearer {self.token}"
        return headers

    def stat(self) -> dict:
        req = urllib.request.Request(self.url, method="HEAD", headers=self._headers())
        try:
            with urllib.request.urlopen(req, context=self.context, timeout=self.timeout) as resp:
                etag = resp.headers.get("ETag") or resp.headers.get("Etag")
                self._etag = etag
                length = int(resp.headers.get("Content-Length") or 0)
                mod = resp.headers.get("Last-Modified") or ""
                return {"etag": etag or "", "modified_at": mod, "size": length}
        except urllib.error.HTTPError as e:
            if e.code == 404:
                # treat as empty remote file
                return {"etag": "", "modified_at": "", "size": 0}
            raise IOError(f"WebDAV stat failed: {e.code}")

    def download(self) -> bytes:
        req = urllib.request.Request(self.url, method="GET", headers=self._headers())
        try:
            with urllib.request.urlopen(req, context=self.context, timeout=self.timeout) as resp:
                etag = resp.headers.get("ETag") or resp.headers.get("Etag")
                self._etag = etag
                return resp.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return b""
            raise IOError(f"WebDAV download failed: {e.code}")

    def upload(self, data: bytes, metadata: dict) -> None:
        # Use If-None-Match or If-Match based on known etag if provided in metadata
        headers = self._headers()
        etag = metadata.get("etag") or self._etag
        if etag:
            headers["If-Match"] = etag
        req = urllib.request.Request(self.url, data=data, method="PUT", headers=headers)
        try:
            with urllib.request.urlopen(req, context=self.context, timeout=self.timeout) as _:
                return
        except urllib.error.HTTPError as e:
            # 412 Precondition Failed indicates etag mismatch; bubble up
            raise IOError(f"WebDAV upload failed: {e.code}")

    def copy_backup(self, backup_name: str) -> None:
        # COPY {url} Destination: {url}.bak
        dest = self.url.rsplit("/", 1)[0] + "/" + backup_name
        headers = self._headers()
        headers["Destination"] = dest
        # Custom request with COPY method
        class _Copy(urllib.request.Request):
            def get_method(self):
                return "COPY"
        req = _Copy(self.url, headers=headers)
        try:
            with urllib.request.urlopen(req, context=self.context, timeout=self.timeout):
                return
        except Exception:
            # optional; ignore failures
            return

