from pwdlib import PasswordHash
from pwdlib.hashers.bcrypt import BcryptHasher

pwd_hasher = PasswordHash([BcryptHasher()])


def hash_password(plain_password: str) -> str:
    """Hash a plain password. Call this on register / password change."""
    return pwd_hasher.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check a plain password against its hash. Call this on login."""
    return pwd_hasher.verify(plain_password, hashed_password)
