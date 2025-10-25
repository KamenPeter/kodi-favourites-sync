#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script entry point for the RUN button
When user clicks RUN in addon info, this script is executed
It simply launches the main addon menu
"""
import xbmc
import xbmcaddon

# Get addon ID
ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')

# Launch the main addon
xbmc.executebuiltin('RunAddon({})'.format(ADDON_ID))
