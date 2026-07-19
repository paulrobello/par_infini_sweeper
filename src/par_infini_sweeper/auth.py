"""OAuth2 / Auth0 PKCE flow + loopback callback server.

Implements the Authorization Code flow with PKCE (RFC 7636) against an Auth0
tenant, including the loopback HTTP listener that receives the authorization
code redirect and exchanges it for tokens. Used by ``GameState.auth_client``
via ``build_auth_client``.

Design points (see ``docs/ARCHITECTURE.md#oauth2--auth0-flow`` for the full
sequence diagram):

* PKCE ``code_verifier`` is generated per login and passed to both
  ``create_authorization_url`` (derives ``code_challenge = S256``) and
  ``fetch_token`` (redeems it).
* Loopback listener binds to ``127.0.0.1:1999`` with ``SO_REUSEADDR`` so a
  previous process leaving the socket in ``TIME_WAIT`` does not block the
  next launch.
* ``LOOPBACK_AUTHORITY`` is pinned (never reflected from the request ``Host``
  header) so a forged Host cannot inject authority into
  ``parse_authorization_code_response``.
* Callback errors return a generic ``"Authentication failed"`` body; raw
  exception text is logged locally only (SEC-003).
* ``AUTH0_DOMAIN`` / ``AUTH0_CLIENT_ID`` can be overridden via env for local
  development against a test tenant; if ``AUTH0_CLIENT_ID`` is unset,
  ``warn_if_default_auth0_client_id`` prints a one-time stderr warning.
"""

from __future__ import annotations

import http.server
import logging
import os
import secrets
import socketserver
import sys
import threading
import webbrowser
from typing import Any
from urllib.parse import urlparse

import requests
from authlib.integrations.requests_client import OAuth2Session
from authlib.oauth2 import OAuth2Error
from textual.app import App

from par_infini_sweeper import db
from par_infini_sweeper.messages import AuthServerError, ShowURL, WebServerStarted, WebServerStopped

logger = logging.getLogger(__name__)

# Production Auth0 tenant + client ID. Local dev should override BOTH via env
# (e.g. point at a test tenant). See warn_if_default_auth0_client_id() for the
# one-time stderr nudge when AUTH0_CLIENT_ID is unset (ARC-019).
AUTH0_DOMAIN = os.environ.get("AUTH0_DOMAIN", "par-dev.us.auth0.com")
_DEFAULT_AUTH0_CLIENT_ID = "79LqAgzljQjin3dihidWdmLSD7o4CpL5"
AUTH0_CLIENT_ID = os.environ.get("AUTH0_CLIENT_ID", _DEFAULT_AUTH0_CLIENT_ID)
API_AUDIENCE = "PIM"
# ARC-018: loopback callback port. Hardcoded for now (Auth0's allowed callback
# URL list is per-client); SO_REUSEADDR is enabled via ReusableTCPServer below,
# and the port-in-use case is surfaced via AuthServerError instead of crashing.
OAUTH_CALLBACK_PORT = 1999
REDIRECT_URI = f"http://127.0.0.1:{OAUTH_CALLBACK_PORT}/oauth/callback"
# Pinned loopback authority used to build `authorization_response`. We must not
# reflect the request's `Host` header here: a forged Host (e.g. from a malicious
# page redirecting to the loopback listener) would otherwise be passed verbatim
# into authlib's `parse_authorization_code_response`, allowing attacker-controlled
# authority injection. Deriving from REDIRECT_URI keeps the single source of truth.
LOOPBACK_AUTHORITY = urlparse(REDIRECT_URI).netloc

_default_auth0_client_id_warned = False


