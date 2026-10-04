"""Offline regression tests. Kodi APIs are stubbed; filesystem operations are real."""
import copy
import base64
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch, Mock

sys.dont_write_bytecode = True
LIB = Path(__file__).resolve().parents[1] / 'addon' / 'resources' / 'lib'
sys.path.insert(0, str(LIB))
BOOT = tempfile.TemporaryDirectory()


class Addon:
    settings = {}

    def __init__(self, *args):
        pass

    def getSetting(self, key):
        return self.settings.get(key, '')

    def getSettingBool(self, key):
        return self.getSetting(key) == 'true'

    def getAddonInfo(self, key):
        return {'id': 'plugin.service.favourites-sync', 'profile': BOOT.name,
                'name': 'Favourites Sync', 'path': str(LIB.parents[1])}.get(key, '')

    def setSetting(self, key, value):
        self.settings[key] = value


class Dialog:
    def notification(self, *args):
        pass


sys.modules['xbmc'] = types.SimpleNamespace(Monitor=object, sleep=lambda n: None,
    getInfoLabel=lambda key: '', executebuiltin=lambda cmd: None)
sys.modules['xbmcaddon'] = types.SimpleNamespace(Addon=Addon)
sys.modules['xbmcvfs'] = types.SimpleNamespace(translatePath=lambda path: BOOT.name + '/', exists=os.path.exists)
sys.modules['xbmcgui'] = types.SimpleNamespace(Dialog=Dialog, WindowXMLDialog=object,
    NOTIFICATION_INFO=0, NOTIFICATION_WARNING=1, NOTIFICATION_ERROR=2)
sys.modules['logutil'] = types.SimpleNamespace(log_info=lambda *a: None,
    log_error=lambda *a: None, log_debug=lambda *a: None, kvfmt=lambda **kw: str(kw))

import storage
import sync
import xmlio
import profiles_mgr
import backend_config
import service
import settings_mgr
import reorder
import ui_cross_add
import ui_profiles
import context_cross_add
from drivers.local import Driver


def favourites(*labels):
    return xmlio.serialize([xmlio.Favourite(label, 'PlayMedia("' + label + '")', {}) for label in labels])


class Backend:
    def __init__(self, data):
        self.data = data
        self.fail = False

    def stat(self):
        return {'etag': 'old', 'modified_at': '2000-01-01T00:00:00Z'}

    def download(self):
        return self.data

    def upload(self, data, metadata):
        if self.fail:
            raise IOError('connection refused')
        self.data = data

    def copy_backup(self, *args):
        pass


class RegressionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.local = self.root / 'favourites.xml'
        self.data = self.root / 'state'
        self.backend = Backend(favourites('A'))
        Addon.settings = {}
        for target, replacement in [
            ('sync._backend_from_settings', lambda cfg: self.backend),
            ('sync._apply_reordering', lambda items: xmlio.serialize(items)),
        ]:
            patcher = patch(target, replacement)
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_sync(self, mode='bidirectional', **kwargs):
        return sync._run(mode, config={'backend': 'local', 'conflict_policy': 'merge',
                         'local_backups': False}, local_path=str(self.local),
                         data_dir=str(self.data), skip_profile_reload=True, **kwargs)

    def labels(self, data):
        return [item.label for item in xmlio.load_xml(data)]

    def test_failed_upload_preserves_baseline_and_retries_additions(self):
        self.local.write_bytes(favourites('A'))
        self.assertEqual(self.run_sync()['result'], 'success')
        baseline = (self.data / 'base_snapshot.xml').read_bytes()
        self.local.write_bytes(favourites('A', 'B'))
        self.backend.fail = True
        result = self.run_sync()
        self.assertEqual(result['result'], 'partial_success')
        self.assertIsNotNone(result['error'])
        self.assertEqual((self.data / 'base_snapshot.xml').read_bytes(), baseline)
        self.backend.fail = False
        self.assertEqual(self.run_sync()['result'], 'success')
        self.assertEqual(self.labels(self.backend.data), ['A', 'B'])

    def test_preview_and_download_failure_preserve_deletions(self):
        self.local.write_bytes(favourites('A', 'B'))
        self.backend.data = self.local.read_bytes()
        self.run_sync()
        history = json.loads((self.data / 'status.json').read_text())['last_synced_items']
        self.local.write_bytes(favourites('A'))
        self.assertEqual(self.run_sync('dryrun')['result'], 'dryrun')
        self.assertEqual(json.loads((self.data / 'status.json').read_text())['last_synced_items'], history)
        with patch.object(self.backend, 'download', side_effect=IOError('offline')):
            self.assertEqual(self.run_sync()['result'], 'cloud_unavailable')
        self.run_sync()
        self.assertEqual(self.labels(self.backend.data), ['A'])

    def test_empty_baseline_commits_and_new_addition_survives(self):
        self.local.write_bytes(favourites('A'))
        self.run_sync()
        self.local.write_bytes(favourites())
        self.run_sync()
        self.assertEqual(self.labels((self.data / 'base_snapshot.xml').read_bytes()), [])
        self.local.write_bytes(favourites('A'))
        self.run_sync()
        self.assertEqual(self.labels(self.backend.data), ['A'])

    def test_legacy_status_baseline_survives_preview(self):
        self.data.mkdir()
        self.local.write_bytes(favourites('A'))
        old = {'last_synced_items': [{'label': 'A', 'path': 'PlayMedia("A")', 'attrib': {}}]}
        (self.data / 'status.json').write_text(json.dumps(old))
        self.run_sync('dryrun')
        self.assertEqual(sync._load_last_synced_items(str(self.data / 'status.json'),
                         str(self.data / 'missing.xml'))[0].label, 'A')

    def test_profile_sync_uses_target_backend_and_separate_state(self):
        profiles = {}
        cfg = {'profiles': {}}
        for name in ('M', 'T'):
            directory = self.root / name
            directory.mkdir()
            remote = self.root / (name + '-remote.xml')
            remote.write_bytes(favourites(name))
            profiles[name] = str(directory)
            cfg['profiles'][name] = {'backend': 'local', 'config': {'local_path': str(remote)}}
        # Replace the setUp backend mock with the production driver factory.
        real_factory = RegressionTests.real_factory
        with patch.object(profiles_mgr, 'list_kodi_profiles', return_value=profiles), \
             patch.object(profiles_mgr, 'load_profiles_cfg', return_value=cfg), \
             patch.object(sync, '_backend_from_settings', real_factory):
            original_local = sync.LOCAL_FAV
            for name in profiles:
                self.assertEqual(sync.run_sync_for_profile(name, 'pull')['result'], 'success')
                directory = Path(profiles[name])
                self.assertEqual(self.labels((directory / 'favourites.xml').read_bytes()), [name])
                self.assertTrue((directory / 'addon_data/plugin.service.favourites-sync/profile_sync/base_snapshot.xml').exists())
            self.assertEqual(sync.LOCAL_FAV, original_local)

    def test_atomic_replace_failure_keeps_original_and_cleans_temp(self):
        self.local.write_bytes(b'original')
        with patch.object(storage.os, 'replace', side_effect=OSError('replace failed')):
            with self.assertRaises(OSError):
                Driver({'local_path': str(self.local)}).upload(b'new')
        self.assertEqual(self.local.read_bytes(), b'original')
        self.assertEqual(list(self.root.glob('.favourites.xml.*')), [])

    def test_concurrent_lock_blocks_and_releases(self):
        with storage.file_lock(str(self.local) + '.lock'):
            with self.assertRaises(OSError):
                with storage.file_lock(str(self.local) + '.lock'):
                    pass
            self.assertEqual(self.run_sync()['result'], 'error')
        self.assertEqual(self.run_sync()['result'], 'success')

    def test_profile_save_failure_keeps_previous_configuration(self):
        path = self.root / 'profiles.json'
        previous = b'{"profiles": {}}'
        path.write_bytes(previous)
        with patch.multiple(profiles_mgr, ADDON_DATA=str(self.root), PROFILES_JSON=str(path)), \
             patch.object(storage.os, 'replace', side_effect=OSError('replace failed')):
            with self.assertRaises(OSError):
                profiles_mgr.save_profiles_cfg({'profiles': {'M': {'backend': 'local', 'config': {}}}})
        self.assertEqual(path.read_bytes(), previous)

    def test_profile_append_uses_shared_lock_and_normalized_duplicates(self):
        self.local.write_bytes(favourites('Movie'))
        with patch.object(profiles_mgr, 'profile_favourites_path', return_value=str(self.local)):
            with storage.file_lock(str(self.local) + '.lock'):
                self.assertFalse(xmlio.append_favourite_to_profile('M', 'Other', 'action'))
            self.assertTrue(xmlio.append_favourite_to_profile('M', '[B]MOVIE[/B]', 'PlayMedia("Movie")'))
            self.assertEqual(self.labels(self.local.read_bytes()), ['Movie'])
            self.assertTrue(xmlio.append_favourite_to_profile('M', 'Other', 'action'))
            self.assertEqual(self.labels(self.local.read_bytes()), ['Movie', 'Other'])

    def test_encryption_failure_does_not_return_plaintext(self):
        with patch.object(profiles_mgr, '_derive_key', side_effect=OSError('keystore unavailable')):
            with self.assertRaises((ValueError, OSError)):
                profiles_mgr.encrypt_secret('plain')

    def test_global_and_profile_state_are_distinct_for_active_profile(self):
        self.local.write_bytes(favourites('A'))
        self.run_sync()
        baseline = (self.data / 'base_snapshot.xml').read_bytes()
        remote = self.root / 'remote.xml'
        remote.write_bytes(favourites('T'))
        cfg = {'profiles': {'M': {'backend': 'local', 'config': {'local_path': str(remote)}}}}
        with patch.object(profiles_mgr, 'list_kodi_profiles', return_value={'M': str(self.root)}), \
             patch.object(profiles_mgr, 'load_profiles_cfg', return_value=cfg), \
             patch.object(sync, '_backend_from_settings', RegressionTests.real_factory):
            self.assertEqual(sync.run_sync_for_profile('M', 'pull')['result'], 'success')
        self.assertEqual((self.data / 'base_snapshot.xml').read_bytes(), baseline)

    def test_local_read_failure_aborts_without_upload(self):
        self.local.write_bytes(favourites('A'))
        with patch.object(sync, '_xbmcvfs_read', side_effect=PermissionError('denied')), \
             patch.object(self.backend, 'upload') as upload:
            self.assertEqual(self.run_sync()['result'], 'error')
            upload.assert_not_called()

    def test_all_backend_settings_are_collected(self):
        for backend, fields in backend_config.FIELDS.items():
            Addon.settings = {'backend': str(backend_config.BACKENDS.index(backend))}
            Addon.settings.update({key: 'configured' for key in fields})
            result = sync._settings_dict()
            for key in fields:
                self.assertEqual(result[key], 'configured', (backend, key))

    def test_real_http_and_webdav_factories_receive_credentials(self):
        with patch.object(profiles_mgr, 'decrypt_secret', return_value='plain'):
            profile = {'backend': 'webdav', 'config': {'webdav_url': 'https://example.test',
                       'webdav_user': 'user', 'password': 'ENC:X:placeholder'}}
            driver = RegressionTests.real_factory(backend_config.profile_driver_config(profile))
            self.assertEqual(driver.password, 'plain')
            self.assertEqual(profile['config']['password'], 'ENC:X:placeholder')
            Addon.settings = {'backend': '2', 'http_get': 'https://example.test/f.xml',
                              'http_put': 'https://example.test/f.xml', 'http_auth_header': 'ENC:X:placeholder'}
            driver = RegressionTests.real_factory(sync._settings_dict())
            self.assertEqual(driver._headers()['Authorization'], 'Bearer plain')

    def test_legacy_xor_credential_remains_readable(self):
        key = bytes(range(32))
        secret = b'legacy-secret'
        payload = base64.b64encode(bytes(value ^ key[i % len(key)]
                                        for i, value in enumerate(secret))).decode()
        with patch.object(profiles_mgr, '_derive_key', return_value=key):
            self.assertEqual(profiles_mgr.decrypt_secret('ENC:' + payload), secret.decode())
            self.assertEqual(profiles_mgr.decrypt_secret('ENC:X:' + payload), secret.decode())

    def test_python_sources_compile_and_addon_xml_parses(self):
        import xml.etree.ElementTree as ET
        root = LIB.parents[2]
        for directory in ('addon', 'runner', 'tools'):
            for path in (root / directory).rglob('*.py'):
                compile(path.read_bytes(), str(path), 'exec')
        for path in (root / 'addon').rglob('*.xml'):
            ET.parse(path)

    def test_validation_does_not_mutate_and_decrypts_driver_fields(self):
        pcfg = {'backend': 'webdav', 'config': {'webdav_url': 'https://example.test',
                'webdav_user': 'user', 'password': 'ENC:X:placeholder'}}
        before = copy.deepcopy(pcfg)
        capture = []
        def factory(config):
            capture.append(backend_config.decrypt_driver_config(config, lambda value: 'plain'))
            return self.backend
        with patch.object(sync, '_backend_from_settings', factory):
            self.assertTrue(profiles_mgr.validate_profile_endpoint(pcfg)[0])
        self.assertEqual(pcfg, before)
        self.assertEqual(capture[0]['webdav_password'], 'plain')
        result = backend_config.decrypt_driver_config({'s3_secret': 'ENC:x',
                 'http_auth_header': 'ENC:y'}, lambda v: 'decrypted')
        self.assertEqual(result, {'s3_secret': 'decrypted', 'http_auth_header': 'decrypted'})

    def test_credentials_round_trip_and_save_encrypted(self):
        with patch.multiple(profiles_mgr, ADDON_DATA=str(self.root),
                PROFILES_JSON=str(self.root / 'profiles.json'), KEYSTORE_JSON=str(self.root / 'keystore.json')):
            encoded = profiles_mgr.encrypt_secret('secret')
            self.assertTrue(encoded.startswith('ENC:'))
            self.assertEqual(profiles_mgr.decrypt_secret(encoded), 'secret')
            cfg = {'profiles': {'M': {'backend': 'local', 'config': {'password': 'plain'}}}}
            profiles_mgr.save_profiles_cfg(cfg)
            saved = json.loads((self.root / 'profiles.json').read_text())
            self.assertTrue(saved['profiles']['M']['config']['password'].startswith('ENC:'))
            self.assertEqual(cfg['profiles']['M']['config']['password'], 'plain')
            with self.assertRaises(ValueError):
                profiles_mgr.decrypt_secret('ENC:F:invalid')

    def test_merge_preserves_order_and_uses_actual_remote_time(self):
        local = xmlio.load_xml(favourites('B', 'A', 'C'))
        merged, _ = xmlio.merge_sets(local, local, local)
        self.assertEqual([item.label for item in merged], ['B', 'A', 'C'])
        local[0].attrib = {'thumb': 'local'}
        remote = xmlio.load_xml(favourites('B', 'A', 'C'))
        remote[0].attrib = {'thumb': 'remote'}
        merged, _ = xmlio.merge_sets(local, remote, prefer='newer', local_mtime=2000000000,
                                     remote_mtime=sync._remote_mtime(self.backend.stat()))
        self.assertEqual(merged[0].attrib['thumb'], 'local')
        self.assertGreater(sync._remote_mtime({'modified_at': 'Wed, 21 Oct 2015 07:28:00 GMT'}), 0)
        self.assertEqual(sync._remote_mtime({}), 0)

    def test_profile_schedule_independent_of_global_schedule(self):
        cfg = types.SimpleNamespace(enabled=False, on_startup=False, on_shutdown=False)
        profiles = {'M': {'schedule': {'on_start': True, 'on_shutdown': True, 'mode': 'push'}}}
        with patch.object(profiles_mgr, 'load_profiles_cfg', return_value={'profiles': profiles}), \
             patch.object(sync, 'run_sync_for_profile', return_value={'result': 'success'}) as run, \
             patch.object(service, 'is_endpoint_valid', return_value=False):
            service._run_scheduled_event('on_start', cfg)
            service._run_scheduled_event('on_shutdown', cfg)
        self.assertEqual(run.call_count, 2)
        run.assert_called_with('M', 'push', skip_profile_reload=True)

    def test_first_settings_change_applies_reorder(self):
        settings_mgr._ADDON = Addon()
        with patch.object(settings_mgr, 'misc_add_to_fav', return_value=False):
            monitor = service._Monitor()
        with patch.object(settings_mgr, 'misc_add_to_fav', return_value=True), \
             patch.object(reorder, 'reorder_favourites', return_value={'changed': False}) as run:
            monitor.onSettingsChanged()
            run.assert_called_once()

    def test_documented_cross_add_action_and_filtered_defaults(self):
        with patch.object(context_cross_add, 'open_for_current_selection') as opened, \
             patch.object(sys, 'argv', ['script', 'action=cross_add_current']):
            context_cross_add.main()
            opened.assert_called_once()
        cfg = {'profiles': {'A': {'cross_add': {'enabled': False}},
               'M': {'cross_add': {'enabled': False, 'auto_targets': ['T']}},
               'T': {'cross_add': {'enabled': True}}, 'Z': {'cross_add': {'enabled': True}}}}
        dialog = Mock()
        dialog.multiselect.return_value = None
        labels = {'System.ProfileName': 'M', 'ListItem.Label': 'Movie', 'ListItem.FolderPath': 'movie.mkv'}
        with patch.object(profiles_mgr, 'load_profiles_cfg', return_value=cfg), \
             patch.object(ui_cross_add.xbmc, 'getInfoLabel', side_effect=lambda key: labels.get(key, '')), \
             patch.object(ui_cross_add.xbmcgui, 'Dialog', return_value=dialog):
            ui_cross_add.open_for_current_selection()
        self.assertEqual(dialog.multiselect.call_args.args[1], ['T', 'Z'])
        self.assertEqual(dialog.multiselect.call_args.kwargs['preselect'], [0])

    def test_active_editor_saves_default_targets(self):
        dialog = Mock()
        dialog.select.side_effect = [11, 13]
        dialog.multiselect.return_value = [1]
        pcfg = {'backend': 'local', 'config': {'local_path': 'file.xml'},
                'schedule': {}, 'conflict_policy': 'merge', 'cross_add': {'auto_targets': ['T']}}
        with patch.object(ui_profiles.xbmcgui, 'Dialog', return_value=dialog), \
             patch.object(profiles_mgr, 'get_profile_names', return_value=['T', 'Z']):
            result = ui_profiles._edit_profile_dialog('M', pcfg)
        self.assertEqual(result['cross_add']['auto_targets'], ['Z'])
        self.assertEqual(pcfg['cross_add']['auto_targets'], ['T'])


RegressionTests.real_factory = staticmethod(sync._backend_from_settings)

if __name__ == '__main__':
    unittest.main()
