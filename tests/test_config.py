from pathlib import Path

from app.config import Settings


def test_allowed_origins_supports_comma_separated_env(tmp_path: Path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "APP_ENV=dev",
                "API_KEY=test-key",
                "ALLOWED_ORIGINS=http://127.0.0.1:3000,http://localhost:3000",
            ]
        ),
        encoding="utf-8",
    )

    settings = Settings(_env_file=str(env_path))
    assert settings.allowed_origins == ["http://127.0.0.1:3000", "http://localhost:3000"]
