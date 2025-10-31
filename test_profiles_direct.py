"""
Direct test of profiles UI - bypasses settings action
Copy this to Kodi addons folder and run
"""
import sys
import os

# Add addon lib to path
addon_path = os.path.join(os.path.dirname(__file__), 'addon', 'resources', 'lib')
sys.path.insert(0, addon_path)

# Import and run
try:
    import ui_profiles
    print("Opening profiles dialog...")
    ui_profiles.open_dialog()
    print("Dialog closed")
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
