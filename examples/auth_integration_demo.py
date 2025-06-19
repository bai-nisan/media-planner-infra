#!/usr/bin/env python3
"""
Auth Integration Demo

Demonstrates how to use the enhanced authentication endpoints
for Google credential management with Supabase Vault storage.
"""

import asyncio
import httpx
import json
from datetime import datetime, timedelta
from typing import Dict, Any


class AuthDemo:
    """Demo client for testing auth endpoints."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = httpx.AsyncClient()
        self.access_token = None
    
    async def authenticate(self, username: str = "admin", password: str = "admin123") -> str:
        """Get access token for API calls."""
        print(f"🔐 Authenticating as {username}...")
        
        response = await self.session.post(
            f"{self.base_url}/api/v1/auth/token",
            data={
                "username": username,
                "password": password,
                "scope": "read write ai:execute external:write external:read admin"
            }
        )
        
        if response.status_code == 200:
            token_data = response.json()
            self.access_token = token_data["access_token"]
            print(f"✅ Authentication successful! Token expires in {token_data['expires_in']} seconds")
            return self.access_token
        else:
            print(f"❌ Authentication failed: {response.text}")
            raise Exception("Authentication failed")
    
    @property
    def headers(self) -> Dict[str, str]:
        """Get authorization headers."""
        if not self.access_token:
            raise Exception("Not authenticated - call authenticate() first")
        return {"Authorization": f"Bearer {self.access_token}"}
    
    async def check_health(self):
        """Check auth service health."""
        print("\n🏥 Checking auth service health...")
        
        response = await self.session.get(f"{self.base_url}/api/v1/auth/health")
        
        if response.status_code == 200:
            health_data = response.json()
            print(f"✅ Auth service healthy: {health_data['service']} v{health_data['version']}")
            print("📋 Available endpoints:")
            for category, endpoints in health_data["endpoints"].items():
                if isinstance(endpoints, dict):
                    print(f"  {category}:")
                    for action, endpoint in endpoints.items():
                        print(f"    {action}: {endpoint}")
                else:
                    print(f"  {category}: {endpoints}")
        else:
            print(f"❌ Health check failed: {response.text}")
    
    async def store_google_credentials(self, service_id: str, tenant_id: str = "default"):
        """Store sample Google credentials."""
        print(f"\n💾 Storing Google credentials for service '{service_id}'...")
        
        # Sample credentials (in production, these would come from OAuth flow)
        credentials_data = {
            "tenant_id": tenant_id,
            "provider_token": "ya29.sample_access_token_from_oauth",
            "provider_refresh_token": "1//sample_refresh_token",
            "user_email": "user@example.com"
        }
        
        response = await self.session.post(
            f"{self.base_url}/api/v1/auth/credentials/google/{service_id}",
            json=credentials_data,
            headers=self.headers
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Credentials stored successfully for {result['service_id']} (tenant: {result['tenant_id']})")
        else:
            print(f"❌ Failed to store credentials: {response.text}")
    
    async def check_credential_status(self, service_id: str, tenant_id: str = "default"):
        """Check credential status."""
        print(f"\n🔍 Checking credential status for service '{service_id}'...")
        
        response = await self.session.get(
            f"{self.base_url}/api/v1/auth/credentials/google/{service_id}/status",
            params={"tenant_id": tenant_id},
            headers=self.headers
        )
        
        if response.status_code == 200:
            status = response.json()
            print(f"📊 Credential Status:")
            print(f"  Has credentials: {status['has_credentials']}")
            print(f"  Valid: {status['credentials_valid']}")
            print(f"  Expired: {status.get('is_expired', 'Unknown')}")
            print(f"  Expires in: {status.get('expires_in_seconds', 'Unknown')} seconds")
            print(f"  Scopes: {', '.join(status['scopes'])}")
            print(f"  User email: {status.get('user_email', 'Not specified')}")
        else:
            print(f"❌ Failed to check status: {response.text}")
    
    async def list_credentials(self, tenant_id: str = "default"):
        """List all credentials for a tenant."""
        print(f"\n📋 Listing credentials for tenant '{tenant_id}'...")
        
        response = await self.session.get(
            f"{self.base_url}/api/v1/auth/credentials/google",
            params={"tenant_id": tenant_id},
            headers=self.headers
        )
        
        if response.status_code == 200:
            credentials = response.json()
            print(f"📊 Found {len(credentials)} credential(s):")
            for cred in credentials:
                print(f"  Service: {cred['service_id']}")
                print(f"  Tenant: {cred['tenant_id']}")
                print(f"  Type: {cred['credential_type']}")
                print(f"  Created: {cred['created_at']}")
                print(f"  Description: {cred.get('description', 'No description')}")
                print()
        else:
            print(f"❌ Failed to list credentials: {response.text}")
    
    async def refresh_credentials(self, service_id: str, tenant_id: str = "default"):
        """Refresh credentials with new tokens."""
        print(f"\n🔄 Refreshing credentials for service '{service_id}'...")
        
        # Sample refreshed credentials
        refresh_data = {
            "tenant_id": tenant_id,
            "provider_token": "ya29.new_refreshed_access_token",
            "provider_refresh_token": "1//new_refresh_token_if_provided",
            "user_email": "user@example.com"
        }
        
        response = await self.session.post(
            f"{self.base_url}/api/v1/auth/credentials/google/{service_id}/refresh",
            json=refresh_data,
            params={"tenant_id": tenant_id},
            headers=self.headers
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Credentials refreshed successfully: {result['message']}")
        else:
            print(f"❌ Failed to refresh credentials: {response.text}")
    
    async def retrieve_credentials(self, service_id: str, tenant_id: str = "default"):
        """Retrieve stored credentials (for testing - be careful with sensitive data)."""
        print(f"\n📥 Retrieving credentials for service '{service_id}'...")
        
        response = await self.session.get(
            f"{self.base_url}/api/v1/auth/credentials/google/{service_id}",
            params={"tenant_id": tenant_id},
            headers=self.headers
        )
        
        if response.status_code == 200:
            cred_data = response.json()
            print(f"✅ Retrieved credentials for {cred_data['service_id']}")
            print(f"  Stored at: {cred_data['stored_at']}")
            print(f"  Expires at: {cred_data.get('expires_at', 'Not specified')}")
            # Don't print actual credential values for security
            print(f"  Has access token: {'access_token' in cred_data['credentials']}")
            print(f"  Has refresh token: {'refresh_token' in cred_data['credentials']}")
        else:
            print(f"❌ Failed to retrieve credentials: {response.text}")
    
    async def revoke_credentials(self, service_id: str, tenant_id: str = "default"):
        """Revoke and delete credentials."""
        print(f"\n🗑️ Revoking credentials for service '{service_id}'...")
        
        response = await self.session.delete(
            f"{self.base_url}/api/v1/auth/credentials/google/{service_id}",
            params={"tenant_id": tenant_id},
            headers=self.headers
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Credentials revoked successfully: {result['message']}")
        else:
            print(f"❌ Failed to revoke credentials: {response.text}")
    
    async def test_service_registry(self):
        """Test service registry endpoints."""
        print(f"\n🏢 Testing service registry...")
        
        response = await self.session.get(
            f"{self.base_url}/api/v1/auth/services",
            headers=self.headers
        )
        
        if response.status_code == 200:
            registry = response.json()
            print(f"📊 Found {registry['total_count']} registered service(s):")
            for service_id, service_info in registry['services'].items():
                print(f"  {service_id}: {service_info['service_name']}")
                print(f"    Type: {service_info['service_type']}")
                print(f"    Permissions: {', '.join(service_info['permissions'])}")
        else:
            print(f"❌ Failed to get service registry: {response.text}")
    
    async def close(self):
        """Close the HTTP session."""
        await self.session.aclose()


async def main():
    """Run the auth integration demo."""
    print("🚀 Auth Integration Demo")
    print("=" * 50)
    
    demo = AuthDemo()
    
    try:
        # Step 1: Check health
        await demo.check_health()
        
        # Step 2: Authenticate
        await demo.authenticate()
        
        # Step 3: Test service registry
        await demo.test_service_registry()
        
        # Step 4: Credential management workflow
        service_id = "workspace_agent"
        tenant_id = "demo_tenant"
        
        # Store credentials
        await demo.store_google_credentials(service_id, tenant_id)
        
        # Check status
        await demo.check_credential_status(service_id, tenant_id)
        
        # List all credentials
        await demo.list_credentials(tenant_id)
        
        # Retrieve credentials (testing only)
        await demo.retrieve_credentials(service_id, tenant_id)
        
        # Refresh credentials
        await demo.refresh_credentials(service_id, tenant_id)
        
        # Check status after refresh
        await demo.check_credential_status(service_id, tenant_id)
        
        # Clean up - revoke credentials
        await demo.revoke_credentials(service_id, tenant_id)
        
        # Verify cleanup
        await demo.check_credential_status(service_id, tenant_id)
        
        print("\n🎉 Demo completed successfully!")
        
    except Exception as e:
        print(f"\n💥 Demo failed: {str(e)}")
    
    finally:
        await demo.close()


if __name__ == "__main__":
    asyncio.run(main()) 