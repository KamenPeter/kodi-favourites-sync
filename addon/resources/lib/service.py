import xbmc, xbmcaddon
try:
    from .logutil import log_info, log_error, kvfmt
except Exception:
    from logutil import log_info, log_error, kvfmt
try:
    from .settings_mgr import is_endpoint_valid, schedule_config
except Exception:
    from settings_mgr import is_endpoint_valid, schedule_config
try:
    from .sync import run_scheduled_once, validate_endpoint
except Exception:
    from sync import run_scheduled_once, validate_endpoint
try:
    from . import rpc
except Exception:
    import rpc

def run():
    monitor = _Monitor()
    # Try start JSON-RPC server (localhost-only)
    try:
        rpc.start_server()
    except Exception as e:
        log_error(kvfmt(event="rpc_start_failed", error=str(e)))

    cfg = schedule_config()
    log_info(kvfmt(event="service_start", mode=cfg.mode, enabled=cfg.enabled))
    while not monitor.abortRequested():
        cfg = schedule_config()
        if not cfg.enabled:
            if monitor.waitForAbort(5):
                break
            continue
        if not is_endpoint_valid():
            log_info("Service: endpoint not validated; waiting…")
            if monitor.waitForAbort(10):
                break
            continue
        run_scheduled_once(cfg, monitor)
    log_info("Service stopped")


class _Monitor(xbmc.Monitor):
    def onSettingsChanged(self):
        # Attempt auto-validate on any settings change
        res = validate_endpoint()
        if not res.get("ok"):
            log_error(kvfmt(event="auto_validate_failed", error=res.get("error")))
        else:
            log_info(kvfmt(event="auto_validate_ok"))

if __name__ == "__main__":
    run()
