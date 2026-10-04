"""Shared settings and profile-to-driver configuration mapping."""
import copy

BACKENDS = ['webdav', 's3', 'http', 'sftp', 'smb', 'nfs', 'local']
FIELDS = {
    'webdav': ['webdav_url', 'webdav_path', 'webdav_user', 'webdav_password'],
    's3': ['s3_endpoint', 's3_region', 's3_bucket', 's3_key', 's3_access', 's3_secret', 's3_versioning'],
    'http': ['http_get', 'http_put', 'http_auth_header'],
    'sftp': ['sftp_host', 'sftp_port', 'sftp_user', 'sftp_password', 'sftp_keyfile', 'sftp_key_password', 'sftp_path'],
    'smb': ['smb_path', 'smb_user', 'smb_password'],
    'nfs': ['nfs_path'],
    'local': ['local_path'],
}
SECRET_FIELDS = {'password', 'webdav_password', 'sftp_password', 'sftp_key_password',
                 'smb_password', 's3_secret', 'http_auth_header', 'secret_key',
                 'private_key_password', 'access_key', 's3_access'}
ALIASES = {
    'webdav': {'url': 'webdav_url', 'path': 'webdav_path', 'user': 'webdav_user',
               'username': 'webdav_user', 'password': 'webdav_password'},
    's3': {'endpoint': 's3_endpoint', 'region': 's3_region', 'bucket': 's3_bucket',
           'path': 's3_key', 'key': 's3_key', 'access_key': 's3_access', 'secret_key': 's3_secret'},
    'http': {'url': 'http_get', 'password': 'http_auth_header'},
    'sftp': {'host': 'sftp_host', 'port': 'sftp_port', 'username': 'sftp_user',
             'user': 'sftp_user', 'password': 'sftp_password', 'path': 'sftp_path',
             'private_key_path': 'sftp_keyfile', 'private_key_password': 'sftp_key_password'},
    'smb': {'path': 'smb_path', 'user': 'smb_user', 'username': 'smb_user', 'password': 'smb_password'},
    'nfs': {'path': 'nfs_path'},
    'local': {'path': 'local_path'},
}


def profile_driver_config(profile):
    backend = profile.get('backend', '')
    if isinstance(backend, dict):
        config = copy.deepcopy(backend)
        backend = config.pop('type', '')
    else:
        config = copy.deepcopy(profile.get('config', {}))
    for source, dest in ALIASES.get(backend, {}).items():
        if source in config and dest not in config:
            config[dest] = config[source]
    if backend == 'http' and 'url' in config:
        config.setdefault('http_put', config['url'])
    config['backend'] = backend
    config['conflict_policy'] = {'prefer_remote': 'cloud', 'remote_wins': 'cloud',
                                 'prefer_local': 'local', 'local_wins': 'local'}.get(
        profile.get('conflict_policy'), profile.get('conflict_policy', 'merge'))
    return config


def decrypt_driver_config(config, decrypt):
    result = copy.deepcopy(config)
    for key in SECRET_FIELDS:
        value = result.get(key)
        if isinstance(value, str) and value.startswith('ENC:'):
            result[key] = decrypt(value)
    return result
