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
not public. A source-built uinput_type helper preserves the bridge's existing ASCII input
protocol and guard checks; actual Minecraft targeting/input is a physical
acceptance item. The referenced music helper is packaged with its Python
dependency. The market helper reads real public results, keeps credentials out
of source and requires --send-telegram for external upload. The older private
helper's embedded credential and fabricated static offers are not published.
The verified 720-minute cleanup intent uses the original bounded retention code
in a user timer; private Hermes cron prompts/history are not copied.

Mutable state: existing files are preserved. Fresh hosts seed reviewed Noctalia
TOML settings and wallpaper files. Application-generated databases, downloads,
secrets and session histories are not copied. The three community template
inputs actually referenced by the seeded profiles are included as public text assets.

Boot/recovery: only Tonelico references existing local generations. New hosts
begin their own generation history. UEFI systemd-boot and BIOS GRUB are selected
from the installer's actual firmware mode. No swap partition is generated;
ZRAM remains enabled with the original 50 percent policy.

## Setting ownership and deliberate differences

| Configuration area | Class | Fresh-machine rule |
| --- | --- | --- |
| Pinned inputs, overlays, application overrides and versions | SHARED | Exact original lock file and package declarations; no broad update. |
| Nix policy/caches, locale/timezone, security and system services | SHARED | Preserve current declared policy. Passwordless wheel and trusted Nix users remain intentional high-trust choices. |
| All seven desktop/session packages, patches, lifecycle wrappers and portals | SHARED | Preserve package owners, custom grammar, ordering and session catalogue. |
| Zoom/other animations, overview/keybindings, Fcitx/Vietnamese, themes/fonts | SHARED | Preserve the source settings; physical keys, appearance and hardware rendering still need acceptance. |
| Home Manager, shell/Git/editor/terminal, user packages and agents | SHARED | Same integrated architecture/stateVersion; substitute the selected home/user without standalone activation. |
| ZRAM and system swap policy | SHARED | Keep ZRAM at 50%; do not invent SSD swap or hibernation. |
| Account provisioning, hostname, primary UID and home directory | HOST-SPECIFIC | Guided hostname/user; default aesc, UID 1000. Never silently create root or greeter as primary user. |
| Filesystem UUIDs, mounts and hardware-configuration.nix | HOST-SPECIFIC | Generated from the chosen new disk and actual mounts; no Tonelico UUID reuse. |
| EFI/BIOS, loader and BIOS boot target | HOST-SPECIFIC | Detect actual firmware; BIOS requires a stable by-id disk reference to survive USB removal/device renumbering. |
| CPU microcode and GPU/firmware driver integration | HOST-SPECIFIC | Detect vendor; ask for driver selection; retain redistributable firmware. Legacy NVIDIA/hybrid-specific tuning is not claimed tested. |
| Fixed panel/HDMI layout, workspace-to-connector assignments and pointer startup | HOST-SPECIFIC | Automatic preferred outputs on foreign hardware; omit laptop-only connector assumptions. Other workspace/binding behavior stays. |
| Laptop Intel NPU, PixArt reprobe and exact USB identities | HOST-SPECIFIC | Retained only under hosts/tonelico; generic QMK/VIA and virtualization remain shared. |
| Recovery generation 128/129/135 references | HOST-SPECIFIC | Retain original laptop files; do not add foreign store paths/boot payloads to fresh hosts. |
| Writable Mango/Noctalia/GTK/KDE/XFCE state | SHARED / HOST-SPECIFIC | Seed reviewed defaults only when absent; keep application mutability, ownership and backups. |
| Dormant archive modules | OPTIONAL | Preserve history; never import an unused desktop merely to reproduce an archive file. |
| Private API/messaging credentials, AGY sessions and personal application data | EXTERNAL DEPENDENCY | Not public. Programs/bridge/helpers are declared; private authenticated behavior cannot be manufactured. |
| Imperative helper binaries and music dependencies | SHARED | Source-built uinput helper and declared Python/websockets/Pillow/wtype dependencies replace unpublished local executable assumptions. |
| Market helper's private embedded token/static offers | EXTERNAL DEPENDENCY | Never publish a token or fabricate listings. Public helper retrieves actual listings; optional sending needs environment credentials and explicit flag. |
| Former private Hermes cleanup scheduling record | SHARED / HOST-SPECIFIC | Same bounded 30-day cleaner, declared 12-hour user timer; private prompts/history excluded. |

The complete file/resource classification and SHA-256 manifest is
[SOURCE-OWNERSHIP.json](SOURCE-OWNERSHIP.json). Mixed module boundaries above
are intentionally preserved instead of replacing the architecture.
The existing Git identity, browser flags and trusted-user policy are configuration
parity choices, not new security promises. Shared user scripts may require private
Minecraft instances or authenticated services before their real task can run.

Fresh-host first-login repairs preserve intended behavior: mutable GTK profile
settings, initial colors and available terminal/Qt palettes are included, rather
than depending on unpublished files. The original laptop's source behavior is
unchanged. The small autosleep policy retries briefly if Noctalia is still
starting; it does not restart the compositor. Root rebuilds trust only
`/etc/nixos` through the generated system Git configuration. Installer Nix caches
use a private directory on the target disk, with trust scoped to `/mnt/etc/nixos`.

The newly installed repository is a clean local snapshot plus its generated
host and upstream provenance; it is not a blind checkout that overwrites future
local host changes. Review upstream updates before integrating them. Native
rebuilds use the generated hostname alias. Private credentials and personal
application state remain excluded, even when a public helper refers to their
expected runtime location. Original laptop-only recovery closures are an external
machine-local dependency of `tonelico`, not an installer dependency of new hosts.
The ISO launcher never selects `tonelico` for a different computer.
