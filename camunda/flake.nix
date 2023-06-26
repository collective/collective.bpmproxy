{
  description = "Camunda Application";

  inputs = {

    # Core
    flake-utils.url = "github:numtide/flake-utils";
    nixpkgs.url = "github:NixOS/nixpkgs/release-22.11";
    nixpkgs-unstable.url = "github:NixOS/nixpkgs/master";
    flake-compat = { url = "github:edolstra/flake-compat"; flake = false; };

    # Flakes
    mvn2nix = { url = "github:fzakaria/mvn2nix"; inputs.nixpkgs.follows = "nixpkgs"; inputs.utils.follows = "flake-utils"; };
  };

  outputs = { self, nixpkgs, nixpkgs-unstable, flake-utils, ...}@inputs: flake-utils.lib.eachDefaultSystem (system: let
    pkgs = import nixpkgs { inherit system; overlays = [
      (final: prev: {
        maven = (prev.maven.override { jdk = final.jdk17; });
      })
      inputs.mvn2nix.overlay
    ]; };
    pkgs-unstable = import nixpkgs-unstable { inherit system; };
    call-name = "plone-camunda-app";
  in {

    apps.default = {
        type = "app";
        program = "${self.packages.${system}.default}/bin/${call-name}";
    };

    packages.default = pkgs.stdenv.mkDerivation {
      name = call-name;
      src = self.packages.${system}.jar;
      phases = [ "installPhase" "fixupPhase" ];
      installPhase = ''
        mkdir -p $out/bin $out/var/lib
        cp $src $out/var/lib/${call-name}.jar
        cat << EOF > $out/bin/${call-name}
#!/usr/bin/env bash
exec ${pkgs.temurin-jre-bin-17}/bin/java ''\\$@ -jar $out/var/lib/${call-name}.jar
EOF
        chmod u+x $out/bin/${call-name}
      '';
    };

    # Jar
    packages.jar = let mavenRepository = pkgs.buildMavenRepositoryFromLockFile {
      file = ./mvn2nix-lock.json;
    }; in pkgs.stdenv.mkDerivation rec {
      pname = call-name;
      version = "0.1";
      name = "${pname}-${version}.jar";
      src = ./.;

      buildInputs = with pkgs; [ jdk17_headless maven ];
      buildPhase = ''
        find . -print0|xargs -0 touch
        echo "mvn package --offline -Dmaven.repo.local=${mavenRepository}"
        mvn package --offline -Dmaven.repo.local=${mavenRepository}
      '';

      installPhase = ''
        mv target/${name} $out
        jar i $out
      '';
    };

    # Container image
    packages.image = pkgs.dockerTools.streamLayeredImage {
      name = call-name;
      tag = "latest";
      created = "now";
      contents = [(pkgs.buildEnv {
        name = "image-contents";
        paths = [
          pkgs.busybox
          pkgs.dockerTools.fakeNss
          pkgs.dockerTools.usrBinEnv
          pkgs.tini
          pkgs.temurin-jre-bin-11
          self.packages.${system}.default
        ];
        pathsToLink = [ "/etc" "/sbin" "/bin" ];
      })];
      extraCommands = ''
        mkdir -p usr/bin && ln -s /sbin/env usr/bin/env
        mkdir -p tmp && chmod a+rxwt tmp
      '';
      config = {
        Entrypoint = [ "${pkgs.tini}/bin/tini" "--" "${self.packages.${system}.default}/bin/${call-name}" ];
        Env = [
          "TMPDIR=/tmp"
          "HOME=/tmp"
          "LOG4J_FORMAT_MSG_NO_LOOKUPS=true"
        ];
        Labels = {};
        User = "nobody";
      };
    };

    devShells.default = pkgs.mkShell {
      buildInputs = [
        pkgs-unstable.cachix
        pkgs-unstable.jfrog-cli
        pkgs.entr
        pkgs.gnumake
        pkgs.jdk17
        pkgs.jq
        pkgs.openssl
        pkgs.poetry
        (pkgs.maven.override { jdk = pkgs.jdk17; })
        (inputs.mvn2nix.defaultPackage.${system}.override { jdk = pkgs.jdk17; maven = pkgs.maven.override { jdk = pkgs.jdk17; }; })
      ];
    };
  });
}
