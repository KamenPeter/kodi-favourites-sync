"""
Manual order editor UI for addon shortcuts
"""
import xbmcgui
import xbmc

try:
    from .reorder import load_addon_order, save_addon_order, entry_key, reorder_favourites, _get_favourites_path
    from .xmlio import parse_favourites_xml
    from .logutil import log_info, kvfmt
except ImportError:
    from reorder import load_addon_order, save_addon_order, entry_key, reorder_favourites, _get_favourites_path
    from xmlio import parse_favourites_xml
    from logutil import log_info, kvfmt


class ManualOrderDialog(xbmcgui.WindowXMLDialog):
    """Dialog for manually ordering addon shortcuts"""
    
    def __init__(self, *args, **kwargs):
        self.addon_entries = kwargs.pop('addon_entries', [])
        self.current_order = []
        super(ManualOrderDialog, self).__init__(*args, **kwargs)
    
    def onInit(self):
        """Initialize the dialog"""
        pass
    
    def onClick(self, controlId):
        """Handle button clicks"""
        pass
    
    def onAction(self, action):
        """Handle actions"""
        if action.getId() in (xbmcgui.ACTION_NAV_BACK, xbmcgui.ACTION_PREVIOUS_MENU):
            self.close()


def show_manual_order_editor():
    """Show simple text-based manual order editor using select dialogs"""
    import os
    
    # Load current favourites
    fav_path = _get_favourites_path()
    if not os.path.exists(fav_path):
        xbmcgui.Dialog().ok("Manual Order Editor", 
                           "No favourites.xml found in profile.")
        return
    
    try:
        with open(fav_path, 'rb') as f:
            xml_bytes = f.read()
        entries = parse_favourites_xml(xml_bytes)
    except Exception as e:
        xbmcgui.Dialog().ok("Error", f"Failed to parse favourites.xml:\n{str(e)}")
        return
    
    # Filter to addon-type entries only
    addon_entries = [e for e in entries if e.type == "addon"]
    
    if not addon_entries:
        xbmcgui.Dialog().ok("Manual Order Editor", 
                           "No addon shortcuts found in favourites.")
        return
    
    # Load existing manual order
    current_order = load_addon_order()
    
    # Build working list - start with current order, append new items
    if current_order:
        ordered_keys = []
        key_to_entry = {entry_key(e): e for e in addon_entries}
        
        # Add known items in order
        for k in current_order:
            if k in key_to_entry:
                ordered_keys.append(k)
        
        # Add new items not in order
        for e in addon_entries:
            k = entry_key(e)
            if k not in ordered_keys:
                ordered_keys.append(k)
        
        # Rebuild entries list in order
        working_entries = []
        for k in ordered_keys:
            if k in key_to_entry:
                working_entries.append(key_to_entry[k])
    else:
        working_entries = addon_entries[:]
    
    # Main edit loop
    while True:
        # Build display list
        display_items = []
        for i, e in enumerate(working_entries):
            display_items.append(f"{i+1}. {e.name}")
        
        # Show selection dialog
        dialog = xbmcgui.Dialog()
        selected = dialog.select("Manual Order Editor - Select item to move", 
                                display_items,
                                useDetails=False)
        
        if selected < 0:
            # User cancelled
            break
        
        # Show move options
        move_options = ["Move Up", "Move Down", "Move to Top", "Move to Bottom", 
                       "---", "Save Order", "Cancel"]
        
        action = dialog.select(f"Move: {working_entries[selected].name}", 
                              move_options)
        
        if action < 0 or action == 6:  # Cancel
            continue
        elif action == 0:  # Move Up
            if selected > 0:
                working_entries[selected], working_entries[selected-1] = \
                    working_entries[selected-1], working_entries[selected]
        elif action == 1:  # Move Down
            if selected < len(working_entries) - 1:
                working_entries[selected], working_entries[selected+1] = \
                    working_entries[selected+1], working_entries[selected]
        elif action == 2:  # Move to Top
            item = working_entries.pop(selected)
            working_entries.insert(0, item)
        elif action == 3:  # Move to Bottom
            item = working_entries.pop(selected)
            working_entries.append(item)
        elif action == 5:  # Save Order
            # Save the order
            keys = [entry_key(e) for e in working_entries]
            save_addon_order(keys)
            
            log_info(kvfmt(event="manual_order_saved", count=len(keys)))
            
            # Ask if user wants to apply now
            apply_now = dialog.yesno("Apply Order", 
                                    "Order saved successfully!\n\n" +
                                    "Apply this order to favourites now?")
            
            if apply_now:
                result = reorder_favourites(manual_context=True)
                if result.get('changed'):
                    dialog.ok("Success", 
                             f"Favourites reordered:\n" +
                             f"Addons: {result['addons']}\n" +
                             f"Others: {result['others']}")
                else:
                    dialog.ok("Info", "No changes were needed.")
            
            break


if __name__ == "__main__":
    show_manual_order_editor()
