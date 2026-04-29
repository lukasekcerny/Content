import keyring

SERVICE_NAME = "ContentUploader"


def save_credentials(platform_id: str, email: str, password: str):
    keyring.set_password(SERVICE_NAME, f"{platform_id}_email", email)
    keyring.set_password(SERVICE_NAME, f"{platform_id}_password", password)


def get_credentials(platform_id: str) -> tuple[str, str] | tuple[None, None]:
    email = keyring.get_password(SERVICE_NAME, f"{platform_id}_email")
    password = keyring.get_password(SERVICE_NAME, f"{platform_id}_password")
    if email and password:
        return email, password
    return None, None


def delete_credentials(platform_id: str):
    try:
        keyring.delete_password(SERVICE_NAME, f"{platform_id}_email")
    except keyring.errors.PasswordDeleteError:
        pass
    try:
        keyring.delete_password(SERVICE_NAME, f"{platform_id}_password")
    except keyring.errors.PasswordDeleteError:
        pass


def save_api_token(platform_id: str, token_type: str, token: str):
    keyring.set_password(SERVICE_NAME, f"{platform_id}_{token_type}", token)


def get_api_token(platform_id: str, token_type: str) -> str | None:
    return keyring.get_password(SERVICE_NAME, f"{platform_id}_{token_type}")
