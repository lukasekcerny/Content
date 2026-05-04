import logging

import keyring

logger = logging.getLogger(__name__)

SERVICE_NAME = "ContentUploader"


def save_credentials(platform_id: str, email: str, password: str):
    try:
        keyring.set_password(SERVICE_NAME, f"{platform_id}_email", email)
        keyring.set_password(SERVICE_NAME, f"{platform_id}_password", password)
    except Exception as e:
        logger.error("Failed to save credentials for %s: %s", platform_id, e)


def get_credentials(platform_id: str) -> tuple[str, str] | tuple[None, None]:
    try:
        email = keyring.get_password(SERVICE_NAME, f"{platform_id}_email")
        password = keyring.get_password(SERVICE_NAME, f"{platform_id}_password")
        if email and password:
            return email, password
    except Exception as e:
        logger.error("Failed to read credentials for %s: %s", platform_id, e)
    return None, None


def delete_credentials(platform_id: str):
    try:
        keyring.delete_password(SERVICE_NAME, f"{platform_id}_email")
    except keyring.errors.PasswordDeleteError:
        pass
    except Exception as e:
        logger.error("Failed to delete credentials for %s: %s", platform_id, e)
    try:
        keyring.delete_password(SERVICE_NAME, f"{platform_id}_password")
    except keyring.errors.PasswordDeleteError:
        pass
    except Exception as e:
        logger.error("Failed to delete credentials for %s: %s", platform_id, e)


def save_api_token(platform_id: str, token_type: str, token: str):
    try:
        keyring.set_password(SERVICE_NAME, f"{platform_id}_{token_type}", token)
    except Exception as e:
        logger.error("Failed to save API token for %s/%s: %s", platform_id, token_type, e)


def get_api_token(platform_id: str, token_type: str) -> str | None:
    try:
        return keyring.get_password(SERVICE_NAME, f"{platform_id}_{token_type}")
    except Exception as e:
        logger.error("Failed to read API token for %s/%s: %s", platform_id, token_type, e)
        return None
