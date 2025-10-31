"""
Favourites reordering logic - groups and sorts addon shortcuts
"""
import json
import os
import threading
import time
from datetime import datetime
from typing import List, Dict, Any
import xbmcvfs
import xbmc

try:
    from .xmlio import FavEntry, parse_favourites_xml, serialize_favourites, normalize_title
    from .settings_mgr import misc_add_to_fav, misc_keep_first, misc_group_addons_top, misc_sort_addons
    from .logutil import log_info, log_error, kvfmt
except ImportError:
    from xmlio import FavEntry, parse_favourites_xml, serialize_favourites, normalize_title
    from settings_mgr import misc_add_to_fav, misc_keep_first, misc_group_addons_top, misc_sort_addons
    from logutil import log_info, log_error, kvfmt


ADDON_ID = "plugin.service.favourites-sync"
SELF_ACTIONS = [
    f'RunAddon("{ADDON_ID}")',
    f'RunScript(special://home/addons/{ADDON_ID}/resources/lib/addon.py)'
]

def refresh_kodi_profile(
    set_reload_flag: bool = True,
    delay_skin_reload: bool = False,
    focus_favourites: bool = False
) -> bool:
    """
    Refresh Kodi profile to reload favourites.xml and other profile data.
    
    Args:
        set_reload_flag: If True, sets flag to prevent startup sync after reload
        delay_skin_reload: If True, delays skin reload to allow dialogs to close first
        focus_favourites: If True, opens Favourites window after reload
        
    Returns:
        True if reload was successful, False otherwise
    """
    try:
        # Set flag to prevent startup sync from running after reload
        if set_reload_flag:
            try:
                from service import _set_reload_flag
                _set_reload_flag()
            except Exception:
                try:
                    from .service import _set_reload_flag
                    _set_reload_flag()
                except Exception as e:
                    log_error(kvfmt(event="reload_flag_failed", error=str(e)))
        
        log_info("Refreshing Kodi profile...")
        
        if delay_skin_reload:
            # Delayed approach: Let settings/addon dialogs close before forcing a refresh
            def delayed_reload():
                monitor = xbmc.Monitor()
                wait_until = time.time() + 5.0
                try:
                    log_info(kvfmt(event="delayed_reload_waiting"))
                    while time.time() < wait_until and not monitor.abortRequested():
                        if not (
                            xbmc.getCondVisibility("Window.IsActive(settings)") or
                            xbmc.getCondVisibility("Window.IsActive(addonsettings)")
                        ):
                            break
                        monitor.waitForAbort(0.2)
                    
                    # Check if we should abort before continuing
                    if monitor.abortRequested():
                        log_info(kvfmt(event="delayed_reload_aborted"))
                        return
                    
                    xbmc.sleep(200)  # Extra grace period after dialog closes
                    
                    log_info(kvfmt(event="delayed_reload_starting"))
                    
                    # Use LoadProfile with actual profile name - the ONLY reliable way
                    current_profile = xbmc.getInfoLabel('System.ProfileName')
                    log_info(kvfmt(event="current_profile", profile=current_profile))
                    xbmc.executebuiltin(f'LoadProfile({current_profile})')
                    log_info(kvfmt(event="profile_reloaded", profile=current_profile))
                    
                    xbmc.sleep(300)  # Wait for profile reload (reduced from 500ms)
                    
                    if focus_favourites and not monitor.abortRequested():
                        xbmc.sleep(100)
                        # Use window ID 10134 (Favourites window) instead of name
                        xbmc.executebuiltin("ActivateWindow(10134)")
                        xbmc.sleep(100)
                        xbmc.executebuiltin("Container.Refresh")
                        log_info(kvfmt(event="favourites_window_refreshed"))
                except SystemExit:
                    # Python is shutting down, exit gracefully
                    log_info(kvfmt(event="delayed_reload_system_exit"))
                except Exception as thread_error:
                    log_error(kvfmt(event="delayed_reload_failed", error=str(thread_error)))
            
            thread = threading.Thread(target=delayed_reload, name="fav-sync-delayed-reload", daemon=True)
            thread.start()
            log_info(kvfmt(event="delayed_reload_scheduled"))
        else:
            # Immediate approach: Use LoadProfile with actual profile name
            current_profile = xbmc.getInfoLabel('System.ProfileName')
            log_info(kvfmt(event="current_profile", profile=current_profile))
            xbmc.executebuiltin(f'LoadProfile({current_profile})')
            log_info(kvfmt(event="profile_reloaded", profile=current_profile))
            xbmc.sleep(500)
            
            if focus_favourites:
                # Use window ID 10134 (Favourites window) instead of name
                xbmc.executebuiltin("ActivateWindow(10134)")
                xbmc.sleep(200)
                xbmc.executebuiltin("Container.Refresh")
                log_info(kvfmt(event="favourites_window_refreshed"))
            
            if focus_favourites:
                xbmc.executebuiltin("ActivateWindow(favourites)")
                xbmc.sleep(200)
                xbmc.executebuiltin("Container.Refresh")
                log_info(kvfmt(event="favourites_window_refreshed"))
        
        log_info("Profile refresh completed")
        return True
        
    except Exception as e:
        log_error(kvfmt(event="profile_refresh_failed", error=str(e)))
        try:
            # Fallback to container refresh only
            xbmc.executebuiltin("Container.Refresh")
            log_info(kvfmt(event="container_refreshed_fallback"))
            return True
        except Exception as e2:
            log_error(kvfmt(event="container_refresh_failed", error=str(e2)))
            return False


