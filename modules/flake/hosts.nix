# Host discovery. Each directory under hosts/ that holds host.nix and
# hardware-configuration.nix becomes nixosConfigurations.<directory>.
# Templates and documentation are ignored. Host metadata reaches NixOS and
# Home Manager modules as the `host` argument.
{ config, inputs, lib, ... }:
let
  hostRoot = ../../hosts;

  hostKeys = builtins.attrNames (
    lib.filterAttrs (
      name: type:
      type == "directory"
      && builtins.pathExists (hostRoot + "/${name}/host.nix")
      && builtins.pathExists (hostRoot + "/${name}/hardware-configuration.nix")
    ) (builtins.readDir hostRoot)
  );

  readHost = key: import (hostRoot + "/${key}/host.nix");

  mkHost =
    hostKey:
    let
      hostPath = hostRoot + "/${hostKey}";
      host = readHost hostKey;
      codexPackage = inputs.codex-nixpkgs.legacyPackages.${host.system}.codex;
    in
    lib.nameValuePair hostKey (
      inputs.nixpkgs.lib.nixosSystem {
        system = host.system;
        modules = [
          (hostPath + "/hardware-configuration.nix")
          (hostPath + "/default.nix")
          inputs.home-manager.nixosModules.home-manager
          config.nixos.home-manager-integration
          {
            _module.args.host = host;
            # Codex is intentionally sourced from the dedicated pinned input
            # instead of upgrading all NixOS packages.
            nixpkgs.overlays = [ (_final: _prev: { codex = codexPackage; }) ];
          }
          config.nixos.system
          { networking.hostName = host.hostName; }
        ]
        ++ (host.extraModules or [ ])
        ++ map (name: config.nixos.${name}) (host.features or [ ]);
      }
    );

  configurations = builtins.listToAttrs (map mkHost hostKeys);

  hostnames = map (key: (readHost key).hostName) hostKeys;

  hostnameAliases = builtins.listToAttrs (
    map (key: lib.nameValuePair (readHost key).hostName configurations.${key}) hostKeys
  );
in
{
  # Directory-based names serve installation and backup tooling; hostname
  # aliases serve native nixos-rebuild without --flake.
  flake.nixosConfigurations =
    assert lib.assertMsg (builtins.length (lib.unique hostnames) == builtins.length hostnames)
      "Vivian hostnames must be unique across hosts/.";
    assert lib.assertMsg (lib.all (key:
      let name = (readHost key).hostName;
      in name == key || !(builtins.elem name hostKeys)) hostKeys)
      "A Vivian hostname alias must not shadow another host directory.";
    configurations // hostnameAliases;
}
