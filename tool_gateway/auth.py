import os


class SecretStore:
    def has(self, name: str) -> bool:
        return bool(os.environ.get(name, ""))

    def get_for_executor(self, name: str) -> str:
        return os.environ.get(name, "")

    def describe(self, name: str) -> dict:
        return {"name": name, "configured": self.has(name)}
