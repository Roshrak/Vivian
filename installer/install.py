#!/usr/bin/env python3
"""Vivian: install the exact launching flake from a standard NixOS installer.

Destructive operations require a real controlling terminal and explicit disk
identity confirmation. This program refuses to run on an installed NixOS host.
"""
from __future__ import annotations
import argparse
import fcntl
import hashlib
import json
import os
import platform
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

MIN_DISK = 80 * 1024**3
TARGET = Path('/mnt')
ROOT_TYPES = {'ext4', 'btrfs', 'xfs'}
EFI_TYPE = 'c12a7328-f81f-11d2-ba4b-00a0c93ec93b'
BIOS_TYPE = '21686148-6449-6e6f-744e-656564454649'
NIX_FLAGS = ['--extra-experimental-features', 'nix-command flakes',
             '--accept-flake-config']


def run(args, capture=False):
    args = list(map(str, args))
    print('[RUN] ' + shlex.join(args), flush=True)
    p = subprocess.run(args, check=True, text=True,
                       stdout=subprocess.PIPE if capture else None)
    return p.stdout.strip() if capture else None


def ask(prompt, default=None):
    # BufferedRandom (r+) requires seekability, which a real terminal lacks.
    # Separate text readers/writers work on the actual ISO and SSH ptys.
    with open('/dev/tty', 'r') as reader, open('/dev/tty', 'w') as writer:
        writer.write(prompt + (f' [{default}]' if default is not None else '') + ': ')
        writer.flush()
        answer = reader.readline()
    if not answer:
        raise ValueError('Terminal closed; no action confirmed.')
    return answer.strip() or default


def require_installer():
    fields = dict(line.split('=', 1) for line in Path('/etc/os-release').read_text().splitlines() if '=' in line)
    if fields.get('ID', '').strip('"') != 'nixos' or fields.get('VARIANT_ID', '').strip('"') != 'installer':
        raise ValueError('Run Vivian from the official NixOS installation ISO, not the installed laptop.')
    if os.geteuid() != 0 or platform.machine() != 'x86_64':
        raise ValueError('Run using sudo on an x86_64 NixOS installer.')
    mounts = json.loads(run(['findmnt', '-J', '-o', 'TARGET,FSTYPE'], True))['filesystems']
    if not any(p.get('fstype') in {'iso9660', 'squashfs'} for p in flatten(mounts)):
        raise ValueError('No live installer medium detected.')


def flatten(nodes):
    for n in nodes:
        yield n
        yield from flatten(n.get('children', []))


def inventory():
    return json.loads(run(['lsblk', '--tree', '-J', '-b', '-p', '-o',
        'PATH,TYPE,SIZE,MODEL,SERIAL,WWN,RO,RM,TRAN,MAJ:MIN,MOUNTPOINTS,FSTYPE,PARTTYPE,UUID'], True))['blockdevices']


def unsafe_device(node, allowed_mounts=()):
    if node.get('ro') or node.get('rm') or node.get('tran') == 'usb':
        return 'read-only/removable/USB device'
    swaps = {os.path.realpath(l.split()[0]) for l in Path('/proc/swaps').read_text().splitlines()[1:]}
    for p in flatten([node]):
        if any(m and m not in allowed_mounts for m in p.get('mountpoints', [])):
            return 'mounted device (including live media)'
        if os.path.realpath(p['path']) in swaps:
            return 'active swap'
        holders = Path('/sys/class/block') / Path(p['path']).name / 'holders'
        if holders.is_dir() and any(holders.iterdir()):
            return 'device-mapper/RAID holder'
    return None


def device_identity(node):
    st = os.stat(node['path'])
    if not stat.S_ISBLK(st.st_mode):
        raise ValueError('Target is not a block device.')
    return {k: node.get(k) for k in ('path', 'size', 'serial', 'wwn', 'maj:min')} | {'rdev': st.st_rdev}


def revalidate(expected, allowed_mounts=()):
    matches = [p for p in flatten(inventory()) if p['path'] == expected['path']]
    if len(matches) != 1 or device_identity(matches[0]) != expected:
        raise ValueError('Disk identity changed; refusing to continue.')
    reason = unsafe_device(matches[0], allowed_mounts)
    if reason:
        raise ValueError('Unsafe target: ' + reason)


