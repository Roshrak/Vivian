# Installation verification — October 9, 2026

This is the complete modular configuration, not a reduced VM recreation.
The public GitHub installer was exercised from a clean official NixOS 26.05
graphical ISO, then each guest was booted from its installed disk without the ISO.

| Test | Observed result |
| --- | --- |
| Original `tonelico` compatibility | Complete build passed; critical options, Home Manager settings and original package names/priorities compared with the October 9 source baseline. |
| Public UEFI installation | Revision `de3b64e207e3689052ff83ef7c95eef476cf0852`, GNOME ISO session, new host `vivian-public`, selected user `vivtest`; installed and booted through systemd-boot. |
| Public BIOS installation | Revision `683478db7207338848afa3903a3ea13c472988f6`, Plasma ISO session, new host `vivian-bios`, default user `aesc`; installed and booted through GRUB using its stable disk ID. |
| Native rebuilds after installation | Plain `sudo nixos-rebuild build`, `test`, and `switch` all passed in both installed guests, without a manual flake argument or Home Manager activation. |
| Hardware/source generation | New UUIDs and hardware modules; generated host files tracked. BIOS checkout parent equals its launching GitHub revision and the only added files are three host files plus provenance. |
| Safe rerun | Both completed installations resumed and verified without formatting, reinstalling, or requesting a new password. Interrupted UEFI builds also resumed. |
| Home Manager and swap | Integrated activation successful; ZRAM active at the original 50% policy, no disk swap. Lock-file SHA-256 preserved. |
| Graphical operation | Actual Niri/Noctalia login in UEFI and Mango/Noctalia login in BIOS; real PDF Arranger GUI in both. |
| Integration checks | BIOS Settings portal ReadAll, notification server information, and libvirt RPC completed; final system/user failed-unit lists were empty. These calls do not certify screen sharing or visible notification delivery. |
| Session coverage | All seven desktop families present; Niri and Mango exercised. Other sessions retain their source and static definitions but were not graphically logged into. |
| Installer fixtures | 41 passing tests covering terminal I/O, disk protection/confirmation, source inclusion, symlinks, interrupted preparation, OS-root preservation, upstream revision checks, bounded crash retry and safe resume. |
| Public source/history | Tracked-file/hash manifest, resource dependencies, Python syntax and credential-pattern checks passed. Pattern scanning cannot prove absence of every possible secret. |

Both VMs used QEMU/KVM, two virtual CPUs, 8 GiB RAM and separate 110 GiB
virtual disks. The official ISO included both GNOME and Plasma boot selections;
both were tested. Its SHA-256 was
`8c39c59fb6a83cf5451e02934ccf06c7a9f62addf409a8bb9e02efbb2d994d0c`.

The BIOS test covers the final functional installer code at `683478d`.
Subsequent publication changes update documentation and its hash manifest only.
For that exact tested installer, use
`github:Roshrak/Vivian/683478db7207338848afa3903a3ea13c472988f6#install`.

Tests used a loopback NAR cache of existing, hash-verified packages to avoid
repeatedly downloading the approximately 38 GiB closure. The actual public
source was fetched from GitHub. The cache and SSH access added to the disposable
ISO were test infrastructure, not repository dependencies. Neither published
installation used the optional VM SSH host module; installed observations used
the actual graphical login and private test callbacks. No keys or test passwords
are published.

## Observed failures and limits

Three Nix 2.34.8 subprocesses crashed with SIGBUS in earlier attempts: one local
prototype build and two published UEFI evaluation/build attempts. Target/RAM
filesystem space and inodes remained available; no logged OOM/storage failure
established the cause. A debugger run completed normally without reproducing
the fault. The final installer retries that identical evaluation/build once,
then stops safely if it recurs. Ordinary errors are not hidden or retried.
Completed phases can be resumed. This is recovery behavior, not a claim that
Nix itself has been repaired. The final BIOS installation had no SIGBUS.

The published UEFI guest's first libvirt idle shutdown exited with status 1.
After native activation, its subsequent idle shutdown exited normally and no
failed units remained. The BIOS guest's initial idle shutdown also exited
normally; libvirt RPC passed. The isolated earlier shutdown failure remains
recorded and is not presented as a proven root-cause repair.

Physical GPUs, hybrid/legacy NVIDIA, monitor hotplug, suspend, Bluetooth pairing,
audible quality, Vietnamese physical input, Minecraft targeting and subjective
animation appearance are not certified by VM tests. Private agent credentials
and personal data are intentionally absent; authenticated Telegram/AGY operation
is not claimed. Storage outside the documented wizard scope is not certified.

The original laptop configuration, running generation, ZRAM policy and recovery
assets were not changed, activated, repartitioned, rebooted or pruned.

To rerun isolated source tests:

```bash
python3 -m unittest discover -s tests -v
nix flake check --no-build
```
