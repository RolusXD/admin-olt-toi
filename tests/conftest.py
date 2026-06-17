import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"

if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

fake_telnetlib = types.ModuleType("telnetlib")
fake_telnetlib.Telnet = object
sys.modules.setdefault("telnetlib", fake_telnetlib)

fake_fernet_module = types.ModuleType("cryptography.fernet")


class FakeFernet:
    def __init__(self, *_args, **_kwargs):
        pass

    def encrypt(self, value: bytes) -> bytes:
        return value

    def decrypt(self, value: bytes) -> bytes:
        return value


fake_fernet_module.Fernet = FakeFernet
fake_crypto_module = types.ModuleType("cryptography")
fake_crypto_module.fernet = fake_fernet_module
sys.modules.setdefault("cryptography", fake_crypto_module)
sys.modules.setdefault("cryptography.fernet", fake_fernet_module)
