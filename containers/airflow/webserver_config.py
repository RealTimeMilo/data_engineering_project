"""
Airflow web-server configuration for the EC2 (docker-compose) Airflow.

Adds **WorkOS AuthKit** single sign-on to the Airflow UI through the Flask
AppBuilder (FAB) auth manager. When WorkOS is not configured it falls back to
the default local database auth, so the existing ``airflow`` / ``airflow``
login keeps working out of the box.

Enable SSO by setting (shell env, ``.env``, or SSM Parameter Store):

    WORKOS_CLIENT_ID          AuthKit application client id
    WORKOS_CLIENT_SECRET      AuthKit application client secret

Optional:

    WORKOS_USE_OIDC           "true" to use the OIDC endpoints on the AuthKit
                              domain instead of WorkOS's generic endpoints.
    WORKOS_AUTHKIT_DOMAIN     e.g. https://your-app.authkit.app (required when
                              WORKOS_USE_OIDC=true)
    WORKOS_SSO_PROVIDER_NAME  provider id used in the callback URL (default: workos)
    WORKOS_DEFAULT_ROLE       FAB role granted to new users (default: Viewer)
    WORKOS_ADMIN_EMAILS       comma-separated emails granted the Admin role

Redirect URI to register on the WorkOS AuthKit application:

    <AIRFLOW__API__BASE_URL>/auth/oauth-authorized/<WORKOS_SSO_PROVIDER_NAME>

Note: WorkOS requires the redirect URI to be HTTPS, except ``http://127.0.0.1``.

This file is mounted into the EC2 Airflow by docker-compose
(see ``docker-compose.yml``); the ECS Airflow image is not affected.
"""

import base64
import json
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

# Map WorkOS role slugs (from the session token's role/roles claim) onto Airflow
# (FAB) roles. Override with WORKOS_ROLE_MAPPING as a JSON dict, e.g.
#   WORKOS_ROLE_MAPPING={"admin":["Admin"],"engineer":["Op"],"member":["Viewer"]}
_DEFAULT_ROLE_MAPPING = {
    "admin": ["Admin"],
    "op": ["Op"],
    "user": ["User"],
    "viewer": ["Viewer"],
    "member": ["Viewer"],
}
try:
    ROLE_MAPPING = json.loads(os.getenv("WORKOS_ROLE_MAPPING") or "null") or _DEFAULT_ROLE_MAPPING
except ValueError:
    ROLE_MAPPING = _DEFAULT_ROLE_MAPPING


def _jwt_claims(token: str) -> dict:
    """Decode a JWT payload without signature verification.

    The token is received directly from WorkOS over TLS, so we only read it to
    map WorkOS roles onto Airflow roles.
    """
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload.encode()))
    except Exception:  # noqa: BLE001
        return {}


def _workos_roles(response) -> list:
    """WorkOS role slugs from the token response (access-token role/roles claim)."""
    if not isinstance(response, dict):
        return []
    token = response.get("access_token")
    claims = _jwt_claims(token) if token else {}
    roles = claims.get("roles")
    if not roles and claims.get("role"):
        roles = [claims["role"]]
    return [str(role) for role in (roles or []) if role]

# WorkOS exposes AuthKit two ways:
#   * generic: https://api.workos.com/user_management/{authorize,authenticate}
#              (accepts the environment's client_id directly - the default)
#   * OIDC:    https://<authkit_domain>/oauth2/{authorize,token,userinfo}
#              (opt in with WORKOS_USE_OIDC=true; requires the domain to know
#               the client)
USE_OIDC = os.getenv("WORKOS_USE_OIDC", "false").strip().lower() in (
    "1", "true", "yes", "on",
)

# Note: the proxy fix is enabled via the Airflow config in docker-compose.yml
# (AIRFLOW__FAB__ENABLE_PROXY_FIX / PROXY_FIX_X_PROTO / PROXY_FIX_X_HOST), which
# makes FAB apply werkzeug's ProxyFix so external URLs (the OAuth callback) are
# built as https://<external host> instead of http://<internal host>.

