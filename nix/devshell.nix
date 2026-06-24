{
  pkgs,
  mkShell,
  ollama-models-db,
}:

mkShell {
  packages = with pkgs; [
    python3
    python3.pkgs.httpx
    python3.pkgs.beautifulsoup4
    python3.pkgs.lxml
    python3.pkgs.click
    python3.pkgs.pytest
    python3.pkgs.ruff
    ollama-models-db
  ];

  shellHook = ''
    echo "ollama-models-db dev shell"
    echo "Run 'ollama-models-db --help' to get started"
  '';
}
