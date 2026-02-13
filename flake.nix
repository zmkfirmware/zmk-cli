{
  description = "The CLI tool for ZMK";

  inputs = {
    flake-parts.url = "github:hercules-ci/flake-parts";
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs =
    inputs@{ flake-parts, ... }:
    flake-parts.lib.mkFlake { inherit inputs; } {
      systems = [
        "x86_64-linux"
        "aarch64-linux"
        "aarch64-darwin"
        "x86_64-darwin"
      ];
      perSystem =
        {
          self',
          pkgs,
          ...
        }:
        let
          python = pkgs.python3Packages;
        in
        {
          packages.default = self'.packages.zmk-cli;
          packages.zmk-cli = python.buildPythonPackage (finalAttrs: {
            pname = "zmk";
            version = "0.4.0";
            src = ./.;

            pyproject = true;

            # basically required for all python packages
            build-system = [
              python.setuptools
              python.setuptools-scm
            ];

            # This is required since some deps in the nixpkgs python
            # distribution are slightly too old. But this should be resolved
            # fairly soon
            #
            # At the time of writing this we have
            #
            # > Checking runtime dependencies for zmk-0.4.0-py3-none-any.whl
            # >   - dacite<2.0.0,>=1.9.2 not satisfied by version 1.9.1
            # >   - mako<2.0.0,>=1.3.10 not satisfied by version 1.3.10.dev0
            # >   - ruamel-yaml<0.19.0,>=0.18.17 not satisfied by version 0.18.16
            pythonRelaxDeps = true;

            # those were infered by just building the package, the check phase
            # will inform you about missing deps if any new ones should pop up
            dependencies = [
              python.dacite
              python.giturlparse
              python.mako
              python.rich
              python.ruamel-yaml
              python.shellingham
              python.typer
              python.west
            ];
          });
        };
    };
}