# Security: do not keep users signed in across browser sessions. FAB reads
# SESSION_PERMANENT from the Flask config; False makes the session cookie a
# browser-session cookie (cleared when the browser closes), so users sign in
# again each session instead of getting a 30-day persistent cookie.
SESSION_PERMANENT = False

WORKOS_ENABLED = bool(CLIENT_ID and CLIENT_SECRET) and (
    AUTHKIT_DOMAIN if USE_OIDC else True
)

if WORKOS_ENABLED:
    AUTH_TYPE = AUTH_OAUTH
    AUTH_USER_REGISTRATION = True
    AUTH_USER_REGISTRATION_ROLE = DEFAULT_ROLE
    AUTH_ROLES_SYNC_AT_LOGIN = True
    # Keys are WorkOS role slugs returned in role_keys (see get_oauth_user_info).
    AUTH_ROLES_MAPPING = ROLE_MAPPING

    if USE_OIDC and AUTHKIT_DOMAIN:
        remote_app = {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "server_metadata_url": f"{AUTHKIT_DOMAIN}/.well-known/openid-configuration",
            "api_base_url": f"{AUTHKIT_DOMAIN}/oauth2/",
            "request_token_url": None,
            "client_kwargs": {"scope": "openid profile email"},
        }
    else:
        remote_app = {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            # provider=authkit selects the AuthKit (hosted UI) flow; without a
            # connection selector WorkOS returns invalid_connection_selector.
            "authorize_url": "https://api.workos.com/user_management/authorize?provider=authkit",
            "access_token_url": "https://api.workos.com/user_management/authenticate",
            "api_base_url": "https://api.workos.com/user_management/",
            "request_token_url": None,
            # WorkOS's authenticate endpoint expects client_id/client_secret in
            # the request body (not HTTP Basic), so use client_secret_post.
            "client_kwargs": {
                "scope": "openid profile email",
                "token_endpoint_auth_method": "client_secret_post",
            },
        }

    OAUTH_PROVIDERS = [
        {
            "name": PROVIDER_NAME,
            "icon": "fa-key",
            "token_key": "access_token",
            "remote_app": remote_app,
        }
    ]

    class WorkOSSecurityManager(FabAirflowSecurityManagerOverride):
        """Map a WorkOS AuthKit identity onto an Airflow (FAB) user."""

        def get_oauth_user_info(self, provider, response=None):
            if provider != PROVIDER_NAME:
                return super().get_oauth_user_info(provider, response)

            # Generic flow: WorkOS returns the user on the token response.
            data = {}
            if isinstance(response, dict):
                data = response.get("user") or {}
            # OIDC flow: fetch the userinfo document for the issued token.
            if not data:
                remote = self.appbuilder.sm.oauth_remotes[provider]
                data = remote.get("userinfo").json()

            email = (data.get("email") or "").lower()
            # Airflow roles follow the user's WorkOS role(s); an email in
            # WORKOS_ADMIN_EMAILS is always Admin. Unknown WorkOS roles fall back
            # to WORKOS_DEFAULT_ROLE.
            workos_roles = _workos_roles(response)
            if email and email in ADMIN_EMAILS:
                role_keys = ["Admin"]
            else:
                mapped = [role for role in workos_roles if role in ROLE_MAPPING]
                role_keys = mapped or [DEFAULT_ROLE]

            return {
                # Email is stable; the WorkOS user id changes on re-signup, which
                # would make FAB try to insert a new row and hit the email unique
                # constraint. Key the username on email instead.
                "username": "workos_" + (email or data.get("id") or data.get("sub") or "user"),
                "email": email,
                "first_name": data.get("first_name") or data.get("given_name") or "",
                "last_name": data.get("last_name") or data.get("family_name") or "",
                "role_keys": role_keys,
            }

    SECURITY_MANAGER_CLASS = WorkOSSecurityManager

else:
    # WorkOS not configured -> keep the default local database authentication.
    AUTH_TYPE = AUTH_DB
