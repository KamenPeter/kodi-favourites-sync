import json
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
	from .sync import _run, _load_status, validate_endpoint, ADDON_DATA
except Exception:
	from sync import _run, _load_status, validate_endpoint, ADDON_DATA
try:
	from .logutil import log_info, log_error, kvfmt
except Exception:
	from logutil import log_info, log_error, kvfmt

_server_thread = None


class Handler(BaseHTTPRequestHandler):
	def _json(self, code, obj):
		data = json.dumps(obj).encode("utf-8")
		self.send_response(code)
		self.send_header("Content-Type", "application/json")
		self.send_header("Content-Length", str(len(data)))
		self.end_headers()
		self.wfile.write(data)

	def do_POST(self):
		try:
			length = int(self.headers.get('Content-Length', 0))
			raw = self.rfile.read(length) if length else b"{}"
			body = json.loads(raw.decode('utf-8') or '{}')
		except Exception:
			body = {}
		method = body.get("method")
		params = body.get("params") or {}
		try:
			if method == "FavouritesSync.Run":
				mode = params.get("mode") or "pull"
				dry = bool(params.get("dry_run", False))
				res = _run(mode, dry)
				self._json(200, {"status": res.get("result"), "changed_items": res.get("changed_items", 0), "error": res.get("error")})
			elif method == "FavouritesSync.Status":
				self._json(200, _load_status())
			elif method == "FavouritesSync.Validate":
				r = validate_endpoint()
				if r.get("ok"):
					self._json(200, {"ok": True, "details": r.get("details")})
				else:
					self._json(401, {"ok": False, "error": r.get("error")})
			elif method == "FavouritesSync.ListBackups":
				files = [f for f in os.listdir(ADDON_DATA) if f.endswith('.xml.bak')]
				files.sort(reverse=True)
				self._json(200, {"backups": files})
			else:
				self._json(400, {"error": "Unknown method"})
		except Exception as e:
			log_error(kvfmt(event="rpc_error", error=str(e)))
			self._json(500, {"error": str(e)})

	def log_message(self, fmt, *args):
		# silence to avoid clutter
		return


def start_server(host: str = "127.0.0.1", port: int = None):
	global _server_thread
	if _server_thread and _server_thread.is_alive():
		return
	try:
		port = port or int(os.environ.get("FAVSYNC_RPC_PORT", "8765"))
	except Exception:
		port = 8765
	server = HTTPServer((host, port), Handler)
	def run():
		log_info(kvfmt(event="rpc_listen", host=host, port=port))
		try:
			server.serve_forever(poll_interval=0.5)
		except Exception:
			pass
	t = threading.Thread(target=run, name="favsync-rpc", daemon=True)
	t.start()
	_server_thread = t

