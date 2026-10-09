{ pkgs, config, lib, host, ... }:
let
  desktop = import ../../../../lib/desktop-config.nix { inherit lib host; home = config.users.users.${host.primaryUser}.home; };
in

{
  # Exactly one plain Hyprland session.  UWSM is intentionally not used.
  programs.hyprland = {
    enable = true;
    withUWSM = false;
    xwayland.enable = true;
  };

  # The guarded session selects this declarative Hyprland Lua source.
  environment.etc."xdg/hypr/hyprland.lua".source = if !(host.portable or false) && host.primaryUser == "aesc" then ./hyprland/hyprland.lua else pkgs.writeText "hyprland.lua" desktop.hyprland;

  # Use the existing Noctalia compositor shell and its own polkit agent.
  # programs.hyprland supplies the matching portal backend in this nixpkgs.
  # Shared screenshot tools and Xwayland bridge live in core/packages.nix.
  environment.systemPackages = with pkgs; [
    satty
  ];
}
