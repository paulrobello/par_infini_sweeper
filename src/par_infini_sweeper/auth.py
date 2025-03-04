from __future__ import annotations

import http.server
import os
import socketserver
import threading
import webbrowser
from typing import Any

from authlib.integrations.requests_client import OAuth2Session
from textual.app import App

from par_infini_sweeper import db
from par_infini_sweeper.messages import ShowURL, WebServerStarted, WebServerStopped

AUTH0_DOMAIN = os.environ.get("AUTH0_DOMAIN", "par-dev.us.auth0.com")
AUTH0_CLIENT_ID = os.environ.get("AUTH0_CLIENT_ID", "79LqAgzljQjin3dihidWdmLSD7o4CpL5")
API_AUDIENCE = "PIM"
REDIRECT_URI = "http://127.0.0.1:1999/oauth/callback"


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
        # if auth token does not exist or is expired and we have a refresh token, refresh it
        if client.token.is_expired() in [None, True] and client.token["refresh_token"]:
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
            except Exception as _:
                # refresh failed, blank out auth info and start fresh
                # print(f"Error refreshing token: {e}")
                user["access_token"] = ""
                user["refresh_token"] = ""
                user["expires_at"] = 0
                db.save_user(user)
        elif client.token["access_token"]:
            # we have an auth token and its not expired
            return client

    return start_auth_server(client, user, app)


def start_auth_server(client: OAuth2Session, user: dict[str, Any], app: App) -> OAuth2Session:
    def login() -> Any:
        """
        Initiate Auth0 OAuth login by redirecting the user to the Auth0 login page.
        """
        authorization_url, state = client.create_authorization_url(
            f"https://{AUTH0_DOMAIN}/authorize", audience=API_AUDIENCE
        )
        if not webbrowser.open(authorization_url):
            app.post_message(ShowURL(authorization_url))

    class OAuthCallbackHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            """Handle the OAuth callback from Auth0.
            This function exchanges the authorization code for tokens and stores the tokens in the db.
            """
            # Allow any request path that starts with "/oauth/callback"
            if not self.path.startswith("/oauth/callback"):
                self.send_error(404, "Not Found")
            try:
                # Include query parameters in the authorization_response URL
                authorization_response = f"http://{self.headers['Host']}{self.path}"
                token = client.fetch_token(
                    f"https://{AUTH0_DOMAIN}/oauth/token",
                    authorization_response=authorization_response,
                )
                user["id_token"] = token.get("id_token")
                user["access_token"] = token.get("access_token")
                user["refresh_token"] = token.get("refresh_token")
                user["expires_at"] = token.get("expires_at")

                db.save_user(user)
            except Exception as e:
                self.send_error(500, str(e))
                return

            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"Logged in. You may close this window.")

            threading.Thread(target=self.shutdown_server).start()

        def shutdown_server(self):
            self.server.shutdown()

    with socketserver.TCPServer(("127.0.0.1", 1999), OAuthCallbackHandler) as httpd:
        try:
            app.post_message(WebServerStarted(httpd))
            login()
            httpd.serve_forever()
        finally:
            app.post_message(WebServerStopped())

    return client
