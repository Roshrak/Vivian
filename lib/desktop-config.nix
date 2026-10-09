{ lib, host, home }:
let
  portable = path: lib.replaceStrings [ "/home/aesc" ] [ home ] (builtins.readFile path);
  isPortable = host.portable or false;
  niriOutputs = ''
output "HDMI-A-1" {
    mode "1920x1080@60.000"
    scale 1

    position x=0 y=60
}'';
  niriPanel = ''
output "eDP-1" {
    mode "1920x1200@60.096"
    scale 1
    focus-at-startup

    position x=1920 y=0
}'';
in {
  niri = lib.replaceStrings (lib.optionals isPortable [ niriOutputs niriPanel ])
    (lib.optionals isPortable [ "// Outputs use their preferred modes and automatic layout." "" ])
    (portable ../home/files/config/niri/config.kdl);
  sway = lib.concatStringsSep "\n" (lib.filter (line:
    !isPortable || !(lib.hasPrefix "output HDMI-A-1 " line || lib.hasPrefix "output eDP-1 " line
      || lib.hasPrefix "focus output eDP-1" line
      || builtins.match "workspace [1-9] output (eDP-1|HDMI-A-1)" line != null))
    (lib.splitString "\n" (portable ../home/files/config/sway/config)));
  hyprland = lib.replaceStrings (lib.optionals isPortable [
    ''hl.monitor({ output = "eDP-1", mode = "preferred", position = "auto", scale = 1 })''
    ''hl.monitor({ output = "HDMI-A-1", mode = "preferred", position = "auto-left", scale = 1 })''
    ''cursor = { default_monitor = "eDP-1" },''
  ]) (lib.optionals isPortable [
    ''hl.monitor({ output = "", mode = "preferred", position = "auto", scale = 1 })''
    "" "cursor = {},"
  ]) (portable ../modules/nixos/desktop/sessions/hyprland/hyprland.lua);
  mangoMonitor = if isPortable then "# Automatic compositor layout; no foreign connector names.\n"
    else portable ../home/files/config/mango/monitor-layout.conf;
}
