import os
import time
import xbmc
import xbmcaddon

_ADDON = xbmcaddon.Addon()
_ADDON_ID = _ADDON.getAddonInfo('id')

def _logfile_path():
	try:
		import xbmcvfs
		base = xbmcvfs.translatePath(f"special://profile/addon_data/{_ADDON_ID}")
	except Exception:
		base = os.path.expanduser(os.path.join("~", f".{_ADDON_ID}"))
	if not os.path.exists(base):
		try:
			os.makedirs(base, exist_ok=True)
		except Exception:
			pass
	return os.path.join(base, "log.txt")

_REDACT_KEYS = {"password", "secret", "token", "authorization", "auth", "bearer", "access_key", "secret_key"}

def redact(value: str) -> str:
	if not isinstance(value, str):
		return value
	if not value:
		return value
	if len(value) <= 8:
		return "***"
	return value[:2] + "***" + value[-2:]

def kvfmt(**kwargs) -> str:
	parts = []
	for k, v in kwargs.items():
		if k.lower() in _REDACT_KEYS:
			v = redact(str(v))
		# squash whitespace
		sv = str(v).replace("\n", " ").replace("\r", " ")
		parts.append(f"{k}={sv}")
	return " ".join(parts)

def _write_file(level: str, msg: str):
	ts = time.strftime("%Y-%m-%dT%H:%M:%S")
	line = f"event=log time={ts} level={level} {msg}\n"
	try:
		path = _logfile_path()
		with open(path, "a", encoding="utf-8") as f:
			f.write(line)
	except Exception:
		pass

def log_info(msg):
	xbmc.log(f"[fav-sync] {msg}", xbmc.LOGINFO)
	_write_file("INFO", msg)

def log_debug(msg):
	xbmc.log(f"[fav-sync] {msg}", xbmc.LOGDEBUG)
	_write_file("DEBUG", msg)

def log_error(msg):
	xbmc.log(f"[fav-sync] {msg}", xbmc.LOGERROR)
	_write_file("ERROR", msg)

