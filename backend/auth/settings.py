import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SORT_TESTER_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    argon2_time_cost: int = 3
    argon2_memory_cost: int = 65536
    argon2_parallelism: int = 1
    login_id_total_groups: int = 4
    login_id_group_size: int = 4
    login_id_alphabet: str = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
    cookie_secure: bool = False
    session_ttl_seconds: int = 8 * 60 * 60

    @property
    def login_id_length(self) -> int:
        return self.login_id_total_groups * self.login_id_group_size


def get_auth_settings() -> AuthSettings:
    return AuthSettings()
