{ config, lib, pkgs, host, ... }:
{
  imports = [ ../../modules/nixos/features/virtualization.nix ../../modules/nixos/features/qmk-keyboard.nix ];
  boot.kernelModules = [ "uinput" ];
  services.udev.extraRules = ''KERNEL=="uinput", SUBSYSTEM=="misc", GROUP="input", MODE="0660", TAG+="uaccess"'';
  # The selected wheel user maintains this one checkout. Native root rebuilds
  # must trust it explicitly; never allow every repository with safe.directory=*.
  programs.git.enable = true;
  programs.git.config.safe.directory = "/etc/nixos";
  hardware.cpu.intel.updateMicrocode = lib.mkIf (host.cpuVendor == "intel")
    (lib.mkDefault config.hardware.enableRedistributableFirmware);
  hardware.cpu.amd.updateMicrocode = lib.mkIf (host.cpuVendor == "amd")
    (lib.mkDefault config.hardware.enableRedistributableFirmware);
  hardware.graphics.extraPackages = lib.optionals (host.gpuVendor == "intel") [
    pkgs.intel-media-driver
    pkgs.vpl-gpu-rt
    pkgs.intel-compute-runtime
  ];
  services.xserver.videoDrivers = lib.mkIf (host.gpuVendor == "nvidia") [ "nvidia" ];
  hardware.nvidia = lib.mkIf (host.gpuVendor == "nvidia") {
    modesetting.enable = true;
    open = host.nvidiaOpen or false;
    package = config.boot.kernelPackages.nvidiaPackages.stable;
  };
}
