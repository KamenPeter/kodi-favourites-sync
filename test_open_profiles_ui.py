"""
Quick launcher for Multi-Profile Management UI
Run this to open the Manage Profiles dialog directly
"""
import xbmc

# Launch the Manage Profiles UI
xbmc.executebuiltin('RunScript(special://home/addons/plugin.service.favourites-sync/resources/lib/ui_profiles.py)')
