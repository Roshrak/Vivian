{ pkgs, inputs, ... }:

{
  environment.sessionVariables = {
    BROWSER = "chromium";
    XCURSOR_THEME = "Bibata-Modern-Ice";
    XCURSOR_SIZE = "24";
    LV2_PATH = "/run/current-system/sw/lib/lv2";
  };

  # Shared greeter assets and the system LV2 plugin path stay system-owned.
  # User applications are declared in home/programs/applications.nix.
  environment.systemPackages = with pkgs; [
    bibata-cursors
    xdg-user-dirs
    lsp-plugins
    calf
    zam-plugins
    mda_lv2
    glib
  ];

  programs.steam.enable = true;
  programs.gamemode.enable = true;

  services.fcitx5-lotus = {
    enable = true;
    users = [ "aesc" ];
    package =
      inputs.lotus.packages.${pkgs.stdenv.hostPlatform.system}.fcitx5-lotus;
  };
}
