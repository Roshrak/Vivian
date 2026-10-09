# Validation status

## Observed tests — October 9, 2026

This is the full modular configuration, not a reduced VM recreation.
The official NixOS 26.05 graphical ISO (GNOME session observed) was used with QEMU/KVM, UEFI,
two virtual CPUs, 8 GiB RAM, a 110 GiB virtual disk and virtio graphics.
ISO SHA-256: `8c39c59fb6a83cf5451e02934ccf06c7a9f62addf409a8bb9e02efbb2d994d0c`.

Completed evidence includes:

- Full original `tonelico` build, flake validation, and comparison of its
  critical options and original system/Home Manager package names/priorities.
- Forty-one isolated installer safety tests, including real terminal I/O,
  explicit erase confirmation, symlinks, stale/changed source, interrupted
  source preparation, refusal to replace another OS root, failure-safe resume
  a bounded retry of the identical evaluation/build after a SIGBUS, and refusal
  of a mismatched upstream revision or changed shared source.
- A complete guided installation from the official ISO; interrupted build
  resumed without reformatting. Kernel/initrd, EFI entry and fallback EFI loader
  were verified on the target disk.
- Actual installed first boot without the ISO: Home Manager activation,
  seven session entries, active ZRAM, and zero failed system units.
- Actual Niri login through Noctalia and a PDF Arranger Wayland window.
- Corrected portable configuration built/activated in the guest and plain
  `sudo nixos-rebuild build` passed from user-owned `/etc/nixos`.
- Reviewed public source/history credential-pattern scan found no matches;
  this is not a proof against every possible secret.

Tests used a loopback NAR cache of existing, hash-verified packages to avoid
redownloading the approximately 38 GiB system closure. It is test infrastructure,
not a dependency in the repository or installed configuration. A test-only SSH
public-key module enabled guest observations; default installations do not add it.

## Publication acceptance still in progress

The actual public GitHub command, a fresh installation of its final revision,
and that installed guest's native rebuild are being tested separately.
Do not treat earlier local-source installation as proof of GitHub bootstrapping.

Two Nix 2.34.8 subprocesses crashed with SIGBUS during initial package fetching
or evaluation. Target and RAM filesystem space were available, with no logged
OOM/storage failure explaining the signal. The underlying cause remains unknown.
The installer retries that exact evaluation/build once and stops if it recurs;
ordinary build failures are never hidden or retried. Completed phases remain
available for resume. This is recovery behavior, not a claim that Nix is repaired.

## Limits

Only Niri has been functionally exercised through a graphical login so far;
the other sessions retain their declared configuration and are statically checked.
BIOS/GRUB, physical GPUs and hotplug, suspend, Bluetooth pairing, audible quality,
Vietnamese physical input, Minecraft targeting and subjective animation appearance
are not certified by the UEFI VM test. Legacy NVIDIA and hybrid GPU combinations
can require host-specific tuning. Private agent credentials and personal data
are intentionally absent; authenticated Telegram/AGY behavior is not claimed.

The original laptop has not been switched, rebooted, repartitioned or pruned.
