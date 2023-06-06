{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-23.05";
    devenv.url = "github:cachix/devenv";
    flake-utils.url = "github:numtide/flake-utils";
    poetry2nix.url = "github:nix-community/poetry2nix";
  };

  outputs = { self, nixpkgs, devenv, flake-utils, poetry2nix, ... } @ inputs:
    flake-utils.lib.eachDefaultSystem (system:
      let
        inherit (poetry2nix.legacyPackages.${system}) mkPoetryApplication;
        pkgs = nixpkgs.legacyPackages.${system};
        python310 = pkgs.python310;
      in
      {
        packages = {
          cnc = mkPoetryApplication {
            projectDir = ./.;
            python = python310;
            preferWheel = true;
          };
          default = self.packages.${system}.cnc;
        };
        devShells.default = devenv.lib.mkShell {
          inherit inputs pkgs;
          modules = [
            ({ pkgs, ... }: {
              packages = [
                pkgs.git
                pkgs.nodePackages.pyright
                pkgs.ruff
                pkgs.pre-commit
                pkgs.act
              ];

              languages.python = {
                enable = true;
                poetry.enable = true;
                package = python310;
              };
            })
          ];
        };
      });
}
