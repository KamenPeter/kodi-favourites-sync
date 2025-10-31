"""
Multi-profile management for favourites sync.

Provides profile discovery, configuration storage (profiles.json),
credential encryption, and validation helpers.
"""
import os
import json
import hashlib
import base64
import xbmcvfs
from typing import Tuple

try:
    from .logutil import log_info, log_error, kvfmt
except ImportError:
    from logutil import log_info, log_error, kvfmt

# Paths
USERDATA = xbmcvfs.translatePath("special://userdata/")
PROFILES_DIR = os.path.join(USERDATA, "profiles")
ADDON_DATA = xbmcvfs.translatePath("special://profile/addon_data/plugin.service.favourites-sync/")
PROFILES_JSON = os.path.join(ADDON_DATA, "profiles.json")
KEYSTORE_JSON = os.path.join(ADDON_DATA, "keystore.json")


def list_kodi_profiles() -> dict:
    """
    Discover all Kodi profiles.
    
    Returns:
        dict[str, str]: {profile_name: absolute_profile_dir}
        Example: {"M": "/path/to/profiles/M", "M1": "/path/to/profiles/M1"}
    """
    try:
        # Check if profiles directory exists
        if not os.path.exists(PROFILES_DIR):
            log_info(kvfmt(event="profiles_dir_not_found", path=PROFILES_DIR))
            # Return Master profile at minimum
            master_profile_dir = xbmcvfs.translatePath("special://masterprofile/")
            return {"Master": master_profile_dir}
        
        profiles = {}
        for name in os.listdir(PROFILES_DIR):
            profile_dir = os.path.join(PROFILES_DIR, name)
            if os.path.isdir(profile_dir):
                profiles[name] = profile_dir
        
        # Always include Master profile
        master_profile_dir = xbmcvfs.translatePath("special://masterprofile/")
        if "Master" not in profiles:
            profiles["Master"] = master_profile_dir
        
        log_info(kvfmt(event="profiles_discovered", count=len(profiles), names=list(profiles.keys())))
        return profiles
        
    except Exception as e:
        log_error(kvfmt(event="profiles_discovery_error", error=str(e)))
        # Fallback to Master profile
        master_profile_dir = xbmcvfs.translatePath("special://masterprofile/")
        return {"Master": master_profile_dir}


def profile_favourites_path(profile_name: str) -> str:
    """
    Get the path to a specific profile's favourites.xml.
    
    Args:
        profile_name: Name of the profile
        
    Returns:
        str: Absolute path to favourites.xml for that profile
    """
    profiles = list_kodi_profiles()
    if profile_name in profiles:
        return os.path.join(profiles[profile_name], "favourites.xml")
    
    # Fallback: construct path manually
    if profile_name == "Master":
        profile_dir = xbmcvfs.translatePath("special://masterprofile/")
    else:
        profile_dir = os.path.join(PROFILES_DIR, profile_name)
    
    return os.path.join(profile_dir, "favourites.xml")


def _ensure_addon_data():
    """Ensure addon_data directory exists."""
    if not os.path.exists(ADDON_DATA):
        os.makedirs(ADDON_DATA, exist_ok=True)


