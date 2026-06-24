{
  description = "SQLite database of available Ollama models";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-parts.url = "github:hercules-ci/flake-parts";
    devshell.url = "github:numtide/devshell";
  };

  outputs =
    inputs@{
      self,
      nixpkgs,
      flake-parts,
      devshell,
      ...
    }:
    flake-parts.lib.mkFlake { inherit inputs; } {
      imports = [
        devshell.flakeModule
      ];

      systems = [
        "x86_64-linux"
        "aarch64-linux"
        "x86_64-darwin"
        "aarch64-darwin"
      ];

      perSystem =
        {
          pkgs,
          system,
          ...
        }:
        let
          pkgs' = import nixpkgs {
            inherit system;
            overlays = [ self.overlays.default ];
          };
        in
        {
          packages = {
            default = pkgs'.ollama-models-db;
          };

          devshells.default = {
            packages = with pkgs'; [
              python3
              python3.pkgs.httpx
              python3.pkgs.beautifulsoup4
              python3.pkgs.lxml
              python3.pkgs.click
              python3.pkgs.pytest
              python3.pkgs.ruff
              self.packages.${system}.default
            ];
          };
        };

      flake = {
        overlays.default = final: prev: {
          ollama-models-db = final.callPackage ./nix/package.nix {
            httpx = final.python3.pkgs.httpx;
            beautifulsoup4 = final.python3.pkgs.beautifulsoup4;
            lxml = final.python3.pkgs.lxml;
            click = final.python3.pkgs.click;
          };
        };

        nixosModules.default = import ./nix/module.nix;
      };
    };
}
