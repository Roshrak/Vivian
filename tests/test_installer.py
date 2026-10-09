"""Safety tests use fixtures only; no disk or live system is ever changed."""
import importlib.util
import fcntl
import json
import os
import pty
import select
import signal
import subprocess
import sys
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

    def test_other_os_root_is_preserved(self):
        root=self.root/'target'; (root/'etc').mkdir(parents=True)
        (root/'etc/passwd').write_text('OTHER OS USER DATA')
        with patch.object(installer,'TARGET',root):
            with self.assertRaisesRegex(ValueError,'operating-system root preserved'):installer.protect_existing_os()
        self.assertEqual((root/'etc/passwd').read_text(),'OTHER OS USER DATA')

    def test_empty_prepartitioned_root_is_supported(self):
        with patch.object(installer,'TARGET',self.root):installer.protect_existing_os()

    def test_nix_signal_crash_retries_only_same_safe_command(self):
        args=['nix','build','fixture'];failure=subprocess.CalledProcessError(-signal.SIGBUS,args)
        with patch.object(installer,'run',side_effect=[failure,'/nix/store/result']) as commands:
            self.assertEqual(installer.run_nix(args,True,{'HOME':'fixture'}),'/nix/store/result')
            self.assertEqual(commands.call_args_list[0],commands.call_args_list[1])
            self.assertEqual(commands.call_count,2)

    def test_repeated_signal_crash_stops_after_one_retry(self):
        args=['nix','eval','fixture'];failure=subprocess.CalledProcessError(-signal.SIGBUS,args)
        with patch.object(installer,'run',side_effect=failure) as commands:
            with self.assertRaises(subprocess.CalledProcessError):installer.run_nix(args)
            self.assertEqual(commands.call_count,2)

    def test_ordinary_build_failure_is_not_hidden_or_retried(self):
        args=['nix','build','fixture']
        with patch.object(installer,'run',side_effect=subprocess.CalledProcessError(1,args)) as commands:
            with self.assertRaises(subprocess.CalledProcessError):installer.run_nix(args)
            self.assertEqual(commands.call_count,1)

    def test_crash_recovery_cannot_retry_deletion_or_activation(self):
        with patch.object(installer,'run') as commands:
            with self.assertRaises(ValueError):installer.run_nix(['nix','store','delete','fixture'])
            commands.assert_not_called()

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

    def test_bios_without_stable_identity_is_refused_before_formatting(self):
        with patch.object(installer, 'choose_disk', return_value=self.node()), patch.object(installer, 'device_identity', return_value={'rdev': 123}), patch.object(Path, 'glob', return_value=[]), patch.object(installer, 'run') as commands:
            with self.assertRaisesRegex(ValueError, 'stable disk ID'): installer.prepare_disk('bios')
            commands.assert_not_called()

    def test_resume_before_receipt_derives_mounted_disk_without_formatting(self):
        d = self.node(); d['children'] = [{'path': '/dev/vda2'}]
        with patch.object(installer, 'inventory', return_value=[d]):
            self.assertEqual(installer.mounted_boot_disk({'root': {'source': '/dev/vda2'}}, 'uefi'), '/dev/vda')

    def test_unknown_mounted_disk_is_not_guessed(self):
        with patch.object(installer, 'inventory', return_value=[self.node()]):
            with self.assertRaisesRegex(ValueError, 'Cannot identify'): installer.mounted_boot_disk({'root': {'source': '/dev/unknown'}}, 'uefi')

    def test_existing_partition_mode_never_formats(self):
        with patch.object(installer, 'TARGET', self.root / 'mnt'), patch.object(installer, 'choose_disk', return_value=self.node()), patch.object(installer, 'device_identity', return_value={'rdev': 123}), patch.object(installer, 'ask', return_value='M'), patch.object(installer, 'choose_partition', side_effect=[{'path': '/dev/vda2'}, {'path': '/dev/vda1'}]), patch.object(installer, 'revalidate'), patch.object(installer, 'run') as commands:
            installer.prepare_disk('uefi')
            self.assertEqual([call.args[0][0] for call in commands.call_args_list], ['mount', 'mount'])

    def test_nix_home_uses_disk_and_trusts_only_installed_checkout(self):
        env = installer.nix_environment(self.root)
        home = Path(env['HOME'])
        self.assertEqual(home.parent, self.root)
        self.assertEqual(Path(env['XDG_CACHE_HOME']).parent, home)
        self.assertEqual((home / '.gitconfig').read_text(), '[safe]\n\tdirectory = /mnt/etc/nixos\n')
        self.assertEqual(stat.S_IMODE(home.stat().st_mode), 0o700)
        self.assertEqual(installer.nix_environment(self.root)['HOME'], env['HOME'])

    def test_changed_git_trust_file_is_preserved(self):
        env = installer.nix_environment(self.root); config = Path(env['HOME']) / '.gitconfig'
        config.write_text('[safe]\n\tdirectory = /other/user/work\n')
        with self.assertRaisesRegex(ValueError, 'changed'): installer.nix_environment(self.root)
        self.assertIn('/other/user/work', config.read_text())

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

    def test_udev_settles_only_after_disk_lock_is_released(self):
        disk = self.root / 'fixture-disk'; disk.write_bytes(b'fixture')
        Path(str(disk) + '1').touch(); Path(str(disk) + '2').touch()
        d = self.node(); d['path'] = str(disk)
        locked = [False]
        def flock(_fd, operation):
            locked[0] = operation != fcntl.LOCK_UN
        def command(args, capture=False):
            if args[0] == 'udevadm': self.assertFalse(locked[0], 'Udev blocked behind installer disk lock')
        with patch.object(installer, 'TARGET', self.root / 'mnt'), patch.object(installer, 'choose_disk', return_value=d), patch.object(installer, 'device_identity', return_value={'rdev': 0}), patch.object(installer, 'ask', side_effect=['E', 'ERASE ' + str(disk)]), patch.object(installer, 'run', side_effect=command), patch.object(installer, 'revalidate'), patch.object(installer.fcntl, 'flock', side_effect=flock):
            installer.prepare_disk('uefi')

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

    def test_reserved_service_identity_stops_before_source_changes(self):
        with patch.object(installer, 'TARGET', self.root / 'target'), patch.object(installer, 'ask', side_effect=['fresh-host', 'nixbld1']), patch.object(installer, 'run') as commands:
            with self.assertRaisesRegex(ValueError, 'reserved'): installer.prepare_source(self.root, 'rev', 'uefi', '/dev/vda')
            commands.assert_not_called()
        self.assertFalse((self.root / 'target/etc/nixos').exists())

    def staged(self):
        target = self.root / 'target'; staged = target / 'etc/.vivian-source-fixture/tree'
        staged.mkdir(parents=True, mode=0o755); staged.parent.chmod(0o700)
        (staged / 'flake.nix').write_text('fixture source')
        return target, staged, {'phase': 'prepared', 'staging_source': str(staged),
                                'installed_source_sha256': installer.digest(staged)[0]}

    def test_checkpointed_source_recovers_interrupted_rename(self):
        target, staged, receipt = self.staged()
        with patch.object(installer, 'TARGET', target): installer.recover_prepared_source(receipt)
        self.assertFalse(staged.exists())
        self.assertEqual((target / 'etc/nixos/flake.nix').read_text(), 'fixture source')

    def test_changed_pending_source_is_preserved(self):
        target, staged, receipt = self.staged(); (staged / 'user-work').write_text('KEEP')
        with patch.object(installer, 'TARGET', target):
            with self.assertRaisesRegex(ValueError, 'changed'): installer.recover_prepared_source(receipt)
        self.assertEqual((staged / 'user-work').read_text(), 'KEEP')
        self.assertFalse((target / 'etc/nixos').exists())

    def test_pending_receipt_cannot_move_other_directory(self):
        target, staged, receipt = self.staged(); receipt['staging_source'] = str(self.root)
        with patch.object(installer, 'TARGET', target):
            with self.assertRaisesRegex(ValueError, 'Invalid'): installer.recover_prepared_source(receipt)
        self.assertTrue(staged.exists())

    def test_existing_changed_source_is_never_replaced_by_checkpoint(self):
        target, staged, receipt = self.staged(); current = target / 'etc/nixos'; current.mkdir()
        (current / 'user-work').write_text('KEEP')
        with patch.object(installer, 'TARGET', target):
            with self.assertRaisesRegex(ValueError, 'changed'): installer.recover_prepared_source(receipt)
        self.assertEqual((current / 'user-work').read_text(), 'KEEP')
        self.assertTrue(staged.exists())

    def test_prompt_works_on_real_nonseekable_controlling_terminal(self):
        pid, fd = pty.fork()
        if pid == 0:
            code = 'import importlib.util; s=importlib.util.spec_from_file_location("i",' + repr(str(Path(installer.__file__))) + '); i=importlib.util.module_from_spec(s); s.loader.exec_module(i); print("ANSWER="+i.ask("Pick"))'
            os.execl(sys.executable, sys.executable, '-c', code)
        data = b''
        try:
            ready, _, _ = select.select([fd], [], [], 5)
            self.assertTrue(ready, 'Prompt did not appear')
            data += os.read(fd, 4096)
            self.assertIn(b'Pick:', data)
            os.write(fd, b'fixture\n')
            while select.select([fd], [], [], 5)[0]:
                try:
                    chunk = os.read(fd, 4096)
                except OSError:
                    break
                if not chunk: break
                data += chunk
            _, status = os.waitpid(pid, 0)
            self.assertEqual(os.waitstatus_to_exitcode(status), 0, data.decode(errors='replace'))
            self.assertIn(b'ANSWER=fixture', data)
        finally:
            os.close(fd)


if __name__ == '__main__':
    unittest.main()
