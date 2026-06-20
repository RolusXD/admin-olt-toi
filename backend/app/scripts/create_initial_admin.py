import argparse
import getpass

from app.core.security import hash_password


def build_admin_environment(username: str, password: str, confirmation: str) -> tuple[str, str]:
    normalized_username = username.strip()
    if not normalized_username:
        raise ValueError("Admin username is required")
    if len(password) < 12:
        raise ValueError("Admin password must contain at least 12 characters")
    if password != confirmation:
        raise ValueError("Passwords do not match")
    return normalized_username, hash_password(password)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate environment values for the initial administrator")
    parser.add_argument("--username", help="Administrator username; prompted when omitted")
    args = parser.parse_args()

    username = args.username or input("Admin username: ")
    password = getpass.getpass("Admin password: ")
    confirmation = getpass.getpass("Confirm admin password: ")

    try:
        normalized_username, password_hash = build_admin_environment(username, password, confirmation)
    except ValueError as exc:
        parser.error(str(exc))

    print("Add these values to your local .env file (never commit that file):")
    print(f"ADMIN_USERNAME={normalized_username}")
    print(f"ADMIN_PASSWORD_HASH={password_hash}")


if __name__ == "__main__":
    main()
