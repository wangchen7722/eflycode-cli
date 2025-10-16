from pathlib import Path

EFLYCODE_USER_HOME_DIR = Path.home() / ".eflycode"
EFLYCODE_USER_CONFIG_FILE = EFLYCODE_USER_HOME_DIR / "config.toml"

EFLYCODE_PROJECT_HOME_DIR = Path.cwd() / ".eflycode"
EFLYCODE_PROJECT_CONFIG_FILE = EFLYCODE_PROJECT_HOME_DIR / "config.toml"