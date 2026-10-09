# Portability boundaries

Shared: all modules imported by configuration.nix and home.nix, unless an
explicit host boundary below applies. All flake inputs remain pinned to the
October 9 lock file. All seven sessions and their custom patches/wrappers remain.

Host-specific: hosts/tonelico's UUIDs, Intel NPU/driver tuning, PixArt touchpad
reprobe, exact USB rules, eDP-1/HDMI-A-1 geometry and local recovery generations.
The installer generates a separate host and imports hosts/template instead.
Foreign hosts use preferred modes and automatic output layout; laptop bindings,
zoom animations and shared session/portal ownership remain unchanged.

User-specific: account, home paths, Fcitx user and Home Manager identity are
parameterized. aesc remains the default. Git's existing Roshrak identity remains
an intentional shared default and can be changed declaratively afterwards.

Optional hardware: graphics vendor selection (Intel, AMD, NVIDIA or generic)
and CPU-specific microcode. QMK/VIA and libvirt functionality remain installed.
NVIDIA's current stable proprietary driver does not support every legacy GPU;
unsupported cards require a reviewed host override, rather than silent removal.

External private dependencies: Telegram/API/AGY credentials, Hermes private
configuration, Minecraft instances, browser profiles and personal files are
not public. The precompiled private uinput_type helper has no available source
and is not redistributed blindly; Minecraft input remains unverified until a
reproducible helper is supplied. Two imperative AGY helper paths named in bridge
prompts are outside the declarative configuration; one contains a credential.
They are excluded rather than publishing private data. The bridge itself and
all declarative agent packages/scripts are present.

Mutable state: existing files are preserved. Fresh hosts seed reviewed Noctalia
TOML settings and wallpaper files. Application-generated databases, downloads,
secrets, session histories and community-template caches are not copied.
Some optional theme templates require their upstream runtime downloads.

Boot/recovery: only Tonelico references existing local generations. New hosts
begin their own generation history. UEFI systemd-boot and BIOS GRUB are selected
from the installer's actual firmware mode. No swap partition is generated;
ZRAM remains enabled with the original 50 percent policy.
