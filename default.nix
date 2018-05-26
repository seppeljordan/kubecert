let
  nixpkgs = import <nixpkgs> {};
  pypiPackages = import nix/requirements.nix { pkgs = nixpkgs; };
  f = { buildPythonPackage, lib, effect, attrs, pytest, flake8 }:
    let
    sourceFilter = name: type:
      let baseName = with builtins; baseNameOf (toString name); in
      lib.cleanSourceFilter name type &&
      !(
        (type == "directory" && lib.hasSuffix ".egg-info" baseName)||
        (type == "directory" && baseName == "tmp")||
        (type == "directory" && baseName == "__pycache__")||
        (type == "directory" && baseName == ".pytest_cache")
      );
    in
    buildPythonPackage {
      name = "kubecert-1.0";
      src = lib.cleanSourceWith {
        filter = sourceFilter;
        src = ./.;
      };
      propagatedBuildInputs = [ effect attrs ];
      checkInputs = [ pytest flake8 ];
      checkPhase = ''
        flake8 src/ tests/
        py.test
      '';
    };
in
nixpkgs.callPackage f
{
  buildPythonPackage = nixpkgs.python3Packages.buildPythonPackage;
  effect = pypiPackages.packages.effect;
  attrs = pypiPackages.packages.attrs;
  pytest = pypiPackages.packages.pytest;
  flake8 = pypiPackages.packages.flake8;
}
