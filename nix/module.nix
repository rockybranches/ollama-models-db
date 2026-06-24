{ lib, config, pkgs, ... }:

let
  cfg = config.services.ollama-models-db;
  pkg = cfg.package;
  dbPath = cfg.databasePath;
in {
  options.services.ollama-models-db = {
    enable = lib.mkEnableOption "ollama-models-db periodic update service";

    package = lib.mkPackageOption pkgs "ollama-models-db" { };

    databasePath = lib.mkOption {
      type = lib.types.str;
      default = "/var/lib/ollama-models-db/models.db";
      description = "Path to the SQLite database file";
    };

    updateInterval = lib.mkOption {
      type = lib.types.str;
      default = "daily";
      example = "hourly";
      description = "How often to run the update (systemd calendar expression)";
    };

    user = lib.mkOption {
      type = lib.types.str;
      default = "ollama-models-db";
      description = "User under which the service runs";
    };

    group = lib.mkOption {
      type = lib.types.str;
      default = "ollama-models-db";
      description = "Group under which the service runs";
    };

    extraFlags = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [];
      description = "Extra CLI flags passed to 'ollama-models-db update'";
    };
  };

  config = lib.mkIf cfg.enable {
    users.users = lib.mkIf (cfg.user == "ollama-models-db") {
      ollama-models-db = {
        isSystemUser = true;
        group = cfg.group;
        home = "/var/lib/ollama-models-db";
        createHome = true;
      };
    };

    users.groups = lib.mkIf (cfg.group == "ollama-models-db") {
      ollama-models-db = {};
    };

    systemd.services.ollama-models-db-update = {
      description = "Update ollama-models-db SQLite database";
      after = [ "network-online.target" ];
      wants = [ "network-online.target" ];

      serviceConfig = {
        Type = "oneshot";
        User = cfg.user;
        Group = cfg.group;
        StateDirectory = "ollama-models-db";
        ExecStartPre = [
          "${lib.getExe pkg} init --db ${dbPath}"
        ];
        ExecStart = [
          "${lib.getExe pkg} update --db ${dbPath} ${lib.escapeShellArgs cfg.extraFlags}"
        ];
        PrivateTmp = true;
        ProtectHome = true;
        ProtectSystem = "strict";
        ReadWritePaths = [ (builtins.dirOf dbPath) ];
      };
    };

    systemd.timers.ollama-models-db-update = {
      description = "Scheduled ollama-models-db database update";
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnCalendar = cfg.updateInterval;
        Persistent = true;
        RandomizedDelaySec = "30min";
      };
    };
  };
}
