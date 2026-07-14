import json
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from app.domain.errors import ExternalServiceError


class LocalSecretStore:
    def __init__(self, data_dir: str | Path) -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.key_path = self.data_dir / ".model-secrets.key"
        self.data_path = self.data_dir / "model-secrets.json"
        self._fernet = Fernet(self._load_or_create_key())

    def set(self, reference: str, secret: str) -> None:
        data = self._read()
        data[reference] = self._fernet.encrypt(secret.encode("utf-8")).decode("ascii")
        self.data_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def get(self, reference: str) -> str | None:
        token = self._read().get(reference)
        if not token:
            return None
        try:
            return self._fernet.decrypt(token.encode("ascii")).decode("utf-8")
        except (InvalidToken, ValueError) as exc:
            raise ExternalServiceError("本地模型密钥无法解密") from exc

    def delete(self, reference: str) -> None:
        data = self._read()
        if reference in data:
            del data[reference]
            self.data_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )

    def has(self, reference: str) -> bool:
        return reference in self._read()

    def _load_or_create_key(self) -> bytes:
        if self.key_path.exists():
            return self.key_path.read_bytes().strip()
        key = Fernet.generate_key()
        self.key_path.write_bytes(key)
        return key

    def _read(self) -> dict[str, str]:
        if not self.data_path.exists():
            return {}
        try:
            value = json.loads(self.data_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise ExternalServiceError("本地模型密钥文件不可用") from exc
        return value if isinstance(value, dict) else {}
