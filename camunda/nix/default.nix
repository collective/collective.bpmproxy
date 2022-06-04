# https://github.com/nmattia/niv
{ sources ? import ./sources.nix
, nixpkgs ? sources."nixpkgs-21.11"
}:

let

  overlay = _: pkgs: {
    buildMavenRepositoryFromLockFile = (pkgs.callPackage ./pkgs/mvn2nix { inherit nixpkgs; }).buildMavenRepositoryFromLockFile;
    gitignoreSource = pkgs.callPackage ./pkgs/gitignore-source {};
    mvn2nix = (pkgs.callPackage ./pkgs/mvn2nix { inherit nixpkgs; }).mvn2nix;
  };

  pkgs = import nixpkgs {
    overlays = [ overlay ];
    config = {};
  };

in pkgs
