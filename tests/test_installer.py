"""Safety tests use fixtures only; no disk or live system is ever changed."""
import importlib.util
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('installer', Path(__file__).parents[1] / 'installer/install.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class InstallerSafety(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def node(self, **extra):
        return dict(path='/dev/vda', type='disk', size=100 * 1024**3,
                    model='test only', serial='fixture', ro=False, rm=False,
                    tran=None, mountpoints=[], children=[], **extra)

    def test_usb_never_erasable(self):
        d = self.node(); d['tran'] = 'usb'
        self.assertIn('USB', installer.unsafe_device(d))

    def test_mounted_child_excludes_disk(self):
        d = self.node(); d['children'] = [dict(path='/dev/vda1', mountpoints=['/iso'])]
        self.assertIn('mounted', installer.unsafe_device(d))

    def test_swap_excludes_disk(self):
        d = self.node()
        with patch.object(Path, 'read_text', return_value='Filename Type Size Used Priority\n/dev/vda partition 1 0 0\n'):
            self.assertIn('swap', installer.unsafe_device(d))

    def test_regular_rejects_link_ancestor(self):
        (self.root / 'linked').symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError): installer.regular(self.root / 'linked' / 'child')

    def test_regular_rejects_dangling_link(self):
        p = self.root / 'dangling'; p.symlink_to(self.root / 'missing')
        with self.assertRaises(ValueError): installer.regular(p)

    def test_regular_rejects_traversal(self):
        with self.assertRaises(ValueError): installer.regular(self.root / '..' / 'etc')

    def test_regular_accepts_new_owned_path(self):
        self.assertEqual(installer.regular(self.root / 'new'), self.root / 'new')

    def test_source_digest_rejects_link(self):
        (self.root / 'link').symlink_to('/etc/passwd')
        with self.assertRaises(ValueError): installer.digest(self.root)

    def test_digest_changes_on_resource_change(self):
        p = self.root / 'resource'; p.write_text('before')
        before = installer.digest(self.root)[0]; p.write_text('after')
        self.assertNotEqual(before, installer.digest(self.root)[0])

    def test_digest_excludes_only_git_metadata(self):
        git = self.root / '.git'; git.mkdir(); (git / 'config').write_text('metadata')
        before = installer.digest(self.root)[0]; (git / 'config').write_text('changed')
        self.assertEqual(before, installer.digest(self.root)[0])

    def test_wrong_erasure_confirmation_runs_no_commands(self):
        with patch.object(installer, 'TARGET', self.root / 'mnt'), patch.object(installer, 'choose_disk', return_value=self.node()), patch.object(installer, 'device_identity', return_value={'rdev': 123}), patch.object(installer, 'ask', side_effect=['E', 'NO']), patch.object(installer, 'run') as commands:
            with self.assertRaisesRegex(ValueError, 'not confirmed'): installer.prepare_disk('uefi')
            commands.assert_not_called()

    def test_invalid_storage_choice_runs_no_commands(self):
        with patch.object(installer, 'TARGET', self.root / 'mnt'), patch.object(installer, 'choose_disk', return_value=self.node()), patch.object(installer, 'device_identity', return_value={'rdev': 123}), patch.object(installer, 'ask', return_value='unknown'), patch.object(installer, 'run') as commands:
            with self.assertRaises(ValueError): installer.prepare_disk('uefi')
            commands.assert_not_called()

    def test_mounted_mnt_refused_before_erasure(self):
        with patch.object(installer, 'TARGET', self.root / 'mnt'), patch.object(installer, 'choose_disk', return_value=self.node()), patch.object(installer, 'device_identity', return_value={'rdev': 123}), patch.object(installer, 'ask', return_value='E'), patch.object(os.path, 'ismount', return_value=True), patch.object(installer, 'run') as commands:
            with self.assertRaisesRegex(ValueError, 'already mounted'): installer.prepare_disk('uefi')
            commands.assert_not_called()

    def test_disk_identity_change_refused(self):
        with patch.object(installer, 'inventory', return_value=[self.node()]), patch.object(installer, 'device_identity', return_value={'rdev': 2}):
            with self.assertRaisesRegex(ValueError, 'identity changed'): installer.revalidate({'path': '/dev/vda', 'rdev': 1})

    def test_missing_disk_refused(self):
        with patch.object(installer, 'inventory', return_value=[]):
            with self.assertRaises(ValueError): installer.revalidate({'path': '/dev/vda'})

    def test_atomic_receipt_is_private_and_complete(self):
        p = self.root / 'receipt.json'; installer.save_json(p, {'phase': 'built'})
        self.assertEqual(json.loads(p.read_text()), {'phase': 'built'})
        self.assertEqual(stat.S_IMODE(p.stat().st_mode), 0o600)
        self.assertEqual(list(self.root.glob('.vivian-*')), [])

    def test_target_payload_absolute_store_links_resolved_in_target(self):
        target = self.root / 'target'; a = target / 'nix/store/system'; b = target / 'nix/store/kernel'
        a.mkdir(parents=True); b.mkdir(); (b / 'bzImage').write_text('payload')
        (a / 'kernel').symlink_to('/nix/store/kernel/bzImage')
        with patch.object(installer, 'TARGET', target):
            self.assertTrue(installer.target_payload('/nix/store/system', 'kernel'))

    def test_payload_cannot_escape_target_store(self):
        target = self.root / 'target'; a = target / 'nix/store/system'; a.mkdir(parents=True)
        (a / 'kernel').symlink_to('/etc/passwd')
        with patch.object(installer, 'TARGET', target):
            with self.assertRaises(ValueError): installer.target_payload('/nix/store/system', 'kernel')

    def test_existing_source_never_overwritten(self):
        target = self.root / 'target'; p = target / 'etc/nixos'; p.mkdir(parents=True); (p / 'user-work').write_text('KEEP')
        with patch.object(installer, 'TARGET', target):
            with self.assertRaisesRegex(ValueError, 'preserved'): installer.prepare_source(self.root, 'rev', 'uefi', '/dev/vda')
        self.assertEqual((p / 'user-work').read_text(), 'KEEP')


if __name__ == '__main__':
    unittest.main()