def choose_disk():
    choices = []
    for d in inventory():
        if d['type'] != 'disk':
            continue
        reason = unsafe_device(d)
        if int(d['size']) < MIN_DISK:
            reason = 'less than 80 GiB'
        text = f"{d['path']} | {int(d['size']) / 1024**3:.1f} GiB | {d.get('model') or 'unknown model'} | serial {d.get('serial') or 'unavailable'}"
        if reason:
            print(f'[PROTECTED] {text}: {reason}')
        else:
            choices.append(d)
            print(f'[{len(choices)}] {text}')
    choice = ask('Target disk number')
    if not choice or not choice.isdecimal() or not 1 <= int(choice) <= len(choices):
        raise ValueError('No valid disk selected; all disks preserved.')
    return choices[int(choice) - 1]


def regular(path):
    path = Path(path)
    if not path.is_absolute() or '..' in path.parts:
        raise ValueError('Absolute non-traversing path required.')
    for p in (path, *path.parents):
        if p.is_symlink():
            raise ValueError('Symlink target refused: ' + str(p))
    return path


def mount_state(path):
    rows = json.loads(run(['findmnt', '-J', '-M', str(path), '-o', 'TARGET,SOURCE,FSTYPE,OPTIONS,MAJ:MIN'], True))['filesystems']
    if len(rows) != 1:
        raise ValueError('Expected one distinct mountpoint.')
    return rows[0]


def validate_mounts(mode):
    regular(TARGET)
    root = mount_state(TARGET)
    if root['maj:min'] == mount_state(Path('/'))['maj:min'] or root['fstype'] not in ROOT_TYPES or 'rw' not in root['options'].split(','):
        raise ValueError('Target must be a separate writable Linux filesystem.')
    boot = mount_state(TARGET / 'boot') if mode == 'uefi' else None
    if boot and (boot['fstype'] not in {'vfat', 'fat', 'fat32'} or 'rw' not in boot['options'].split(',') or boot['maj:min'] == root['maj:min']):
        raise ValueError('UEFI requires a separate writable FAT ESP at /mnt/boot.')
    for p in ('etc', 'etc/nixos', 'var', 'var/lib', 'nix', 'nix/store', 'home', 'boot'):
        regular(TARGET / p)
    for p in (TARGET, TARGET / 'etc', TARGET / 'var', TARGET / 'var/lib'):
        if p.exists() and (p.stat().st_uid != 0 or p.stat().st_mode & 0o022):
            raise ValueError('Target system directory is not securely root-owned: ' + str(p))
    return {'root': root, 'boot': boot}


def choose_partition(disk, kind):
    allowed = ROOT_TYPES if kind == 'root' else {'vfat', 'fat', 'fat32'}
    choices = [p for p in flatten(disk.get('children', [])) if p['type'] == 'part' and p.get('fstype') in allowed and not unsafe_device(p)]
    for i, p in enumerate(choices, 1):
        print(f"[{i}] {p['path']} | {p['fstype']} | {int(p['size']) / 1024**3:.1f} GiB")
    answer = ask(f'Existing {kind} partition number (it will NOT be formatted)')
    if not answer or not answer.isdecimal() or not 1 <= int(answer) <= len(choices):
        raise ValueError('No eligible existing partition selected.')
    p = choices[int(answer) - 1]
    if kind == 'boot' and (p.get('parttype') or '').lower() != EFI_TYPE:
        raise ValueError('Selected boot partition is not an EFI System Partition.')
    token = 'USE ' + p['path']
    if ask(f'Type {token} to mount this partition and install onto it') != token:
        raise ValueError('Mount/install not confirmed.')
    return p


