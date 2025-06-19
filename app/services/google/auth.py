"""
Google API Authentication Manager

Handles OAuth 2.0 authentication for Google APIs following FastAPI best practices.
Integrates with the existing configuration and dependency injection patterns.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from pydantic import BaseModel

from app.core.config import Settings

logger = logging.getLogger(__name__)


class GoogleCredentials(BaseModel):
    """Pydantic model for Google credentials."""

    access_token: str
    refresh_token: Optional[str] = None
    token_uri: str
    client_id: str
    client_secret: str
    scopes: List[str]
    expiry: Optional[str] = None


class GoogleAuthManager:
    """
    Manages OAuth 2.0 authentication for Google APIs.

    Follows FastAPI dependency injection patterns and integrates with
    the existing configuration system.
    """

    def __init__(self, settings: Settings):
        """Initialize the Google Auth Manager."""
        self.settings = settings
        self.credentials: Optional[Credentials] = None
        self._validate_configuration()

    def _validate_configuration(self) -> None:
        """Validate that necessary configuration is present."""
        secrets_file = Path(self.settings.GOOGLE_CLIENT_SECRETS_FILE)
        if not secrets_file.exists():
            logger.warning(
                f"Google client secrets file not found at {secrets_file}. "
                "OAuth flow will not be available."
            )

    def _get_client_secrets(self) -> Dict[str, Any]:
        """Load client secrets from configuration file."""
        secrets_file = Path(self.settings.GOOGLE_CLIENT_SECRETS_FILE)

        if not secrets_file.exists():
            raise FileNotFoundError(
                f"Google client secrets file not found at {secrets_file}. "
                "Please ensure the client_secrets.json file is present."
            )

        try:
            with open(secrets_file, "r") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in client secrets file: {e}")

    def create_oauth_flow(self, redirect_uri: str) -> Flow:
        """
        Create OAuth flow for user authentication.

        Args:
            redirect_uri: The URI to redirect to after authentication

        Returns:
            Google OAuth Flow instance
        """
        try:
            flow = Flow.from_client_secrets_file(
                self.settings.GOOGLE_CLIENT_SECRETS_FILE,
                scopes=self.settings.all_google_scopes,
                redirect_uri=redirect_uri,
            )
            return flow
        except Exception as e:
            logger.error(f"Failed to create OAuth flow: {e}")
            raise

    def get_authorization_url(self, redirect_uri: str) -> tuple[str, str]:
        """
        Get the authorization URL for OAuth flow.

        Args:
            redirect_uri: The URI to redirect to after authentication

        Returns:
            Tuple of (authorization_url, state)
        """
        flow = self.create_oauth_flow(redirect_uri)

        authorization_url, state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",  # Force consent to get refresh token
        )

        return authorization_url, state

    def exchange_code_for_credentials(
        self, authorization_code: str, redirect_uri: str
    ) -> Credentials:
        """
        Exchange authorization code for credentials.

        Args:
            authorization_code: The authorization code from OAuth callback
            redirect_uri: The redirect URI used in the initial flow

        Returns:
            Google credentials object
        """
        flow = self.create_oauth_flow(redirect_uri)

        try:
            flow.fetch_token(code=authorization_code)
            self.credentials = flow.credentials

            # Save credentials for future use
            self._save_credentials(self.credentials)

            return self.credentials
        except Exception as e:
            logger.error(f"Failed to exchange code for credentials: {e}")
            raise

    def load_credentials(self) -> Optional[Credentials]:
        """
        Load saved credentials from file.

        Returns:
            Google credentials if available, None otherwise
        """
        credentials_file = Path(self.settings.GOOGLE_CREDENTIALS_FILE)

        if not credentials_file.exists():
            return None

        try:
            with open(credentials_file, "r") as f:
                cred_data = json.load(f)

            credentials = Credentials(
                token=cred_data["access_token"],
                refresh_token=cred_data.get("refresh_token"),
                token_uri=cred_data["token_uri"],
                client_id=cred_data["client_id"],
                client_secret=cred_data["client_secret"],
                scopes=cred_data["scopes"],
            )

            # Refresh if needed
            if credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
                self._save_credentials(credentials)

            self.credentials = credentials
            return credentials

        except Exception as e:
            logger.error(f"Failed to load credentials: {e}")
            return None

    def _save_credentials(self, credentials: Credentials) -> None:
        """Save credentials to file."""
        credentials_file = Path(self.settings.GOOGLE_CREDENTIALS_FILE)
        credentials_file.parent.mkdir(parents=True, exist_ok=True)

        cred_data = {
            "access_token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": credentials.scopes,
        }

        try:
            with open(credentials_file, "w") as f:
                json.dump(cred_data, f, indent=2)
            logger.info("Credentials saved successfully")
        except Exception as e:
            logger.error(f"Failed to save credentials: {e}")

    def get_valid_credentials(self) -> Optional[Credentials]:
        """
        Get valid credentials, refreshing if necessary.

        Returns:
            Valid Google credentials or None if not available
        """
        if not self.credentials:
            self.credentials = self.load_credentials()

        if not self.credentials:
            return None

        # Check if credentials are expired and can be refreshed
        if self.credentials.expired:
            if self.credentials.refresh_token:
                try:
                    logger.info("Refreshing expired credentials...")
                    self.credentials.refresh(Request())
                    self._save_credentials(self.credentials)
                    logger.info("Credentials refreshed successfully")
                except Exception as e:
                    logger.error(f"Failed to refresh credentials: {e}")
                    # Clear invalid credentials to force re-authentication
                    self.credentials = None
                    # Remove saved credentials file since they're invalid
                    try:
                        credentials_file = Path(self.settings.GOOGLE_CREDENTIALS_FILE)
                        if credentials_file.exists():
                            credentials_file.unlink()
                            logger.info("Removed invalid credentials file")
                    except Exception:
                        pass
                    return None
            else:
                logger.warning("Credentials expired but no refresh token available")
                self.credentials = None
                return None

        # Validate credentials are still valid
        if not self.credentials.valid:
            logger.warning("Credentials are not valid")
            self.credentials = None
            return None

        return self.credentials

    def revoke_credentials(self) -> bool:
        """
        Revoke current credentials.

        Returns:
            True if revocation was successful
        """
        if not self.credentials:
            return True

        try:
            # Revoke the credentials
            self.credentials.revoke(Request())

            # Remove saved credentials file
            credentials_file = Path(self.settings.GOOGLE_CREDENTIALS_FILE)
            if credentials_file.exists():
                credentials_file.unlink()

            self.credentials = None
            logger.info("Credentials revoked successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to revoke credentials: {e}")
            return False

    def is_authenticated(self) -> bool:
        """Check if user is authenticated with valid credentials."""
        credentials = self.get_valid_credentials()
        return credentials is not None and not credentials.expired

    def get_credentials_info(self) -> Optional[Dict[str, Any]]:
        """Get information about current credentials."""
        credentials = self.get_valid_credentials()
        if not credentials:
            return None

        return {
            "scopes": credentials.scopes,
            "client_id": credentials.client_id,
            "expired": credentials.expired,
            "has_refresh_token": bool(credentials.refresh_token),
        }
