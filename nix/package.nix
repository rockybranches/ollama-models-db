{
  lib,
  buildPythonApplication,
  python3,
  httpx,
  beautifulsoup4,
  lxml,
  click,
}:

buildPythonApplication {
  pname = "ollama-models-db";
  version = "0.1.0";
  pyproject = true;

  src = lib.cleanSourceWith {
    src = ../.;
    filter = path: type:
      (lib.hasPrefix (toString ../src) path)
      || (path == toString ../pyproject.toml)
    ;
  };

  pythonImportsCheck = [ "ollama_models_db" ];

  nativeBuildInputs = [ python3.pkgs.setuptools ];

  propagatedBuildInputs = [
    httpx
    beautifulsoup4
    lxml
    click
  ];

  meta = {
    description = "SQLite database of available Ollama models from ollama.com/search";
    homepage = "https://github.com/robbiec/ollama-models-db";
    license = lib.licenses.mit;
    mainProgram = "ollama-models-db";
  };
}
