#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Launcher add-on exposed to Kodi's Programs UI.
It loads the shared Favourites Sync menu from the service add-on.
"""
import os
import sys

import xbmcaddon
import xbmcgui
import xbmcvfs

SERVICE_ID = "plugin.service.favourites-sync"


def _notify_error(message: str) -> None:
    xbmcgui.Dialog().ok("Favourites Sync", message)


def main() -> None:
    try:
        service_addon = xbmcaddon.Addon(SERVICE_ID)
    except Exception as exc:  # Kodi raises RuntimeError when addon is missing
        _notify_error(f"Required add-on missing:\n{SERVICE_ID}\n\n{exc}")
        return

    service_path = xbmcvfs.translatePath(service_addon.getAddonInfo("path"))
    lib_path = os.path.join(service_path, "resources", "lib")
    if lib_path not in sys.path:
        sys.path.insert(0, lib_path)

    try:
        from addon import main as addon_main  # type: ignore import-not-found
    except Exception as exc:
        _notify_error(f"Unable to load Favourites Sync UI:\n{exc}")
        return

    addon_main()


if __name__ == "__main__":
    main()