def warn_if_default_auth0_client_id() -> None:
    """Print a one-time stderr warning when the production Auth0 client ID is
    in use because ``AUTH0_CLIENT_ID`` was not set in the environment.

    ARC-019: the hardcoded default means local dev hits the production auth
    tenant by default. The warning is idempotent (fires at most once per
    process) and routed to stderr so it doesn't pollute the TUI / structured
    stdout. Imported and called from ``__main__.main`` so it only fires for
    real launches, not on every ``import par_infini_sweeper.*``.
    """
    global _default_auth0_client_id_warned
    if _default_auth0_client_id_warned:
        return
    _default_auth0_client_id_warned = True
    if "AUTH0_CLIENT_ID" not in os.environ:
        print(
            "warning: AUTH0_CLIENT_ID not set; using the production Auth0 tenant "
            f"({AUTH0_DOMAIN}). Set AUTH0_CLIENT_ID (and AUTH0_DOMAIN) for local dev.",
            file=sys.stderr,
        )


def build_auth_client(user: dict[str, Any], app: App) -> OAuth2Session:
    """
    Returns a rest client that sends authorization bearer token with requests

    Args:
        user: (dict) User dictionary with token info
        app: (App) Textual app
    """
    token_data = {
        "access_token": user["access_token"] or None,
        "refresh_token": user["refresh_token"] or None,
        "expires_at": user["expires_at"] or None,
        "token_type": "Bearer",
    }

    client = OAuth2Session(
        client_id=AUTH0_CLIENT_ID,
        redirect_uri=REDIRECT_URI,
        scope="openid profile email offline_access",
        token=token_data,
    )
    if client.token:
        # ARC-012: ``is_expired()`` may return True / False / None (unknown
        # when expiry can't be determined). The previous ``in [None, True]``
        # was correct but obscure — spell out "expired OR unknown" so the
        # refresh condition is readable. Refresh only when we have a
        # refresh_token to redeem (offline_access scope).
        token_expired = client.token.is_expired()
        needs_refresh = token_expired is None or token_expired is True
        if needs_refresh and client.token["refresh_token"]:
            try:
                refresh_token_url = f"https://{AUTH0_DOMAIN}/oauth/token"

                new_token = client.refresh_token(
                    url=refresh_token_url,  # Use the correct URL here
                    refresh_token=client.token["refresh_token"],
                )

                client.token = new_token

                user["access_token"] = client.token["access_token"]
                user["refresh_token"] = client.token["refresh_token"]
                user["expires_at"] = client.token["expires_at"]
                db.save_user(user)
                return client
            except (OAuth2Error, requests.RequestException):
                # QA-004: refresh failed (OAuth error from Auth0 or transport
                # failure). Blank out auth info and start fresh. Logged at
                # info — this fires on every cold-start with a stale refresh
                # token, so warning would spam the log.
                logger.info("token refresh failed; clearing auth state", exc_info=True)
                user["access_token"] = ""
                user["refresh_token"] = ""
                user["expires_at"] = 0
                db.save_user(user)
        elif client.token["access_token"]:
            # we have an auth token and its not expired
            return client

    return start_auth_server(client, user, app)


