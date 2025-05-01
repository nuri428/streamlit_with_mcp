from pathlib import Path
import json
import logging

logger = logging.getLogger(__name__)

default_mcp_config = {
        "command": "python",
        "args": [Path(__file__).parent.parent.parent / "src/api/math_server.py"]
}

class MCPConfigManager:
    def __init__(self, path: Path, default_entry: dict = {}):
        self.path = path
        self.default_entry = default_entry
        self.configs = self.load()
        self.ensure_default("math")

    def load(self):
        if not self.path.exists():
            self.path.write_text("{}", encoding="utf-8")
        try:
            with self.path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Config load error: {e}")
            return {}

    def save(self):
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(self.configs, f, indent=2, ensure_ascii=False)

    def ensure_default(self, key="math"):
        if key not in self.configs:
            self.configs[key] = default_mcp_config

    def detect_transport(self, config: dict) -> str:
        if "command" in config and "args" in config:
            return "stdio"
        elif "url" in config:
            return "sse"
        else:
            raise ValueError("Unknown transport type")

    def prepare_configs(self):
        result = {}
        for name, config in self.configs.items():
            try:
                config["transport"] = self.detect_transport(config)
                result[name] = config
            except Exception as e:
                logger.warning(f"Skipping invalid config '{name}': {e}")
        return result