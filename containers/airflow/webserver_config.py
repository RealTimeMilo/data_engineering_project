"""
Airflow web-server configuration for the EC2 (docker-compose) Airflow.

Adds **WorkOS AuthKit** single sign-on to the Airflow UI through the Flask
AppBuilder (FAB) auth manager. When WorkOS is not configured it falls back to
the default local database auth, so the existing ``airflow`` / ``airflow``
login keeps working out of the box.

Enable SSO by setting these (shell env, ``.env``, or SSM Parameter Store):

    WORKOS_CLIENT_ID          AuthKit application client id
    WORKOS_CLIENT_SECRET      AuthKit application client secret
    WORKOS_AUTHKIT_DOMAIN     e.g. https://your-app.authkit.app

Optional:

    WORKOS_SSO_PROVIDER_NAME  provider id used in the callback URL (default: workos)
    WORKOS_DEFAULT_ROLE       FAB role granted to new users (default: Viewer)
    WORKOS_ADMIN_EMAILS       comma-separated emails granted the Admin role

Redirect URI to register on the WorkOS AuthKit application:

    <AIRFLOW__API__BASE_URL>/auth/oauth-authorized/<WORKOS_SSO_PROVIDER_NAME>

This file is mounted into the EC2 Airflow by docker-compose
(see ``docker-compose.yml``); the ECS Airflow image is not affected.
"""

import os

from flask_appbuilder.const import AUTH_DB, AUTH_OAUTH

# The security-manager override moved between apache-airflow-providers-fab
# releases; import it defensively.
try:  # providers-fab >= 2.x (Airflow 3)
    from airflow.providers.fab.auth_manager.security_manager.override import (
        FabAirflowSecurityManagerOverride,
    )
except ImportError:  # older layout
    from airflow.providers.fab.auth_manager.security_manager import (  # type: ignore
        FabAirflowSecurityManagerOverride,
    )

PROVIDER_NAME = os.getenv("WORKOS_SSO_PROVIDER_NAME", "workos").strip() or "workos"
CLIENT_ID = os.getenv("WORKOS_CLIENT_ID", "").strip()
CLIENT_SECRET = os.getenv("WORKOS_CLIENT_SECRET", "").strip()
AUTHKIT_DOMAIN = os.getenv("WORKOS_AUTHKIT_DOMAIN", "").strip().rstrip("/")
# Accept a bare AuthKit domain (e.g. my-app.authkit.app) and default to https.
if AUTHKIT_DOMAIN and not AUTHKIT_DOMAIN.startswith(("http://", "https://")):
    AUTHKIT_DOMAIN = f"https://{AUTHKIT_DOMAIN}"
DEFAULT_ROLE = os.getenv("WORKOS_DEFAULT_ROLE", "Viewer").strip() or "Viewer"
ADMIN_EMAILS = {
    email.strip().lower()
    for email in os.getenv("WORKOS_ADMIN_EMAILS", "").split(",")
    if email.strip()
}

WORKOS_ENABLED = bool(CLIENT_ID and CLIENT_SECRET and AUTHKIT_DOMAIN)

if WORKOS_ENABLED:
    AUTH_TYPE = AUTH_OAUTH
    AUTH_USER_REGISTRATION = True
    AUTH_USER_REGISTRATION_ROLE = DEFAULT_ROLE
    AUTH_ROLES_SYNC_AT_LOGIN = True
    AUTH_ROLES_MAPPING = {DEFAULT_ROLE: [DEFAULT_ROLE], "Admin": ["Admin"]}

    OAUTH_PROVIDERS = [
        {
            "name": PROVIDER_NAME,
            "icon": "fa-key",
            "token_key": "access_token",
            "remote_app": {
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                # WorkOS Connect / AuthKit speak standard OIDC discovery.
                "server_metadata_url": f"{AUTHKIT_DOMAIN}/.well-known/openid-configuration",
                "api_base_url": f"{AUTHKIT_DOMAIN}/oauth2/",
                "client_kwargs": {"scope": "openid profile email"},
                "request_token_url": None,
            },
        }
    ]

    class WorkOSSecurityManager(FabAirflowSecurityManagerOverride):
        """Map a WorkOS AuthKit identity onto an Airflow (FAB) user."""

        def get_oauth_user_info(self, provider, response=None):
            if provider != PROVIDER_NAME:
                return super().get_oauth_user_info(provider, response)

            # Fetch the OIDC userinfo document for the freshly issued token.
            remote = self.appbuilder.sm.oauth_remotes[provider]
            data = remote.get("userinfo").json()

            email = (data.get("email") or "").lower()
            role_keys = ["Admin"] if email and email in ADMIN_EMAILS else [DEFAULT_ROLE]

            return {
                "username": "workos_" + (data.get("sub") or email or "user"),
                "email": email,
                "first_name": data.get("given_name") or data.get("first_name") or "",
                "last_name": data.get("family_name") or data.get("last_name") or "",
                "role_keys": role_keys,
            }

    SECURITY_MANAGER_CLASS = WorkOSSecurityManager

else:
    # WorkOS not configured -> keep the default local database authentication.
    AUTH_TYPE = AUTH_DB
