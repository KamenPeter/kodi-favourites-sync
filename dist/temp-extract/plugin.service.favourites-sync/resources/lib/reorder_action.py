"""
Action script for 'Reorder favourites now' button
"""
import xbmcgui

try:
    from reorder import reorder_favourites
    from logutil import log_info, kvfmt
except ImportError:
    import sys
    import os
    addon_lib = os.path.join(os.path.dirname(__file__))
    if addon_lib not in sys.path:
        sys.path.insert(0, addon_lib)
    from reorder import reorder_favourites
    from logutil import log_info, kvfmt


if __name__ == "__main__":
    log_info(kvfmt(event="reorder_action_triggered", context="settings_button"))
    
    result = reorder_favourites(manual_context=True, skip_profile_reload=False)
    
    dialog = xbmcgui.Dialog()
    
    if result.get('error'):
        dialog.notification("[fav-sync]", 
                          f"Reorder failed: {result['error']}",
                          xbmcgui.NOTIFICATION_ERROR,
                          5000)
    elif result.get('changed'):
        dialog.notification("[fav-sync]", 
                          f"Favourites reordered: {result['addons']} addons, {result['others']} others",
                          xbmcgui.NOTIFICATION_INFO,
                          3000)
    else:
        dialog.notification("[fav-sync]", 
                          "No changes needed - favourites already in correct order",
                          xbmcgui.NOTIFICATION_INFO,
                          2000)