def load_profiles_cfg() -> dict:
    """
    Load profiles.json configuration.
    
    Returns:
        dict: Configuration with structure:
        {
            "version": 1,
            "profiles": {
                "ProfileName": {
                    "backend": "webdav",
                    "config": {...},
                    "schedule": {...},
                    "conflict_policy": "merge",
                    "cross_add": {...}
                }
            }
        }
    """
    _ensure_addon_data()
    
    try:
        if os.path.exists(PROFILES_JSON):
            with open(PROFILES_JSON, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                log_info(kvfmt(event="profiles_cfg_loaded", profiles=len(cfg.get("profiles", {}))))
                return cfg
    except Exception as e:
        log_error(kvfmt(event="profiles_cfg_load_error", error=str(e)))
    
    # Return default structure
    default_cfg = {
        "version": 1,
        "profiles": {}
    }
    
    # Initialize with discovered profiles (empty configs)
    discovered = list_kodi_profiles()
    for profile_name in discovered.keys():
        default_cfg["profiles"][profile_name] = {
            "backend": "",
            "config": {},
            "schedule": {
                "on_start": False,
                "on_shutdown": False,
                "mode": "bidirectional"
            },
            "conflict_policy": "merge",
            "cross_add": {
                "enabled": False,
                "auto_targets": []
            }
        }
    
    log_info(kvfmt(event="profiles_cfg_initialized", count=len(default_cfg["profiles"])))
    return default_cfg


def save_profiles_cfg(cfg: dict) -> None:
    """
    Atomically save profiles.json configuration.
    
    Args:
        cfg: Configuration dictionary
    """
    _ensure_addon_data()
    
    try:
        tmp_path = PROFILES_JSON + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
        
        # Atomic replace
        if os.path.exists(PROFILES_JSON):
            os.remove(PROFILES_JSON)
        os.rename(tmp_path, PROFILES_JSON)
        
        log_info(kvfmt(event="profiles_cfg_saved", profiles=len(cfg.get("profiles", {}))))
        
    except Exception as e:
        log_error(kvfmt(event="profiles_cfg_save_error", error=str(e)))
        raise


def get_profile_cfg(cfg: dict, profile_name: str) -> dict:
    """
    Get configuration for a specific profile.
    
    Args:
        cfg: Full profiles configuration
        profile_name: Name of profile to retrieve
        
    Returns:
        dict: Profile configuration (empty dict if not found)
    """
    return cfg.get("profiles", {}).get(profile_name, {})


def set_profile_cfg(cfg: dict, profile_name: str, new_cfg: dict) -> dict:
    """
    Update configuration for a specific profile.
    
    Args:
        cfg: Full profiles configuration
        profile_name: Name of profile to update
        new_cfg: New configuration for the profile
        
    Returns:
        dict: Updated configuration
    """
    if "profiles" not in cfg:
        cfg["profiles"] = {}
    
    cfg["profiles"][profile_name] = new_cfg
    log_info(kvfmt(event="profile_cfg_updated", profile=profile_name))
    
    return cfg


# ============================================================================
# Encryption helpers
# ============================================================================

def _get_or_create_keystore() -> dict:
    """
    Get or create keystore with salt for encryption.
    
    Returns:
        dict: {"salt": "<base64-encoded-salt>"}
    """
    _ensure_addon_data()
    
    try:
        if os.path.exists(KEYSTORE_JSON):
            with open(KEYSTORE_JSON, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        log_error(kvfmt(event="keystore_load_error", error=str(e)))
    
    # Create new keystore
    import random
    salt_bytes = bytes([random.randint(0, 255) for _ in range(16)])
    salt_b64 = base64.b64encode(salt_bytes).decode('utf-8')
    
    keystore = {"salt": salt_b64}
    
    try:
        with open(KEYSTORE_JSON, "w", encoding="utf-8") as f:
            json.dump(keystore, f, indent=2)
        log_info(kvfmt(event="keystore_created"))
    except Exception as e:
        log_error(kvfmt(event="keystore_save_error", error=str(e)))
    
    return keystore


def _derive_key() -> bytes:
    """
    Derive encryption key from addon ID, machine ID, and salt.
    
    Returns:
        bytes: 32-byte encryption key
    """
    keystore = _get_or_create_keystore()
    salt = base64.b64decode(keystore["salt"])
    
    # Build key material
    addon_id = "plugin.service.favourites-sync"
    
    # Try to get a machine identifier
    import platform
    machine_id = platform.node() or "unknown"
    
    # Combine and hash
    key_material = f"{addon_id}:{machine_id}".encode('utf-8') + salt
    key = hashlib.sha256(key_material).digest()
    
    return key


def encrypt_secret(plain: str) -> str:
    """
    Encrypt a plaintext secret.
    
    Args:
        plain: Plaintext string to encrypt
        
    Returns:
        str: Encrypted string in format "ENC:<base64>"
    """
    if not plain:
        return ""
    
    try:
        # Try to use cryptography library (Fernet)
        from cryptography.fernet import Fernet
        
        key = _derive_key()
        # Fernet requires base64-encoded 32-byte key
        fernet_key = base64.urlsafe_b64encode(key)
        f = Fernet(fernet_key)
        
        encrypted = f.encrypt(plain.encode('utf-8'))
        return f"ENC:{base64.b64encode(encrypted).decode('utf-8')}"
        
    except ImportError:
        # Fallback: XOR with key + base64 (obfuscation, not strong encryption)
        log_info(kvfmt(event="crypto_fallback", method="xor"))
        key = _derive_key()
        
        plain_bytes = plain.encode('utf-8')
        encrypted_bytes = bytes([plain_bytes[i] ^ key[i % len(key)] for i in range(len(plain_bytes))])
        
        return f"ENC:{base64.b64encode(encrypted_bytes).decode('utf-8')}"
    
    except Exception as e:
        log_error(kvfmt(event="encrypt_error", error=str(e)))
        return plain  # Fallback: return plaintext


def decrypt_secret(maybe_enc: str) -> str:
    """
    Decrypt a secret (or return as-is if not encrypted).
    
    Args:
        maybe_enc: String that may be encrypted ("ENC:<base64>") or plaintext
        
    Returns:
        str: Decrypted plaintext
    """
    if not maybe_enc or not maybe_enc.startswith("ENC:"):
        return maybe_enc
    
    try:
        encrypted_b64 = maybe_enc[4:]  # Remove "ENC:" prefix
        encrypted_bytes = base64.b64decode(encrypted_b64)
        
        # Try cryptography library first
        try:
            from cryptography.fernet import Fernet
            
            key = _derive_key()
            fernet_key = base64.urlsafe_b64encode(key)
            f = Fernet(fernet_key)
            
            decrypted = f.decrypt(encrypted_bytes)
            return decrypted.decode('utf-8')
            
        except ImportError:
            # Fallback: XOR decryption
            key = _derive_key()
            decrypted_bytes = bytes([encrypted_bytes[i] ^ key[i % len(key)] for i in range(len(encrypted_bytes))])
            return decrypted_bytes.decode('utf-8')
        
    except Exception as e:
        log_error(kvfmt(event="decrypt_error", error=str(e)))
        return maybe_enc  # Fallback: return as-is


# ============================================================================
# Validation
# ============================================================================

def validate_profile_endpoint(pcfg: dict) -> Tuple[bool, str]:
    """
    Validate a profile's backend endpoint configuration.
    
    Args:
        pcfg: Profile configuration dict with 'backend' and 'config' keys
        
    Returns:
        Tuple[bool, str]: (success, message)
    """
    try:
        backend = pcfg.get("backend", "")
        if not backend:
            return (False, "No backend configured")
        
        config = pcfg.get("config", {})
        
        # Decrypt password if present
        if "password" in config:
            config["password"] = decrypt_secret(config["password"])
        
        # Import backend factory from sync.py
        try:
            from .sync import _backend_from_settings
        except ImportError:
            from sync import _backend_from_settings
        
        # Build config dict in expected format
        backend_cfg = {"backend": backend}
        backend_cfg.update(config)
        
        # Instantiate driver
        driver = _backend_from_settings(backend_cfg)
        
        # Try to stat
        stat_result = driver.stat()
        
        if stat_result:
            return (True, f"Connected successfully (size: {stat_result.get('size', 0)} bytes)")
        else:
            return (False, "Connection failed")
        
    except Exception as e:
        log_error(kvfmt(event="profile_validation_error", error=str(e)))
        return (False, f"Error: {str(e)}")


# ============================================================================
# UI Helper Functions
# ============================================================================

def get_view_models(cfg: dict) -> list:
    """
    Get view models for displaying profiles in list.
    
    Args:
        cfg: Profiles configuration dict
        
    Returns:
        list: List of (profile_name, status_text) tuples
    """
    profiles = list_kodi_profiles()
    view_models = []
    
    for profile_name in sorted(profiles.keys()):
        pcfg = get_profile_cfg(cfg, profile_name)
        
        if not pcfg or not pcfg.get("backend"):
            status = "Not configured"
        else:
            backend = pcfg.get("backend", "")
            schedule = pcfg.get("schedule", {})
            on_start = "✓" if schedule.get("on_start") else "–"
            on_shutdown = "✓" if schedule.get("on_shutdown") else "–"
            status = f"{backend.upper()} | Start:{on_start} Shutdown:{on_shutdown}"
        
        view_models.append((profile_name, status))
    
    return view_models


def get_endpoint_display(pcfg: dict) -> str:
    """
    Get a displayable endpoint string from profile config.
    
    Args:
        pcfg: Profile configuration dict
        
    Returns:
        str: Display string for endpoint (URL, path, etc.)
    """
    backend = pcfg.get("backend", "")
    config = pcfg.get("config", {})
    
    if backend == "webdav":
        return config.get("webdav_url", "") or "(not set)"
    elif backend == "local":
        return config.get("local_path", "") or "(not set)"
    elif backend == "smb":
        return config.get("smb_path", "") or "(not set)"
    elif backend == "nfs":
        return config.get("nfs_path", "") or "(not set)"
    elif backend == "s3":
        bucket = config.get("s3_bucket", "")
        key = config.get("s3_key", "")
        return f"s3://{bucket}/{key}" if bucket else "(not set)"
    elif backend == "http":
        return config.get("http_get", "") or "(not set)"
    elif backend == "sftp":
        host = config.get("sftp_host", "")
        path = config.get("sftp_path", "")
        return f"sftp://{host}{path}" if host else "(not set)"
    else:
        return "(not configured)"


def new_default_profile(profile_name: str) -> dict:
    """
    Create a new default profile configuration.
    Loads defaults from base addon settings if available.
    
    Args:
        profile_name: Name of the profile
        
    Returns:
        dict: Default profile configuration
    """
    try:
        # Try to load defaults from base settings
        try:
            from . import ui_profiles
            defaults = ui_profiles._load_base_settings_defaults()
            log_info(kvfmt(event="new_profile_defaults_loaded", profile=profile_name))
            return defaults
        except Exception:
            pass
        
        # Fallback to empty defaults
        return {
            "backend": "",
            "config": {},
            "schedule": {
                "on_start": False,
                "on_shutdown": False,
                "mode": "bidirectional"
            },
            "conflict_policy": "merge",
            "cross_add": {
                "enabled": True,
                "auto_targets": []
            }
        }
    except Exception as e:
        log_error(kvfmt(event="new_profile_defaults_error", error=str(e)))
        return {
            "backend": "",
            "config": {},
            "schedule": {"on_start": False, "on_shutdown": False, "mode": "bidirectional"},
            "conflict_policy": "merge",
            "cross_add": {"enabled": True, "auto_targets": []}
        }


def get_profile_names(cfg: dict, exclude: str = None) -> list:
    """
    Get list of all profile names.
    
    Args:
        cfg: Profiles configuration dict
        exclude: Optional profile name to exclude from list
        
    Returns:
        list: List of profile names
    """
    profiles = list_kodi_profiles()
    names = sorted(profiles.keys())
    
    if exclude:
        names = [n for n in names if n != exclude]
    
    return names


def add_empty_profile(cfg: dict, profile_name: str) -> dict:
    """
    Add an empty profile configuration.
    
    Args:
        cfg: Current profiles configuration
        profile_name: Name of new profile
        
    Returns:
        dict: Updated configuration
    """
    if "profiles" not in cfg:
        cfg["profiles"] = {}
    
    cfg["profiles"][profile_name] = new_default_profile(profile_name)
    
    log_info(kvfmt(event="profile_added", profile=profile_name))
    return cfg


def delete_profile(cfg: dict, profile_name: str) -> dict:
    """
    Delete a profile's configuration.
    
    Args:
        cfg: Current profiles configuration
        profile_name: Name of profile to delete
        
    Returns:
        dict: Updated configuration
    """
    if "profiles" in cfg and profile_name in cfg["profiles"]:
        del cfg["profiles"][profile_name]
        log_info(kvfmt(event="profile_deleted", profile=profile_name))
    
    return cfg
