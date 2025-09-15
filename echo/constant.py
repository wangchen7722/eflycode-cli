from pathlib import Path

ECHO_USER_HOME_DIR = Path.home() / ".echo"
ECHO_USER_CONFIG_FILE = ECHO_USER_HOME_DIR / "config.toml"

ECHO_PROJECT_HOME_DIR = Path.cwd() / ".echo"
ECHO_PROJECT_CONFIG_FILE = ECHO_PROJECT_HOME_DIR / "config.toml"