def start_auth_server(client: OAuth2Session, user: dict[str, Any], app: App) -> OAuth2Session:
    """Run the interactive OAuth login: open browser, serve loopback callback, redeem code.

    Generates a per-login PKCE ``code_verifier``, opens the user's browser at
    the Auth0 authorize endpoint, and serves a one-shot HTTP listener on
    ``127.0.0.1:{OAUTH_CALLBACK_PORT}`` that receives the redirect, exchanges
    the authorization code for tokens (passing the same ``code_verifier``),
    and persists them via ``db.save_user``. On callback errors (OAuth2Error,
    transport failure) the response body is a generic ``"Authentication failed"``
    and the raw exception is logged locally only.

    Args:
        client: The ``OAuth2Session`` to authorize (its ``client_id`` /
            ``redirect_uri`` / ``scope`` were configured by ``build_auth_client``).
        user: User dict to receive the ``id_token`` / ``access_token`` /
            ``refresh_token`` / ``expires_at`` columns. Mutated in place and
            persisted to the DB on success.
        app: The Textual app, used to post ``ShowURL`` (if the browser fails
            to open), ``WebServerStarted``, ``WebServerStopped``, and
            ``AuthServerError`` (if the loopback port cannot be bound).

    Returns:
        The original ``client`` (now populated with tokens). The same object
        reference is returned on success and on callback failure — callers
        should check ``client.token`` before treating the session as valid.
    """
    # PKCE: this is a public native/desktop client, so RFC 7636 code_verifier is
    # mandatory. Generate once here; the same value is passed to both
    # create_authorization_url (which derives code_challenge=S256) and fetch_token
    # (which redeems it). Without PKCE, anyone who observes the authorization
    # code can redeem it.
    code_verifier = secrets.token_urlsafe(64)

    def login() -> Any:
        """
        Initiate Auth0 OAuth login by redirecting the user to the Auth0 login page.
        """
        authorization_url, state = client.create_authorization_url(
            f"https://{AUTH0_DOMAIN}/authorize",
            audience=API_AUDIENCE,
            code_verifier=code_verifier,
        )
        if not webbrowser.open(authorization_url):
            app.post_message(ShowURL(authorization_url))

    class OAuthCallbackHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            """Handle the OAuth callback from Auth0.
            This function exchanges the authorization code for tokens and stores the tokens in the db.
            """
            # Match the callback path exactly (ignoring the query string). A loose
            # `startswith` would also accept `/oauth/callbackXYZ`; an early return
            # ensures stray paths can't fall through to the token exchange block.
            request_path = urlparse(self.path).path
            if request_path != "/oauth/callback":
                self.send_error(404, "Not Found")
                return
            try:
                # Build authorization_response from the pinned loopback authority
                # rather than the request's Host header — see LOOPBACK_AUTHORITY.
                authorization_response = f"http://{LOOPBACK_AUTHORITY}{self.path}"
                token = client.fetch_token(
                    f"https://{AUTH0_DOMAIN}/oauth/token",
                    authorization_response=authorization_response,
                    code_verifier=code_verifier,
                )
                user["id_token"] = token.get("id_token")
                user["access_token"] = token.get("access_token")
                user["refresh_token"] = token.get("refresh_token")
                user["expires_at"] = token.get("expires_at")

                db.save_user(user)
            except (OAuth2Error, requests.RequestException) as e:
                # QA-004: log the raw exception for diagnostics via the module
                # logger, but do NOT echo it to the HTTP response body — anyone
                # reaching the loopback callback (e.g. via a browser redirect)
                # would otherwise be able to fingerprint the auth setup via the
                # error text. Narrowed from bare ``except Exception`` so a
                # programming error in the handler still crashes loudly.
                logger.warning("oauth callback token exchange failed: %r", e, exc_info=True)
                self.send_error(500, "Authentication failed")
                return

            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"Logged in. You may close this window.")

            threading.Thread(target=self.shutdown_server).start()

        def shutdown_server(self):
            self.server.shutdown()

    # ARC-018: enable SO_REUSEADDR so a previous pim process leaving the
    # loopback socket in TIME_WAIT doesn't fail the bind on the next launch.
    # ``allow_reuse_address = True`` makes socketserver set SO_REUSEADDR before
    # the bind call (it does NOT enable SO_REUSEPORT — port collisions with a
    # still-living listener still raise, which is what we want).
    class ReusableTCPServer(socketserver.TCPServer):
        allow_reuse_address = True

    # ARC-018: surface a clear error to the UI when port 1999 is already in use
    # (another pim mid-auth, a stray process, etc.) instead of letting the
    # OSError propagate and crash the auth flow.
    try:
        with ReusableTCPServer(("127.0.0.1", OAUTH_CALLBACK_PORT), OAuthCallbackHandler) as httpd:
            try:
                app.post_message(WebServerStarted(httpd))
                login()
                httpd.serve_forever()
            finally:
                app.post_message(WebServerStopped())
    except OSError as e:
        print(f"oauth callback listener failed to bind: {e!r}", file=sys.stderr)
        app.post_message(
            AuthServerError(
                f"Could not start the OAuth callback listener on port {OAUTH_CALLBACK_PORT}: {e}. "
                "Another pim process may already be authenticating; close it and retry."
            )
        )

    return client