def prepare_disk(mode):
    disk = choose_disk()
    expected = device_identity(disk)
    print('E = erase the entire selected disk; M = use existing partitions without formatting.')
    action = ask('Storage method', 'M').upper()
    regular(TARGET).mkdir(exist_ok=True)
    if os.path.ismount(TARGET):
        raise ValueError('/mnt is already mounted: choose Resume instead.')
    if action == 'E':
        print(f"WARNING: ALL partitions and ALL data on {disk['path']} will be erased.")
        token = 'ERASE ' + disk['path']
        if ask(f'Type exactly {token}') != token:
            raise ValueError('Erasure not confirmed; nothing formatted.')
        revalidate(expected)
        # Hold an advisory exclusive lock on the same verified block object.
        # It prevents cooperating tools from racing; it does not claim to stop arbitrary root writers.
        with open(disk['path'], 'rb', buffering=0) as pinned:
            fcntl.flock(pinned.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            if os.fstat(pinned.fileno()).st_rdev != expected['rdev']:
                raise ValueError('Pinned disk identity mismatch.')
            run(['parted', '-s', disk['path'], 'mklabel', 'gpt'])
            if mode == 'uefi':
                run(['parted', '-s', disk['path'], 'mkpart', 'EFI', 'fat32', '1MiB', '1025MiB'])
                run(['parted', '-s', disk['path'], 'set', '1', 'esp', 'on'])
            else:
                run(['parted', '-s', disk['path'], 'mkpart', 'BIOS', '1MiB', '3MiB'])
                run(['parted', '-s', disk['path'], 'set', '1', 'bios_grub', 'on'])
            start = '1025MiB' if mode == 'uefi' else '3MiB'
            run(['parted', '-s', disk['path'], 'mkpart', 'NixOS', 'ext4', start, '100%'])
            run(['udevadm', 'settle'])
            revalidate(expected)
            sep = 'p' if disk['path'][-1].isdigit() else ''
            rootdev, bootdev = disk['path'] + sep + '2', disk['path'] + sep + '1'
            for _ in range(50):
                if Path(rootdev).exists():
                    break
                time.sleep(.1)
            run(['mkfs.ext4', '-L', 'nixos', rootdev])
            if mode == 'uefi':
                run(['mkfs.fat', '-F', '32', '-n', 'EFI', bootdev])
    elif action == 'M':
        rootdev = choose_partition(disk, 'root')['path']
        bootdev = choose_partition(disk, 'boot')['path'] if mode == 'uefi' else None
        if mode == 'bios' and not any((p.get('parttype') or '').lower() == BIOS_TYPE for p in flatten([disk])):
            raise ValueError('Existing BIOS/GPT disk needs a BIOS boot partition; no partitions were modified.')
        revalidate(expected)
    else:
        raise ValueError('Unknown storage method; disk preserved.')
    run(['mount', rootdev, TARGET])
    if mode == 'uefi':
        regular(TARGET / 'boot').mkdir(exist_ok=True)
        run(['mount', bootdev, TARGET / 'boot'])
    return disk['path']


def digest(source):
    hashes = {}
    for p in sorted(source.rglob('*')):
        rel = p.relative_to(source)
        if '.git' in rel.parts:
            continue
        if p.is_symlink():
            raise ValueError('Source symlink refused: ' + str(rel))
        if p.is_dir():
            continue
        if not stat.S_ISREG(p.stat().st_mode):
            raise ValueError('Nonregular source refused.')
        hashes[str(rel)] = hashlib.sha256(p.read_bytes()).hexdigest()
    return hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest(), hashes


def save_json(path, data):
    regular(path.parent).mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.vivian-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(data, f, indent=2)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        d = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(d)
        finally:
            os.close(d)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def detect_hardware():
    cpu = Path('/proc/cpuinfo').read_text()
    cpu_vendor = 'intel' if 'GenuineIntel' in cpu else 'amd' if 'AuthenticAMD' in cpu else 'other'
    gpu = set()
    for p in Path('/sys/class/drm').glob('card[0-9]/device/vendor'):
        gpu.add(p.read_text().strip())
    gpu_vendor = 'nvidia' if '0x10de' in gpu else 'intel' if '0x8086' in gpu else 'amd' if '0x1002' in gpu else 'generic'
    print(f'Detected CPU: {cpu_vendor}; graphics: {gpu_vendor}.')
    if gpu_vendor == 'nvidia':
        print('NVIDIA stable proprietary driver will be selected. Legacy unsupported cards require a separately reviewed host module.')
    answer = ask('Graphics driver: intel / amd / nvidia / generic', gpu_vendor)
    if answer not in {'intel', 'amd', 'nvidia', 'generic'}:
        raise ValueError('Invalid graphics selection.')
    return cpu_vendor, answer


def prepare_source(source, revision, boot_mode, boot_disk, vm_key=None):
    target_source = regular(TARGET / 'etc/nixos')
    if target_source.exists():
        raise ValueError('Existing /mnt/etc/nixos preserved. Resume using its valid receipt, or choose an empty target.')
    hostname = ask('New hostname', 'vivian-' + os.urandom(2).hex())
    username = ask('Primary username', 'aesc')
    if not hostname or not re.fullmatch(r'[a-z][a-z0-9-]{0,61}[a-z0-9]|[a-z]', hostname):
        raise ValueError('Use a lowercase hostname of at most 63 characters.')
    if hostname in {'tonelico', 'tonelico-nix', 'template'} or (source / 'hosts' / hostname).exists():
        raise ValueError('Hostname collides with an existing host; its files were preserved.')
    if not username or not re.fullmatch(r'[a-z_][a-z0-9_-]{0,30}', username) or username in {'root', 'nixbld', 'greeter', 'nobody'}:
        raise ValueError('Invalid or reserved username.')
    cpu, gpu = detect_hardware()
    regular(target_source.parent).mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.vivian-source-', dir=target_source.parent))
    tree = staging / 'tree'
    try:
        shutil.copytree(source, tree, ignore=shutil.ignore_patterns('.git', '__pycache__'))
        for p in [tree, *tree.rglob('*')]:
            p.chmod(p.stat().st_mode | stat.S_IWUSR)
        host = tree / 'hosts' / hostname
        host.mkdir()
        run(['nixos-generate-config', '--root', TARGET, '--dir', host])
        # Only the boilerplate just created by nixos-generate-config is removed.
        (host / 'configuration.nix').unlink()
        hardware = host / 'hardware-configuration.nix'
        hardware.write_text(re.sub(r'swapDevices\s*=\s*\[[^;]*\];', 'swapDevices = [ ];', hardware.read_text(), flags=re.S))
        (host / 'default.nix').write_text('{ ... }: { imports = [ ../template/default.nix ]; }\n')
        extra = []
        if vm_key:
            key = vm_key.read_text().strip()
            if not re.fullmatch(r'ssh-ed25519 [A-Za-z0-9+/=]+(?: [^\n]*)?', key):
                raise ValueError('VM test key must be one Ed25519 public key.')
            (host / 'vm-test.nix').write_text('{ ... }: { services.openssh.enable = true; services.openssh.settings.PasswordAuthentication = false; users.users.root.openssh.authorizedKeys.keys = [ ' + json.dumps(key) + ' ]; boot.kernelParams = [ "console=tty0" "console=ttyS0,115200" ]; }\n')
            extra = ['./vm-test.nix']
        (host / 'host.nix').write_text('''{
  hostName = %s;
  primaryUser = %s;
  system = "x86_64-linux";
  userUid = 1000;
  userGid = 100;
  portable = true;
  retainLocalRecovery = false;
  bootMode = %s;
  bootDisk = %s;
  cpuVendor = %s;
  gpuVendor = %s;
  extraModules = [ %s ];
}
''' % tuple([json.dumps(v) for v in (hostname, username, boot_mode, boot_disk, cpu, gpu)] + [' '.join(extra)]))
        save_json(tree / 'installation-provenance.json', {
            'repository': 'https://github.com/Roshrak/Vivian', 'revision': revision,
            'source_sha256': digest(source)[0], 'hostname': hostname, 'username': username,
            'boot_mode': boot_mode, 'vm_test_only': bool(vm_key), 'created_at': time.time()})
        run(['git', '-C', tree, 'init', '--initial-branch=main'])
        run(['git', '-C', tree, 'add', '--', '.'])
        # This is a brand-new generated checkout; no user index exists to overwrite.
        run(['git', '-C', tree, '-c', 'user.name=Vivian installer', '-c', 'user.email=installer@localhost', 'commit', '-m', 'Install Vivian ' + revision + ' with generated host ' + hostname])
        run(['git', '-C', tree, 'remote', 'add', 'origin', 'https://github.com/Roshrak/Vivian.git'])
        os.rename(tree, target_source)
        return hostname, username, digest(target_source)[0]
    finally:
        shutil.rmtree(staging)  # exclusively this invocation's private staging tree


def target_payload(candidate, name):
    p = TARGET / candidate.lstrip('/') / name
    for _ in range(40):
        if not p.is_symlink():
            return p.is_file() and p.stat().st_size > 0
        link = os.readlink(p)
        p = TARGET / link.lstrip('/') if link.startswith('/') else Path(os.path.normpath(p.parent / link))
        if not str(p).startswith(str(TARGET / 'nix/store') + '/'):
            raise ValueError('Boot payload escaped installed Nix store.')
    raise ValueError('Boot payload symlink loop.')


def verify_installed(receipt):
    candidate = receipt['candidate']
    profile = TARGET / 'nix/var/nix/profiles/system'
    # Resolve absolute store symlinks within target, never against installer /nix.
    p = profile
    for _ in range(40):
        if not p.is_symlink():
            break
        link = os.readlink(p)
        p = TARGET / link.lstrip('/') if link.startswith('/') else Path(os.path.normpath(p.parent / link))
    if p != TARGET / candidate.lstrip('/'):
        raise ValueError('Installed system profile does not match built candidate.')
    for name in ('kernel', 'initrd'):
        if not target_payload(candidate, name):
            raise ValueError('Missing installed boot payload: ' + name)
    if receipt['boot_mode'] == 'uefi':
        entries = TARGET / 'boot/loader/entries'
        valid = False
        for entry in entries.glob('nixos*.conf'):
            paths = [l.split(None, 1)[1].strip() for l in entry.read_text().splitlines() if l.startswith(('linux ', 'initrd '))]
            if len(paths) >= 2 and all(v.startswith('/') and regular(TARGET / 'boot' / v.lstrip('/')).is_file() for v in paths):
                valid = True
        if not valid or not (TARGET / 'boot/EFI/BOOT/BOOTX64.EFI').is_file():
            raise ValueError('UEFI boot entry or removable-media fallback loader is missing.')
    elif not (TARGET / 'boot/grub/grub.cfg').is_file():
        raise ValueError('GRUB boot configuration missing.')
    if digest(TARGET / 'etc/nixos')[0] != receipt['installed_source_sha256']:
        raise ValueError('Installed source changed; do not overwrite local changes while resuming.')
    print('[VERIFIED] System profile, kernel, initrd, bootloader and tracked local source.')


def main():
    parser = argparse.ArgumentParser(description='Guided Vivian installation from the standard NixOS ISO. No unattended erasure.')
    parser.add_argument('--source', required=True, type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--revision', required=True, help=argparse.SUPPRESS)
    parser.add_argument('--vm-test-key', type=Path, help='Add isolated VM-only SSH/serial diagnostics using this public key; never needed for physical installation.')
    args = parser.parse_args()
    require_installer()
    source = args.source.resolve()
    source_hash = digest(source)[0]
    if not (source / 'flake.lock').is_file() or not (source / 'home.nix').is_file():
        raise ValueError('Incomplete immutable flake source.')
    print('\n=== VIVIAN: exact modular NixOS + Home Manager ===')
    print('Source revision: ' + args.revision)
    print('The current live desktop will stay running. No automatic reboot.')
    regular(Path('/run/vivian-installer.lock'))
    with open('/run/vivian-installer.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        mode = 'uefi' if Path('/sys/firmware/efi').is_dir() else 'bios'
        resume = ask('N = new installation; R = resume installation mounted at /mnt', 'N').upper()
        if resume == 'N':
            boot_disk = prepare_disk(mode)
        elif resume == 'R':
            boot_disk = None
        else:
            raise ValueError('No installation selected.')
        mounts = validate_mounts(mode)
        state_dir = regular(TARGET / 'var/lib/vivian-installer')
        if not state_dir.exists():
            state_dir.mkdir(parents=True, mode=0o700)
        if state_dir.stat().st_uid != 0 or state_dir.stat().st_mode & 0o077:
            raise ValueError('Installer receipt must be private and root-owned.')
        receipt_file = regular(state_dir / 'receipt.json')
        if receipt_file.exists():
            r = json.loads(receipt_file.read_text())
            if r['source_sha256'] != source_hash or r['revision'] != args.revision:
                raise ValueError('Resume must use original revision: sudo nix --extra-experimental-features "nix-command flakes" run github:Roshrak/Vivian/' + r['revision'] + '#install')
            if r['mounts']['root']['maj:min'] != mounts['root']['maj:min'] or r['mounts']['root']['source'] != mounts['root']['source'] or r['boot_mode'] != mode or (r['mounts']['boot'] or {}).get('source') != (mounts['boot'] or {}).get('source'):
                raise ValueError('Mounted target differs from receipt; existing installation preserved.')
            if digest(TARGET / 'etc/nixos')[0] != r['installed_source_sha256']:
                raise ValueError('Local source changed after preparation; preserved without overwrite.')
        else:
            if resume == 'R':
                raise ValueError('No valid receipt. Use N and existing partitions (M); never re-erase to recover a build failure.')
            hostname, username, installed_hash = prepare_source(source, args.revision, mode, boot_disk, args.vm_test_key)
            r = {'revision': args.revision, 'source_sha256': source_hash,
                 'installed_source_sha256': installed_hash, 'hostname': hostname, 'username': username,
                 'boot_mode': mode, 'boot_disk': boot_disk, 'mounts': mounts, 'phase': 'prepared'}
            save_json(receipt_file, r)
        ref = str(TARGET / 'etc/nixos') + '#' + r['hostname']
        run(['nix', *NIX_FLAGS, 'eval', '--no-write-lock-file', '--raw', ref.replace('#', '#nixosConfigurations.') + '.config.system.build.toplevel.drvPath'])
        if r['phase'] == 'prepared':
            # Build into the installed disk's store, not the ISO's RAM overlay.
            built = run(['nix', *NIX_FLAGS, 'build', '--no-write-lock-file', '--no-link', '--print-out-paths', '--option', 'max-jobs', '1', '--option', 'cores', '2', '--store', str(TARGET),
                         ref.replace('#', '#nixosConfigurations.') + '.config.system.build.toplevel'], True)
            outputs = built.splitlines()
            if len(outputs) != 1 or not outputs[0].startswith('/nix/store/'):
                raise ValueError('Expected exactly one system output.')
            r.update(candidate=outputs[0], phase='built')
            for name in ('kernel', 'initrd'):
                if not target_payload(r['candidate'], name):
                    raise ValueError('Candidate boot payload missing from target store.')
            save_json(receipt_file, r)
        if r['phase'] == 'built':
            run(['nixos-install', '--root', TARGET, '--system', r['candidate'], '--no-root-passwd', '--no-channel-copy'])
            r['phase'] = 'installed'
            save_json(receipt_file, r)
        if r['phase'] == 'installed':
            print('\nSet the installed user password. Passwords are never logged or stored in the source.')
            run(['nixos-enter', '--root', TARGET, '-c', 'passwd ' + shlex.quote(r['username'])])
            r['phase'] = 'password-set'
            save_json(receipt_file, r)
        verify_installed(r)
        r['phase'] = 'verified'
        save_json(receipt_file, r)
        # Only after build/install verification, allow the installed wheel user
        # to maintain the local source. No shared live-ISO UID can write it during preparation.
        run(['chown', '-R', '1000:100', TARGET / 'etc/nixos'])
        print('\nSUCCESS: Vivian is installed; no automatic reboot was performed.')
        print('Installed host: ' + r['hostname'] + '; user: ' + r['username'])
        print('Exact upstream revision: ' + r['revision'])
        print('After reboot: sudo nixos-rebuild build (or test / switch), using /etc/nixos automatically.')
        print('Private API/Telegram/AGY credentials and personal application data are not copied from another machine.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError, KeyboardInterrupt) as e:
        print('\nINSTALLATION STOPPED SAFELY: ' + str(e), file=sys.stderr)
        print('Existing data and completed phases are retained. A failed build does NOT require formatting again.', file=sys.stderr)
        sys.exit(1)
