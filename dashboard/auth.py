import os
import requests
from flask import Blueprint, redirect, request, session

auth_bp = Blueprint("auth", __name__)

DISCORD_API = "https://discord.com/api/v10"
CLIENT_ID = os.getenv("DISCORD_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET", "")
SCOPES = "identify guilds"


def _redirect_uri():
    """
    Build the OAuth callback URI.

    Priority:
    1. DASHBOARD_URL env var  (set this in Render: e.g. https://ysl-bot.onrender.com)
    2. RENDER_EXTERNAL_URL    (auto-set by Render, may not always be available)
    3. request.url_root       (last resort, may use http:// — usually wrong in prod)
    """
    base = (
        os.getenv("DASHBOARD_URL")
        or os.getenv("RENDER_EXTERNAL_URL")
        or request.url_root
    )
    return base.rstrip("/") + "/callback"


@auth_bp.route("/login")
def login():
    redirect_uri = _redirect_uri()
    url = (
        f"https://discord.com/oauth2/authorize"
        f"?client_id={CLIENT_ID}"
        f"&redirect_uri={requests.utils.quote(redirect_uri, safe='')}"
        f"&response_type=code"
        f"&scope={requests.utils.quote(SCOPES, safe='')}"
    )
    return redirect(url)


@auth_bp.route("/callback")
def callback():
    code = request.args.get("code")
    if not code:
        return redirect("/")

    redirect_uri = _redirect_uri()

    token_resp = requests.post(
        f"{DISCORD_API}/oauth2/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        auth=(CLIENT_ID, CLIENT_SECRET),
        timeout=10,
    )

    if not token_resp.ok:
        return redirect("/")

    tokens = token_resp.json()
    access_token = tokens.get("access_token")
    if not access_token:
        return redirect("/")

    user_resp = requests.get(
        f"{DISCORD_API}/users/@me",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    if not user_resp.ok:
        return redirect("/")

    user = user_resp.json()
    session["user"] = user
    session["access_token"] = access_token
    return redirect("/servers")


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect("/")
