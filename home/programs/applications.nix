{ pkgs, inputs, lib, ... }:
{
  home.packages = with pkgs; [
    # User applications; system services and login/runtime dependencies stay
    # in their NixOS modules.
    pdfarranger
    nautilus file-roller seahorse gnome-disk-utility gparted
    mpv vlc pavucontrol swappy wev kdePackages.fcitx5-configtool
    nano btop ripgrep fd tree rclone codex
    zenity gh fzf gcc tree-sitter lazygit
    (chromium.override { commandLineArgs = [ "--password-store=basic" ]; })
    easyeffects prismlauncher (lib.setPrio 3 jdk8) (lib.setPrio 4 jdk17) jdk21 mangohud
    obs-studio
    (discord.override { commandLineArgs = "--ozone-platform=x11"; })
    obsidian libreoffice telegram-desktop
    inputs.claude-code-nix.packages.${pkgs.stdenv.hostPlatform.system}.default
    inputs.llm-agents.packages.${pkgs.stdenv.hostPlatform.system}.antigravity-cli
    inputs.llm-agents.packages.${pkgs.stdenv.hostPlatform.system}.opencode
    inputs.hermes-agent.packages.${pkgs.stdenv.hostPlatform.system}.messaging
  ];
}
