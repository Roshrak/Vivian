{ pkgs, host, ... }:

{
  virtualisation.libvirtd = {
    enable = true;

    qemu = {
      swtpm.enable = true;
      vhostUserPackages = with pkgs; [
        virtiofsd
      ];
    };
  };

  programs.virt-manager.enable = true;
  virtualisation.spiceUSBRedirection.enable = true;

  users.users.${host.primaryUser}.extraGroups = [
    "libvirtd"
  ];

  environment.systemPackages = with pkgs; [
    dnsmasq
    swtpm
    virtiofsd
  ];
}
