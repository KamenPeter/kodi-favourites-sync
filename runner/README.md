# Favourites Sync Launcher

This add-on exposes the Favourites Sync menu under **Programs → Add-ons** and enables the **Run** button in the Kodi UI. It requires the core service add-on `plugin.service.favourites-sync`, which continues to handle background synchronisation.

## Behaviour

- The launcher delegates execution to `resources/lib/addon.py` from the service package.
- If the service add-on is missing or fails to load, the user sees an on-screen error dialog.
- Version numbers track the service release to keep dependency ranges aligned.

## Packaging

This folder is packaged separately from the service add-on. See `tools/build.py` for the build process that generates both ZIPs.