def _get_favourites_path() -> str:
    """Get path to favourites.xml in current profile"""
    profile_path = xbmcvfs.translatePath("special://profile")
    return os.path.join(profile_path, "favourites.xml")


def _get_addon_data_path() -> str:
    """Get path to addon_data directory for storing config"""
    addon_data = xbmcvfs.translatePath(f"special://profile/addon_data/{ADDON_ID}")
    if not os.path.exists(addon_data):
        os.makedirs(addon_data)
    return addon_data


def _get_order_file_path() -> str:
    """Get path to manual order JSON file"""
    return os.path.join(_get_addon_data_path(), "favourites_order.json")


def load_addon_order() -> List[str]:
    """Load manual addon order from JSON file"""
    order_file = _get_order_file_path()
    if not os.path.exists(order_file):
        return []
    
    try:
        with open(order_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return [item.get("k", "") for item in data.get("addon_order", [])]
    except Exception as e:
        log_error(kvfmt(event="load_order_failed", error=str(e)))
        return []


def save_addon_order(keys: List[str]) -> None:
    """Save manual addon order to JSON file"""
    order_file = _get_order_file_path()
    
    try:
        data = {
            "addon_order": [{"k": k} for k in keys],
            "version": 1
        }
        with open(order_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        log_info(kvfmt(event="save_order_success", count=len(keys)))
    except Exception as e:
        log_error(kvfmt(event="save_order_failed", error=str(e)))


def entry_key(entry: FavEntry) -> str:
    """Generate compound key for an entry (action + name for uniqueness)"""
    # Use both action and name to handle duplicate actions with different names
    return f"{entry.action}||{entry.name}"


def apply_manual_order(addons: List[FavEntry], keys: List[str]) -> List[FavEntry]:
    """Apply manual order to addon list"""
    if not keys:
        return addons
    
    index = {k: i for i, k in enumerate(keys)}
    known = [e for e in addons if entry_key(e) in index]
    unknown = [e for e in addons if entry_key(e) not in index]
    
    # Sort known by manual order
    known.sort(key=lambda e: index[entry_key(e)])
    
    # Append unknown at end
    return known + unknown


def ensure_self_shortcut(entries: List[FavEntry]) -> bool:
    """Add self shortcut if missing. Returns True if added."""
    # Check if self shortcut already exists
    for e in entries:
        if e.action in SELF_ACTIONS:
            return False
    
    # Add self shortcut at beginning
    self_entry = FavEntry(
        name="Favourites Sync (Cloud)",
        action=SELF_ACTIONS[1],  # Prefer RunAddon form
        thumb="special://home/addons/plugin.service.favourites-sync/icon.png",
        type="addon"
    )
    entries.insert(0, self_entry)
    log_info(kvfmt(event="self_shortcut_added"))
    return True


def remove_self_shortcuts(entries: List[FavEntry]) -> bool:
    """Remove all self shortcuts. Returns True if any were removed."""
    removed_count = 0
    entries_to_remove = []
    
    for e in entries:
        if e.action in SELF_ACTIONS:
            entries_to_remove.append(e)
            removed_count += 1
    
    for e in entries_to_remove:
        entries.remove(e)
    
    if removed_count > 0:
        log_info(kvfmt(event="self_shortcuts_removed", count=removed_count))
        return True
    return False


def move_self_first(entries: List[FavEntry]) -> bool:
    """Move self shortcut to first position. Returns True if moved."""
    for i, e in enumerate(entries):
        if e.action in SELF_ACTIONS:
            if i != 0:
                entries.insert(0, entries.pop(i))
                log_info(kvfmt(event="self_moved_first", from_index=i))
                return True
            break
    return False


def write_atomic_with_backup(xml_bytes: bytes, dest: str) -> None:
    """Write favourites.xml atomically with backup"""
    # Create backup if file exists
    if os.path.exists(dest):
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_name = f"favourites_{timestamp}.xml.bak"
        backup_path = dest.replace("favourites.xml", backup_name)
        
        try:
            # Read existing file and write to backup
            with open(dest, 'rb') as f:
                backup_data = f.read()
            with open(backup_path, 'wb') as f:
                f.write(backup_data)
            log_info(kvfmt(event="backup_created", path=backup_name))
        except Exception as e:
            log_error(kvfmt(event="backup_failed", error=str(e)))
    
    # Write to temp file first
    tmp_path = dest + ".tmp"
    try:
        with open(tmp_path, 'wb') as f:
            f.write(xml_bytes)
        
        # Atomic rename
        if os.path.exists(dest):
            os.remove(dest)
        os.rename(tmp_path, dest)
        
        log_info(kvfmt(event="write_success", path=dest))
    except Exception as e:
        log_error(kvfmt(event="write_failed", error=str(e)))
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def reload_favourites(manual_context: bool = False, skip_reload: bool = False):
    """Reload Kodi favourites to show changes immediately"""
    if skip_reload:
        return
    
    if not manual_context:
        log_info(kvfmt(event="skip_reload", reason="non_manual_context"))
        return
    
    # Use delayed reload for manual context to allow settings dialog to close first
    refresh_kodi_profile(set_reload_flag=True, delay_skin_reload=True, focus_favourites=True)


def reorder_favourites(manual_context: bool = False, skip_profile_reload: bool = False) -> Dict[str, Any]:
    """
    Apply grouping/sorting rules + ensure-self/keep-first.
    Returns summary: {'addons': N, 'others': M, 'changed': bool}
    """
    fav_path = _get_favourites_path()
    
    # Load current favourites
    try:
        if not os.path.exists(fav_path):
            log_info(kvfmt(event="no_favourites_file"))
            xml_bytes = b""
            entries = []
            original_count = 0
        else:
            with open(fav_path, 'rb') as f:
                xml_bytes = f.read()
            
            entries = parse_favourites_xml(xml_bytes)
            original_count = len(entries)
        
    except Exception as e:
        log_error(kvfmt(event="parse_failed", error=str(e)))
        return {'addons': 0, 'others': 0, 'changed': False, 'error': str(e)}
    
    # Track if anything changed
    changed = False
    
    # Get settings
    add_to_fav = misc_add_to_fav()
    keep_first = misc_keep_first()
    group_top = misc_group_addons_top()
    sort_mode = misc_sort_addons()
    
    log_info(kvfmt(event="reorder_start", manual=manual_context, add_to_fav=add_to_fav,
                   keep_first=keep_first, group_top=group_top, sort=sort_mode,
                   entries=len(entries)))
    
    # Handle add/remove self shortcut
    if add_to_fav:
        if ensure_self_shortcut(entries):
            changed = True
    else:
        if remove_self_shortcuts(entries):
            changed = True
    
    # Classify all entries
    addons = [e for e in entries if e.type == "addon"]
    others = [e for e in entries if e.type != "addon"]
    
    log_info(kvfmt(event="classified", addons=len(addons), others=len(others)))
    
    # Sort addons according to sort mode
    if sort_mode == "az":
        sorted_addons = sorted(addons, key=lambda e: normalize_title(e.name))
        if sorted_addons != addons:
            addons = sorted_addons
            changed = True
            log_info(kvfmt(event="sorted", mode="az"))
    elif sort_mode == "za":
        sorted_addons = sorted(addons, key=lambda e: normalize_title(e.name), reverse=True)
        if sorted_addons != addons:
            addons = sorted_addons
            changed = True
            log_info(kvfmt(event="sorted", mode="za"))
    elif sort_mode == "manual":
        order = load_addon_order()
        if order:
            sorted_addons = apply_manual_order(addons, order)
            if sorted_addons != addons:
                addons = sorted_addons
                changed = True
                log_info(kvfmt(event="sorted", mode="manual", order_count=len(order)))
    
    # Reconstruct list based on grouping setting
    if group_top:
        # Group all addons at top, others below
        final_entries = addons + others
        log_info(kvfmt(event="grouped", mode="top"))
    else:
        # In-place reorder: maintain original positions for non-addons,
        # but apply addon sort order
        final_entries = []
        addon_idx = 0
        other_idx = 0
        
        # Preserve original structure but with reordered addons
        for entry in entries:
            if entry.type == "addon":
                if addon_idx < len(addons):
                    final_entries.append(addons[addon_idx])
                    addon_idx += 1
            else:
                if other_idx < len(others):
                    final_entries.append(others[other_idx])
                    other_idx += 1
        
        # Add any remaining entries
        while addon_idx < len(addons):
            final_entries.append(addons[addon_idx])
            addon_idx += 1
        while other_idx < len(others):
            final_entries.append(others[other_idx])
            other_idx += 1
        
        log_info(kvfmt(event="reordered", mode="in_place"))
    
    # Move self to first if enabled
    if keep_first and add_to_fav:
        if move_self_first(final_entries):
            changed = True
    
    # Always write if entries were modified OR if content differs
    if changed or len(final_entries) != original_count:
        changed = True
    
    if not changed:
        # Final check: compare serialized form
        original_xml = xml_bytes
        new_xml = serialize_favourites(final_entries)
        if original_xml != new_xml:
            changed = True
    
    # Write if changed
    if changed:
        try:
            new_xml = serialize_favourites(final_entries)
            log_info(kvfmt(event="writing_favourites", entries=len(final_entries), 
                          addons=len(addons), others=len(others), changed=True))
            
            write_atomic_with_backup(new_xml, fav_path)
            
            log_info(kvfmt(event="reorder_complete", addons=len(addons), 
                          others=len(others), changed=True))
            
            # Reload favourites to show changes
            reload_favourites(manual_context=manual_context, skip_reload=skip_profile_reload)
            
        except Exception as e:
            log_error(kvfmt(event="reorder_failed", error=str(e)))
            return {'addons': len(addons), 'others': len(others), 
                   'changed': False, 'error': str(e)}
    else:
        log_info(kvfmt(event="reorder_complete", addons=len(addons), 
                      others=len(others), changed=False, reason="no_changes"))
    
    return {
        'addons': len(addons),
        'others': len(others),
        'changed': changed
    }
