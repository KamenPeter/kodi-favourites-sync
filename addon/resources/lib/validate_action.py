"""Called when user clicks 'Validate endpoint' button in settings"""
import sys
import os
import xbmcgui
import xbmcaddon

# Set the addon ID for proper context
ADDON_ID = "plugin.service.favourites-sync"

# Add the lib directory to path
lib_path = os.path.dirname(os.path.abspath(__file__))
if lib_path not in sys.path:
    sys.path.insert(0, lib_path)

def main():
    # Initialize addon with explicit ID
    addon = xbmcaddon.Addon(ADDON_ID)
    dialog = xbmcgui.Dialog()
    
    try:
        # Import after addon is initialized
        from sync import validate_endpoint
        
        result = validate_endpoint()
        if result.get("ok"):
            dialog.notification("Favourites Sync", "Endpoint validated successfully!", xbmcgui.NOTIFICATION_INFO, 3000)
        else:
            dialog.ok("Validation Failed", f"Error: {result.get('error', 'Unknown error')}")
    except Exception as e:
        dialog.ok("Error", f"Validation script error:\n{str(e)}")

if __name__ == "__main__":
    main()
