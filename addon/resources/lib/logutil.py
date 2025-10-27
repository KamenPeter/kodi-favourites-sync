import os
import time
import datetime
import glob
import xbmc
import xbmcaddon

# Try to initialize addon, but provide fallback for scripts run outside normal context
try:
	_ADDON = xbmcaddon.Addon()
	_ADDON_ID = _ADDON.getAddonInfo('id')
except RuntimeError:
	# Fallback when script is run without proper addon context
	try:
		_ADDON = xbmcaddon.Addon("plugin.service.favourites-sync")
		_ADDON_ID = _ADDON.getAddonInfo('id')
	except Exception:
		_ADDON = None
		_ADDON_ID = "plugin.service.favourites-sync"

def _logfile_base_path():
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
	return base

def _logfile_path():
	return os.path.join(_logfile_base_path(), "log.txt")

def _rotate_logs():
	"""
	Rotate logs daily. Current log is log.txt, old logs are log_YYYY_MM_DD.txt
	Keeps only the configured number of log files.
	"""
	try:
		base_path = _logfile_base_path()
		current_log = _logfile_path()
		
		# Check if current log exists and get its modification date
		if not os.path.exists(current_log):
			return  # No log to rotate
		
		# Get the modification time of the current log
		mtime = os.path.getmtime(current_log)
		log_date = datetime.datetime.fromtimestamp(mtime).date()
		today = datetime.date.today()
		
		# If log is from today, no rotation needed
		if log_date >= today:
			return
		
		# Rotate: rename log.txt to log_YYYY_MM_DD.txt
		old_log_name = f"log_{log_date.strftime('%Y_%m_%d')}.txt"
		old_log_path = os.path.join(base_path, old_log_name)
		
		# If the dated log already exists, append to it instead of replacing
		if os.path.exists(old_log_path):
			# Merge current log into existing dated log
			try:
				with open(current_log, "r", encoding="utf-8") as src:
					content = src.read()
				with open(old_log_path, "a", encoding="utf-8") as dst:
					dst.write(content)
				# Remove current log after merging
				os.remove(current_log)
			except Exception:
				pass
		else:
			# Simply rename
			try:
				os.rename(current_log, old_log_path)
			except Exception:
				pass
		
		# Clean up old logs based on retention setting
		try:
			if _ADDON:
				retention_days = int(_ADDON.getSetting("log_retention_days") or "7")
			else:
				retention_days = 7
			
			# Get all dated log files
			log_pattern = os.path.join(base_path, "log_*.txt")
			log_files = glob.glob(log_pattern)
			
			# Sort by modification time (oldest first)
			log_files.sort(key=lambda x: os.path.getmtime(x))
			
			# Keep only the most recent retention_days files
			if len(log_files) > retention_days:
				files_to_delete = log_files[:len(log_files) - retention_days]
				for old_file in files_to_delete:
					try:
						os.remove(old_file)
					except Exception:
						pass
		except Exception:
			pass
			
	except Exception:
		pass  # Silently fail rotation, don't break logging

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
	# Rotate logs if needed (checks if current log is from a previous day)
	_rotate_logs()
	
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

