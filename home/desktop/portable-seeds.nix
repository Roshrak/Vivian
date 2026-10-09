{ config, lib, pkgs, host, inputs, ... }:
let
  home = config.home.homeDirectory;
  source = ../files/config/portable-seeds;
  render = path: lib.replaceStrings [ "/home/aesc" ] [ home ] (builtins.readFile path);
  seed = relative: path: ''
    seed ${pkgs.writeText (builtins.baseNameOf relative) (render path)} "$HOME/${relative}"
  '';
  profiles = [ "niri" "mango" "sway" "hyprland" ];
  hermes = inputs.hermes-agent.packages.${pkgs.stdenv.hostPlatform.system}.messaging;
in lib.mkIf (host.portable or false) {
  # Mutable application-owned settings are copied only when absent.
  # They are never forced into store symlinks and never overwrite existing data.
  home.activation.seedPortableAppearance = lib.hm.dag.entryAfter [ "seedDesktopDefaults" ] (''
    seed() {
      local source="$1" target="$2"
      if [ ! -e "$target" ] && [ ! -L "$target" ]; then
        run ${pkgs.coreutils}/bin/mkdir -p -- "$(${pkgs.coreutils}/bin/dirname "$target")"
        run ${pkgs.coreutils}/bin/cp --no-clobber -- "$source" "$target"
        run ${pkgs.coreutils}/bin/chmod u+rw -- "$target"
      fi
    }
  '' + lib.concatMapStrings (name: seed ".config/noctalia/${name}" (source + "/${name}")) [
    "config.toml" "99-comic-mono.toml" "99-media-paths.toml"
  ] + lib.concatMapStrings (relative: seed ".local/state/noctalia/community-templates/${relative}"
    (source + "/community-templates/${relative}")) [
      "obs/matugen.obt" "prismlauncher/prismlauncher.json" "obsidian/obsidian.css"
    ] + lib.concatMapStrings (profile:
    lib.concatMapStrings (name: seed ".config/theme-profiles/${profile}/config-home/noctalia/${name}"
      (source + "/profiles/${profile}/${name}"))
      (builtins.attrNames (builtins.readDir (source + "/profiles/${profile}")))) profiles);

  # The original laptop's gateway unit was installed imperatively and contains
  # a local store environment path. Fresh hosts use the pinned package instead.
  # Missing private credentials skip startup, rather than entering a crash loop.
  systemd.user.services.hermes-gateway = {
    Unit = {
      Description = "Hermes Agent Gateway - Messaging Platform Integration";
      After = [ "network-online.target" ];
      Wants = [ "network-online.target" ];
      ConditionPathExists = [ "${home}/.hermes/config.yaml" "${home}/.hermes/.env" ];
    };
    Service = {
      Type = "simple";
      ExecStart = "${hermes}/bin/hermes gateway run";
      WorkingDirectory = "${home}/.hermes";
      Environment = [ "HERMES_HOME=${home}/.hermes" "HERMES_SUPERVISED_CHILD=1" ];
      Restart = "on-failure";
      RestartSec = 5;
      RestartForceExitStatus = 75;
      SuccessExitStatus = 75;
      RestartPreventExitStatus = 78;
      KillMode = "mixed";
      TimeoutStopSec = 70;
    };
    Install.WantedBy = [ "default.target" ];
  };
}
