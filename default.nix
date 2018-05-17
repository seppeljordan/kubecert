let
  nixpkgs = import <nixpkgs> {};
  f = { buildPythonPackage, lib }:
    buildPythonPackage {
      name = "kubecert-1.0";
      src = lib.cleanSource ./.;
    };
in
nixpkgs.callPackage f
{
  buildPythonPackage = nixpkgs.python3Packages.buildPythonPackage;
}
