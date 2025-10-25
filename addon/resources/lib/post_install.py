"""Post-install script that runs after addon installation"""
import xbmcgui
import xbmcaddon

def main():
    addon = xbmcaddon.Addon()
    dialog = xbmcgui.Dialog()
    
    # Show welcome message and offer to configure
    if dialog.yesno(
        addon.getAddonInfo("name"),
        "Thank you for installing Favourites Sync!\n\nWould you like to configure your cloud storage connection now?",
        nolabel="Later",
        yeslabel="Configure Now"
    ):
        # Open settings to cloud category
        addon.openSettings()

if __name__ == "__main__":
    main()
