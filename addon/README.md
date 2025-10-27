# Kodi Favourites Sync (Cloud)

Addon ID: `plugin.service.favourites-sync`  
Version: 1.0.46

**Sync your Kodi favorites across multiple devices using cloud storage.**

This addon automatically synchronizes your Kodi favorites (favourites.xml) to a cloud location, allowing you to maintain consistent favorites across all your Kodi installations. Whether you use WebDAV, local network storage, or cloud services like S3, your favorites stay in sync.

## Features

### Sync Modes
- **Pull (Cloud→Local)**: Download favorites from cloud to your device
- **Push (Local→Cloud)**: Upload your favorites to the cloud
- **Bidirectional**: Three-way merge that intelligently combines changes from both sides

### Scheduling Options
- **On startup only**: Sync when Kodi starts (configurable delay: 2-40 seconds)
- **On shutdown only**: Sync when Kodi closes
- **On startup and shutdown**: Sync at both times for maximum consistency

### Supported Storage Backends
- ✅ **WebDAV** - HTTPS with ETag support and atomic operations
- ✅ **Local Path** - Direct file system access
- ✅ **HTTP(S)** - Generic GET/PUT with Bearer or Basic authentication
- ✅ **SMB/NAS** - Windows network shares (UNC paths: `\\server\share\path`)
- ✅ **NFS** - Mounted NFS shares (Unix/Linux)
- ⚙️ **S3** - AWS S3, MinIO, Wasabi, DigitalOcean Spaces (requires `pip install boto3`)
- ⚙️ **SFTP** - SSH file transfer (requires `pip install paramiko`)

### Conflict Resolution
- **Prefer Cloud**: Cloud version wins conflicts
- **Prefer Local**: Local version wins conflicts
- **Bidirectional Merge**: Intelligent three-way merge with last-synced tracking
- **Manual Review**: Pause and notify on conflicts (for manual resolution)

### Smart Features
- **Three-way merge**: Tracks last synced state to detect additions, changes, and deletions on both sides
- **Optimized profile reload**: Only reloads Kodi when favorites actually change
- **Local backups**: Automatic backup rotation (configurable 1-20 backups)
- **ETag support**: Prevents concurrent modification issues (WebDAV, HTTP, S3)
- **Atomic writes**: Uses temp files to prevent corruption
- **Profile variable support**: `{profile}` in paths for multi-profile setups

## Installation

1. Download `plugin.service.favourites-sync-X.X.XX.zip` from releases
2. In Kodi: **Settings** → **Add-ons** → **Install from zip file**
3. Select the downloaded zip file
4. Configure cloud location in addon settings
5. Click **Validate endpoint** to test connection
6. Enable automatic sync and choose your schedule mode

## Configuration

### Cloud Location (Required)
1. Choose your backend type (WebDAV, Local, HTTP, S3, SFTP, SMB, NFS)
2. Enter connection details (URL, credentials, path)
3. Use `{profile}` in paths for multi-profile support
4. Click **Validate endpoint** to verify

### Scheduling
- Enable automatic sync
- Choose when to sync (startup, shutdown, or both)
- Set startup delay (default: 5 seconds, range: 2-40 seconds)
- Select default sync mode (Pull, Push, or Bidirectional)

### Advanced Options
- Conflict resolution policy
- Local backup settings
- Network timeout and retry settings
- Logging levels (Info, Debug)

## How It Works

1. **Startup Sync**: After Kodi starts (with configurable delay), addon pulls/pushes/merges favorites
2. **Shutdown Sync**: When Kodi closes, addon syncs any changes made during session
3. **Three-Way Merge**: Tracks last synced state to intelligently detect:
   - Items added on either side
   - Items removed on either side
   - Items modified on either side
   - Conflicts (same item changed differently on both sides)
4. **Profile Reload**: Uses `LoadProfile()` to refresh favorites in Kodi UI (only when changes occur)

## Development

### Structure
- **Entry point**: `resources/lib/addon.py` (GUI actions)
- **Service**: `resources/lib/service.py` (background sync)
- **Sync logic**: `resources/lib/sync.py` (merge algorithms)
- **Backend drivers**: `resources/lib/drivers/*.py`
- **Settings**: `resources/settings.xml`
- **Localization**: `resources/language/*/strings.po`

### Key Components
- `sync.py`: Main sync orchestration and three-way merge
- `xmlio.py`: Parse and serialize favourites.xml
- `rpc.py`: JSON-RPC server for manual sync triggers
- `settings_mgr.py`: Settings access and validation
- `drivers/`: Backend-specific implementations

## Troubleshooting

### Favorites not syncing
1. Check `log.txt` in addon data directory
2. Verify endpoint validation passes
3. Check startup delay setting (may need to wait 2-40 seconds after Kodi starts)
4. Ensure sync is enabled in settings

### Conflicts
- Review conflict policy in settings
- Check logs for detailed conflict information
- Use Manual Review mode to handle conflicts yourself

### Network issues
- Increase timeout in Advanced settings
- Check network connectivity and credentials
- Review network logs (enable in Logging settings)

## Credits

Developed for Kodi Matrix (19) through Omega (21)  
Supports Python 3.x addon infrastructure
