# The guided installer, exposed as `nix run github:Roshrak/Vivian#install`.
# It runs installer/install.py against this exact flake source and revision.
{ inputs, ... }:
let
  inherit (inputs.nixpkgs) lib;
in
{
  flake.apps.x86_64-linux.install =
    let
      pkgs = import inputs.nixpkgs { system = "x86_64-linux"; };
      launcher = pkgs.writeShellApplication {
        name = "vivian-install";
        runtimeInputs = with pkgs; [ python3 git nix parted util-linux e2fsprogs dosfstools systemd nixos-install-tools ];
        text = ''
          exec python3 ${../../installer/install.py} --source ${inputs.self.outPath} \
            --revision ${lib.escapeShellArg (inputs.self.rev or inputs.self.dirtyRev or "uncommitted")} "$@"
        '';
      };
    in
    {
      type = "app";
      program = "${launcher}/bin/vivian-install";
    };
}
