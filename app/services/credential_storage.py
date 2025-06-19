"""
Credential Storage Service using Supabase Vault for secure credential management.

This service provides encrypted storage and retrieval of OAuth credentials
for Google API integrations used by LangGraph agents.
"""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from app.core.config import get_settings
from supabase import Client, create_client

logger = logging.getLogger(__name__)


class CredentialType(str, Enum):
    """Supported credential types."""

    GOOGLE_OAUTH = "google_oauth"
    GOOGLE_SERVICE_ACCOUNT = "google_service_account"
    MICROSOFT_OAUTH = "microsoft_oauth"
    META_OAUTH = "meta_oauth"
    TWITTER_OAUTH = "twitter_oauth"


@dataclass
class GoogleOAuthCredentials:
    """Structured Google OAuth credentials."""

    access_token: str
    refresh_token: Optional[str]
    token_uri: str
    client_id: str
    client_secret: str
    scopes: List[str]
    expires_at: Optional[datetime] = None
    user_email: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        data = {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_uri": self.token_uri,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scopes": self.scopes,
            "user_email": self.user_email,
        }
        if self.expires_at:
            data["expires_at"] = self.expires_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GoogleOAuthCredentials":
        """Create from dictionary."""
        expires_at = None
        if data.get("expires_at"):
            expires_at = datetime.fromisoformat(data["expires_at"])

        return cls(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            token_uri=data["token_uri"],
            client_id=data["client_id"],
            client_secret=data["client_secret"],
            scopes=data.get("scopes", []),
            expires_at=expires_at,
            user_email=data.get("user_email"),
        )

    def is_expired(self) -> bool:
        """Check if credentials are expired."""
        if not self.expires_at:
            return False
        return datetime.utcnow() >= self.expires_at

    def expires_in_seconds(self) -> Optional[int]:
        """Get seconds until expiration."""
        if not self.expires_at:
            return None
        delta = self.expires_at - datetime.utcnow()
        return max(0, int(delta.total_seconds()))

    def is_valid(self) -> bool:
        """Basic validation of credential structure."""
        return bool(self.access_token and self.token_uri and self.scopes)


