import base64
import os
import secrets

from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SORT_TESTER_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    session_secret_b64: str = ""
    argon2_time_cost: int = 3
    argon2_memory_cost: int = 65536
    argon2_parallelism: int = 1
    login_id_total_groups: int = 4
    login_id_group_size: int = 4
    login_id_alphabet: str = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
    cookie_secure: bool = False
    session_ttl_seconds: int = 8 * 60 * 60

    @property
    def session_secret_bytes(self) -> bytes:
        if self.session_secret_b64:
            decoded = base64.urlsafe_b64decode(self.session_secret_b64.encode("ascii"))
            if len(decoded) >= 32:
                return decoded
        return secrets.token_bytes(32)

    @property
    def login_id_length(self) -> int:
        return self.login_id_total_groups * self.login_id_group_size


def get_auth_settings() -> AuthSettings:
    return AuthSettings()
