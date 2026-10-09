{ config, lib, pkgs, host, ... }:
let
  python = pkgs.python3.withPackages (ps: [ ps.websockets ps.pillow ]);
  uinput = pkgs.stdenv.mkDerivation {
    pname = "vivian-uinput-type";
    version = "1";
    src = ../files/bin/uinput_type.c;
    dontUnpack = true;
    buildPhase = ''$CC -Wall -Wextra -Werror -O2 "$src" -o uinput_type'';
    installPhase = ''install -Dm755 uinput_type "$out/bin/uinput_type"'';
    doCheck = true;
    checkPhase = ''
      ./uinput_type --check t sleep:250 'type:Hello / World!' enter
      if ./uinput_type --check 'sleep:999999'; then exit 1; fi
      if ./uinput_type --check 'type:非ASCII'; then exit 1; fi
    '';
  };
  helper = name: {
    name = ".local/bin/${name}";
    value = {
      executable = true;
      text = "#!${python}/bin/python3\n" + lib.removePrefix "#!/usr/bin/env python3\n"
        (builtins.readFile (../files/bin + "/${name}"));
    };
  };
in lib.mkIf (host.portable or false) {
  home.file = lib.listToAttrs (map helper [ "ytmusic_control.py" "gpu_market_search.py" "clean-system.py" ]) // {
    ".local/bin/uinput_type".source = "${uinput}/bin/uinput_type";
    ".hermes/scripts/clean-system.py".text = builtins.readFile ../files/bin/clean-system.py;
  };
  # Preserve the verified 720-minute cleanup intent without publishing private
  # Hermes cron history or prompts. The code keeps its original 30-day policy.
  systemd.user.services.vivian-disk-care = {
    Unit.Description = "Vivian bounded 30-day cache retention";
    Service = {
      Type = "oneshot";
      ExecStart = "${pkgs.python3}/bin/python3 ${config.home.homeDirectory}/.hermes/scripts/clean-system.py";
    };
  };
  systemd.user.timers.vivian-disk-care = {
    Unit.Description = "Vivian disk care every 12 hours";
    Timer = { OnBootSec = "12h"; OnUnitActiveSec = "12h"; Persistent = true; };
    Install.WantedBy = [ "timers.target" ];
  };
}
