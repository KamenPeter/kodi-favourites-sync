"""
Context Entry Point - Script invocation for cross-add action.

Provides RunScript() entry point for context menu or action buttons.
"""
import sys

try:
    from resources.lib.ui_cross_add import open_for_current_selection
    from resources.lib.logutil import log_info, log_error, kvfmt
except ImportError:
    from ui_cross_add import open_for_current_selection
    from logutil import log_info, log_error, kvfmt


def main():
    """
    Parse command-line arguments and route to appropriate action.
    
    Usage:
        RunScript(plugin.service.favourites-sync)
        RunScript(plugin.service.favourites-sync, cross_add)
    """
    try:
        # Get action from arguments
        action = "cross_add"  # Default
        if len(sys.argv) > 1:
            action = sys.argv[1].strip()
            if action.startswith('action='):
                action = action.split('=', 1)[1]
        
        log_info(kvfmt(event="context_script_invoked", action=action))
        
        if action in ("cross_add", "cross_add_current"):
            open_for_current_selection()
        else:
            log_error(kvfmt(event="context_script_unknown_action", action=action))
    
    except Exception as e:
        log_error(kvfmt(event="context_script_error", error=str(e)))


if __name__ == "__main__":
    main()
