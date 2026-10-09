{ config, lib, ... }:
let
  portable = path: lib.replaceStrings [ "/home/aesc" ]
    [ config.home.homeDirectory ] (builtins.readFile path);
in
{
  programs.kitty = {
    enable = true;
    shellIntegration.enableBashIntegration = false;
    shellIntegration.mode = null; # Preserve Kitty's existing automatic integration.
    extraConfig = portable ../files/config/kitty/kitty.conf;
  };
  xdg.configFile."kitty/common.conf".text = portable ../files/config/kitty/common.conf;
  xdg.configFile."kitty/tonelico-comic-mono.conf".source = ../files/config/kitty/tonelico-comic-mono.conf;

  programs.neovim = {
    enable = true;
    initLua = builtins.readFile ../files/config/nvim/init.lua;
  };
  xdg.configFile."nvim/lua" = { source = ../files/config/nvim/lua; recursive = true; };
  xdg.configFile."nvim/stylua.toml".source = ../files/config/nvim/stylua.toml;
  # LazyVim lock/session/cache files remain writable and application-owned.

  programs.fastfetch.enable = true;
  xdg.configFile."fastfetch/config.jsonc".text = portable ../files/config/fastfetch/config.jsonc;
}
