"""Configuration management for HarnessGenJ-dev."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field


class LLMConfig(BaseModel):
    """LLM provider configuration."""

    provider: str = "anthropic"
    model: str = "claude-sonnet-4-6"
    api_key: str = ""
    base_url: str | None = None
    max_tokens: int = 4096
    temperature: float = 0.1
    # Retry configuration
    max_retries: int = 3
    retry_base_delay: float = 1.0
    retry_max_delay: float = 60.0


class ToolConfig(BaseModel):
    """Tool configuration."""

    enabled_tools: list[str] = Field(default_factory=lambda: [
        "read_file", "write_file", "edit_file", "search_code",
        "run_command", "run_test", "git_ops",
    ])
    default_timeout: int = 30


class WorkflowConfig(BaseModel):
    """Workflow configuration."""

    default_pipeline: str = "develop"
    max_iterations: int = 20
    adversarial_cycles: int = 3


class AppConfig(BaseModel):
    """Main application configuration."""

    llm: LLMConfig = Field(default_factory=LLMConfig)
    tools: ToolConfig = Field(default_factory=ToolConfig)
    workflow: WorkflowConfig = Field(default_factory=WorkflowConfig)
    project_root: Path = Path(".")

    @classmethod
    def default_config_path(cls) -> Path:
        """Return the default configuration file path."""
        return Path.home() / ".hgj-dev" / "config.yaml"

    @classmethod
    def load(cls, path: Path | None = None) -> AppConfig:
        """Load configuration from YAML file."""
        import yaml  # type: ignore[import-untyped]

        config_path = Path(path) if path else cls.default_config_path()
        if config_path.exists():
            try:
                with open(config_path, encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                # Convert string project_root back to Path
                if "project_root" in data and isinstance(data["project_root"], str):
                    data["project_root"] = Path(data["project_root"])
                return cls.model_validate(data)
            except Exception:
                return cls()
        return cls()

    def save(self, path: Path | None = None) -> None:
        """Save configuration to YAML file."""
        import yaml  # type: ignore[import-untyped]

        config_path = Path(path) if path else self.default_config_path()
        config_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert Path objects to strings for YAML compatibility
        data = self.model_dump()
        if "project_root" in data:
            data["project_root"] = str(data["project_root"])

        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False)