class SupabaseCredentialStorage:
    """Credential storage service using Supabase Vault."""

    def __init__(self):
        self.settings = get_settings()
        self._client: Optional[Client] = None

    @property
    def client(self) -> Client:
        """Get Supabase client (lazy initialization)."""
        if not self._client:
            self._client = create_client(
                self.settings.SUPABASE_URL, self.settings.SUPABASE_SERVICE_ROLE_KEY
            )
        return self._client

    def _get_credential_name(
        self, service_id: str, tenant_id: str, credential_type: CredentialType
    ) -> str:
        """Generate unique credential name for vault storage."""
        return f"cred_{service_id}_{tenant_id}_{credential_type.value}"

    def _validate_inputs(self, service_id: str, tenant_id: str) -> None:
        """Validate input parameters."""
        if not service_id or not service_id.strip():
            raise ValueError("service_id cannot be empty")
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id cannot be empty")
        if len(service_id) > 50:
            raise ValueError("service_id too long (max 50 characters)")
        if len(tenant_id) > 50:
            raise ValueError("tenant_id too long (max 50 characters)")

    async def store_google_credentials(
        self,
        service_id: str,
        tenant_id: str,
        credentials: GoogleOAuthCredentials,
        stored_by: str,
    ) -> bool:
        """
        Store Google OAuth credentials in Supabase Vault.

        Args:
            service_id: Service identifier (e.g., "workspace_agent")
            tenant_id: Tenant identifier for isolation
            credentials: Google OAuth credentials to store
            stored_by: User/service that stored the credentials

        Returns:
            True if stored successfully, False otherwise
        """
        try:
            self._validate_inputs(service_id, tenant_id)

            if not credentials.is_valid():
                logger.error(
                    f"Invalid credentials structure for {service_id}/{tenant_id}"
                )
                return False

            credential_name = self._get_credential_name(
                service_id, tenant_id, CredentialType.GOOGLE_OAUTH
            )

            # Prepare credential data with metadata
            credential_data = {
                **credentials.to_dict(),
                "stored_at": datetime.utcnow().isoformat(),
                "stored_by": stored_by,
                "service_id": service_id,
                "tenant_id": tenant_id,
                "credential_type": CredentialType.GOOGLE_OAUTH.value,
                "version": "1.0",
            }

            # Store in Vault using RPC function
            result = self.client.rpc(
                "vault.create_secret",
                {
                    "secret": json.dumps(credential_data),
                    "name": credential_name,
                    "description": f"Google OAuth credentials for {service_id} (tenant: {tenant_id})",
                },
            ).execute()

            if result.data:
                logger.info(
                    f"Successfully stored Google credentials for {service_id}/{tenant_id}"
                )
                return True
            else:
                logger.error(f"Failed to store credentials: {result}")
                return False

        except ValueError as e:
            logger.error(
                f"Validation error storing credentials for {service_id}/{tenant_id}: {str(e)}"
            )
            return False
        except Exception as e:
            logger.error(
                f"Error storing Google credentials for {service_id}/{tenant_id}: {str(e)}"
            )
            return False

    async def retrieve_google_credentials(
        self, service_id: str, tenant_id: str
    ) -> Optional[GoogleOAuthCredentials]:
        """
        Retrieve Google OAuth credentials from Supabase Vault.

        Args:
            service_id: Service identifier
            tenant_id: Tenant identifier

        Returns:
            GoogleOAuthCredentials if found, None otherwise
        """
        try:
            self._validate_inputs(service_id, tenant_id)

            credential_name = self._get_credential_name(
                service_id, tenant_id, CredentialType.GOOGLE_OAUTH
            )

            # Query decrypted secrets view
            result = (
                self.client.from_("vault.decrypted_secrets")
                .select("*")
                .eq("name", credential_name)
                .execute()
            )

            if result.data and len(result.data) > 0:
                secret_data = result.data[0]
                credential_data = json.loads(secret_data["secret"])

                logger.info(
                    f"Successfully retrieved Google credentials for {service_id}/{tenant_id}"
                )
                return GoogleOAuthCredentials.from_dict(credential_data)
            else:
                logger.warning(
                    f"No Google credentials found for {service_id}/{tenant_id}"
                )
                return None

        except ValueError as e:
            logger.error(
                f"Validation error retrieving credentials for {service_id}/{tenant_id}: {str(e)}"
            )
            return None
        except Exception as e:
            logger.error(
                f"Error retrieving Google credentials for {service_id}/{tenant_id}: {str(e)}"
            )
            return None

    async def check_credential_status(
        self, service_id: str, tenant_id: str
    ) -> Dict[str, Any]:
        """
        Check the status of stored credentials.

        Returns:
            Dictionary with credential status information
        """
        try:
            self._validate_inputs(service_id, tenant_id)

            credentials = await self.retrieve_google_credentials(service_id, tenant_id)

            if not credentials:
                return {
                    "has_credentials": False,
                    "credentials_valid": False,
                    "expires_at": None,
                    "scopes": [],
                    "is_expired": False,
                    "expires_in_seconds": None,
                }

            is_expired = credentials.is_expired()
            expires_in_seconds = credentials.expires_in_seconds()

            return {
                "has_credentials": True,
                "credentials_valid": credentials.is_valid() and not is_expired,
                "expires_at": credentials.expires_at,
                "scopes": credentials.scopes,
                "is_expired": is_expired,
                "expires_in_seconds": expires_in_seconds,
                "user_email": credentials.user_email,
            }

        except Exception as e:
            logger.error(
                f"Error checking credential status for {service_id}/{tenant_id}: {str(e)}"
            )
            return {
                "has_credentials": False,
                "credentials_valid": False,
                "expires_at": None,
                "scopes": [],
                "is_expired": True,
                "expires_in_seconds": 0,
                "error": str(e),
            }

    async def revoke_credentials(self, service_id: str, tenant_id: str) -> bool:
        """
        Revoke and delete stored credentials.

        Args:
            service_id: Service identifier
            tenant_id: Tenant identifier

        Returns:
            True if revoked successfully, False otherwise
        """
        try:
            self._validate_inputs(service_id, tenant_id)

            credential_name = self._get_credential_name(
                service_id, tenant_id, CredentialType.GOOGLE_OAUTH
            )

            # Delete from vault using RPC function
            result = self.client.rpc(
                "vault.delete_secret", {"name": credential_name}
            ).execute()

            logger.info(f"Revoked Google credentials for {service_id}/{tenant_id}")
            return True

        except Exception as e:
            logger.error(
                f"Error revoking credentials for {service_id}/{tenant_id}: {str(e)}"
            )
            return False

    async def list_credentials(
        self, tenant_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List all stored credentials, optionally filtered by tenant.

        Args:
            tenant_id: Optional tenant filter

        Returns:
            List of credential metadata (without sensitive data)
        """
        try:
            # Query vault secrets metadata
            query = self.client.from_("vault.secrets").select(
                "name, created_at, description"
            )

            if tenant_id:
                # Filter by tenant in credential name pattern
                query = query.like("name", f"cred_%_{tenant_id}_%")
            else:
                # Filter for all credential entries
                query = query.like("name", "cred_%")

            result = query.execute()

            credentials = []
            for secret in result.data:
                # Parse credential name to extract metadata
                name_parts = secret["name"].split("_")
                if len(name_parts) >= 4:
                    credentials.append(
                        {
                            "service_id": name_parts[1],
                            "tenant_id": name_parts[2],
                            "credential_type": name_parts[3],
                            "created_at": secret["created_at"],
                            "description": secret.get("description", ""),
                        }
                    )

            return credentials

        except Exception as e:
            logger.error(f"Error listing credentials: {str(e)}")
            return []

    async def refresh_google_credentials(
        self,
        service_id: str,
        tenant_id: str,
        new_credentials: GoogleOAuthCredentials,
        updated_by: str,
    ) -> bool:
        """
        Update existing credentials with refreshed tokens.

        Args:
            service_id: Service identifier
            tenant_id: Tenant identifier
            new_credentials: Updated credentials
            updated_by: User/service performing the update

        Returns:
            True if updated successfully, False otherwise
        """
        try:
            self._validate_inputs(service_id, tenant_id)

            # First, verify existing credentials exist
            existing = await self.retrieve_google_credentials(service_id, tenant_id)
            if not existing:
                logger.warning(
                    f"No existing credentials to refresh for {service_id}/{tenant_id}"
                )
                return False

            # Preserve original metadata but update tokens
            refreshed_credentials = GoogleOAuthCredentials(
                access_token=new_credentials.access_token,
                refresh_token=new_credentials.refresh_token or existing.refresh_token,
                token_uri=existing.token_uri,
                client_id=existing.client_id,
                client_secret=existing.client_secret,
                scopes=existing.scopes,
                expires_at=new_credentials.expires_at,
                user_email=existing.user_email,
            )

            # Store updated credentials
            return await self.store_google_credentials(
                service_id=service_id,
                tenant_id=tenant_id,
                credentials=refreshed_credentials,
                stored_by=f"{updated_by} (refresh)",
            )

        except Exception as e:
            logger.error(
                f"Error refreshing credentials for {service_id}/{tenant_id}: {str(e)}"
            )
            return False


# Singleton instance
_credential_storage = None


def get_credential_storage() -> SupabaseCredentialStorage:
    """Get singleton credential storage instance."""
    global _credential_storage
    if _credential_storage is None:
        _credential_storage = SupabaseCredentialStorage()
    return _credential_storage
