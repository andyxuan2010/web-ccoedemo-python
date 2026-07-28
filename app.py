import base64
import json
import os
from datetime import datetime
from datetime import timedelta
from urllib.parse import quote
from urllib.parse import urljoin
from urllib.parse import urlencode

from dotenv import load_dotenv
from flask import Flask, redirect, render_template, request, session, url_for
from msal import ConfidentialClientApplication
from werkzeug.middleware.proxy_fix import ProxyFix


load_dotenv()


def parse_subscription_id(owner_name: str) -> str:
    trimmed_owner_name = owner_name.strip()
    if not trimmed_owner_name:
        return ""
    return trimmed_owner_name.split("+", 1)[0].strip()


def create_app() -> Flask:
    app = Flask(__name__)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

    secret_key = os.getenv("FLASK_SECRET_KEY", "").strip()
    if not secret_key:
        # Keep demo behavior stable across redirects/instances when env var is missing.
        # For production, set FLASK_SECRET_KEY explicitly in App Service settings.
        site_name = os.getenv("WEBSITE_SITE_NAME", "local-demo")
        secret_key = f"insecure-demo-{site_name}"

    app.config["SECRET_KEY"] = secret_key
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(minutes=30)
    if os.getenv("WEBSITE_SITE_NAME"):
        app.config["SESSION_COOKIE_SECURE"] = True

    app.config["AAD_CLIENT_ID"] = os.getenv("AAD_CLIENT_ID", "")
    app.config["AAD_CLIENT_SECRET"] = os.getenv("AAD_CLIENT_SECRET", "")
    app.config["AAD_TENANT_ID"] = os.getenv("AAD_TENANT_ID", "common")
    app.config["AAD_REDIRECT_PATH"] = os.getenv("AAD_REDIRECT_PATH", "/auth/callback")
    app.config["AAD_REDIRECT_URI"] = os.getenv("AAD_REDIRECT_URI", "")
    app.config["AAD_POST_LOGOUT_REDIRECT_URI"] = os.getenv("AAD_POST_LOGOUT_REDIRECT_URI", "")
    app.config["EASY_AUTH_LOGIN_PATH"] = os.getenv("EASY_AUTH_LOGIN_PATH", "/.auth/login/aad")
    app.config["EASY_AUTH_LOGOUT_PATH"] = os.getenv("EASY_AUTH_LOGOUT_PATH", "/.auth/logout")
    app.config["APP_SERVICE_PORTAL_URL"] = os.getenv("APP_SERVICE_PORTAL_URL", "")
    app.config["APP_REGISTRATION_PORTAL_URL"] = os.getenv("APP_REGISTRATION_PORTAL_URL", "")
    app.config["APP_SERVICE_NAME"] = os.getenv(
        "WEBSITE_SITE_NAME",
        os.getenv("APP_SERVICE_NAME", ""),
    )
    app.config["APP_SERVICE_SUBSCRIPTION_ID"] = os.getenv(
        "WEBSITE_OWNER_NAME",
        "",
    )
    app.config["APP_SERVICE_RESOURCE_GROUP"] = os.getenv(
        "WEBSITE_RESOURCE_GROUP",
        os.getenv("APP_SERVICE_RESOURCE_GROUP", ""),
    )
    app.config["AAD_SCOPES"] = [
        scope.strip()
        for scope in os.getenv("AAD_SCOPES", "User.Read").split(",")
        if scope.strip()
    ]

    @app.context_processor
    def inject_auth_mode_status() -> dict:
        active_auth_modes = []
        if session.get("msal_user"):
            active_auth_modes.append("MSAL")
        if get_easy_auth_user():
            active_auth_modes.append("Easy Auth")
        auth_health = build_auth_health(app)
        return {
            "active_auth_modes": active_auth_modes,
            "is_signed_in": bool(active_auth_modes),
            "cache_token": request.args.get("cb", ""),
            "app_service_portal_url": build_app_service_portal_url(app),
            "app_registration_portal_url": build_app_registration_portal_url(app),
            "session_timeline": get_session_timeline(),
            "auth_health": auth_health,
            "auth_health_ready": all(item["ok"] for item in auth_health),
            "runtime_info": get_runtime_info(),
        }

    register_routes(app)
    return app


def register_routes(app: Flask) -> None:
    @app.route("/")
    def index():
        msal_user = session.get("msal_user")
        easy_auth_user = get_easy_auth_user()
        return render_template(
            "index.html",
            msal_user=msal_user,
            easy_auth_user=easy_auth_user,
        )

    @app.route("/login/msal")
    def login_msal():
        add_timeline_event("MSAL sign-in started", "MSAL")
        auth_flow = build_auth_flow(app)
        session["auth_flow"] = auth_flow
        return redirect(auth_flow["auth_uri"])

    @app.route("/login")
    def login():
        return redirect(url_for("login_msal"))

    @app.route("/login/easyauth")
    def login_easyauth():
        add_timeline_event("Easy Auth sign-in started", "Easy Auth")
        post_login_redirect_uri = urljoin(
            request.host_url, url_for("profile_easyauth").lstrip("/")
        )
        return redirect(build_easy_auth_login_url(app, post_login_redirect_uri))

    @app.route(app.config["AAD_REDIRECT_PATH"])
    def authorized():
        if "auth_flow" not in session:
            return redirect(url_for("index"))

        if "error" in request.args:
            return render_template(
                "auth_error.html",
                error=request.args.get("error"),
                error_description=request.args.get("error_description"),
            )

        result = build_msal_app(app).acquire_token_by_auth_code_flow(
            session["auth_flow"], request.args
        )

        if "error" in result:
            return render_template(
                "auth_error.html",
                error=result.get("error"),
                error_description=result.get("error_description"),
            )

        session["msal_user"] = result.get("id_token_claims", {})
        session["msal_access_token"] = result.get("access_token")
        session.pop("auth_flow", None)
        add_timeline_event("MSAL sign-in completed", "MSAL")

        return redirect(url_for("profile_msal"))

    @app.route("/profile/msal")
    def profile_msal():
        user = session.get("msal_user")
        if not user:
            return redirect(url_for("login_msal"))

        add_timeline_event("Viewed profile", "MSAL")
        badges = build_identity_badges(user)
        return render_template(
            "profile.html",
            user=user,
            auth_mode="MSAL",
            claim_items=build_claim_items(user),
            tenant_badges=badges["tenant"],
            role_badges=badges["roles"],
        )

    @app.route("/profile")
    def profile():
        return redirect(url_for("profile_msal"))

    @app.route("/profile/easyauth")
    def profile_easyauth():
        user = get_easy_auth_user()
        if not user:
            return redirect(url_for("login_easyauth"))

        add_timeline_event("Viewed profile", "Easy Auth")
        badges = build_identity_badges(user)
        return render_template(
            "profile.html",
            user=user,
            auth_mode="Easy Auth",
            claim_items=build_claim_items(user.get("claims", {})),
            tenant_badges=badges["tenant"],
            role_badges=badges["roles"],
        )

    @app.route("/logout/msal")
    def logout_msal():
        add_timeline_event("Signed out", "MSAL")
        session.pop("msal_user", None)
        session.pop("msal_access_token", None)
        session.pop("auth_flow", None)
        return redirect(url_for("index"))

    @app.route("/logout")
    def logout():
        return redirect(url_for("logout_msal"))

    @app.route("/logout/easyauth")
    def logout_easyauth():
        add_timeline_event("Signed out", "Easy Auth")
        post_logout_redirect_uri = url_for("index")
        return redirect(build_easy_auth_logout_url(app, post_logout_redirect_uri))

    @app.route("/logout/all")
    def logout_all():
        add_timeline_event("Signed out", "All")
        session.pop("msal_user", None)
        session.pop("msal_access_token", None)
        session.pop("auth_flow", None)

        if get_easy_auth_user():
            return redirect(build_easy_auth_logout_url(app, url_for("index")))

        return redirect(url_for("index"))


def build_msal_app(app: Flask) -> ConfidentialClientApplication:
    authority = f"https://login.microsoftonline.com/{app.config['AAD_TENANT_ID']}"
    return ConfidentialClientApplication(
        client_id=app.config["AAD_CLIENT_ID"],
        client_credential=app.config["AAD_CLIENT_SECRET"],
        authority=authority,
    )


def build_auth_flow(app: Flask) -> dict:
    redirect_uri = build_redirect_uri(app)
    return build_msal_app(app).initiate_auth_code_flow(
        scopes=app.config["AAD_SCOPES"],
        redirect_uri=redirect_uri,
    )


def build_redirect_uri(app: Flask) -> str:
    configured_uri = app.config["AAD_REDIRECT_URI"].strip()
    if configured_uri:
        return configured_uri

    return urljoin(request.host_url, app.config["AAD_REDIRECT_PATH"].lstrip("/"))


def build_post_logout_redirect_uri(app: Flask) -> str:
    configured_uri = app.config["AAD_POST_LOGOUT_REDIRECT_URI"].strip()
    if configured_uri:
        return configured_uri

    return urljoin(request.host_url, url_for("index").lstrip("/"))


def build_app_service_portal_url(app: Flask) -> str:
    configured_url = app.config["APP_SERVICE_PORTAL_URL"].strip()
    if configured_url:
        return configured_url

    subscription_id = parse_subscription_id(
        app.config["APP_SERVICE_SUBSCRIPTION_ID"]
    ) or os.getenv("APP_SERVICE_SUBSCRIPTION_ID", "").strip() or os.getenv(
        "ARM_SUBSCRIPTION_ID", ""
    ).strip()
    resource_group = app.config["APP_SERVICE_RESOURCE_GROUP"].strip()
    app_service_name = app.config["APP_SERVICE_NAME"].strip() or get_site_name_from_host()
    if subscription_id and resource_group and app_service_name:
        return (
            "https://portal.azure.com/#resource/subscriptions/"
            f"{quote(subscription_id)}/resourceGroups/{quote(resource_group)}"
            f"/providers/Microsoft.Web/sites/{quote(app_service_name)}/overview"
        )

    site_name = get_site_name_from_host()
    return (
        "https://portal.azure.com/#view/HubsExtension/BrowseResource/"
        f"resourceType/Microsoft.Web%2Fsites/search/{quote(site_name)}"
    )


def build_app_registration_portal_url(app: Flask) -> str:
    configured_url = app.config["APP_REGISTRATION_PORTAL_URL"].strip()
    if configured_url:
        return configured_url

    app_id = app.config["AAD_CLIENT_ID"].strip()
    if app_id:
        return (
            "https://portal.azure.com/"
            "#view/Microsoft_AAD_RegisteredApps/ApplicationMenuBlade/"
            f"~/Overview/appId/{quote(app_id)}"
        )

    site_name = get_site_name_from_host()
    return (
        "https://portal.azure.com/"
        "#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade/"
        f"searchText/{quote(site_name)}"
    )


def get_runtime_info() -> list:
    os_type = os.getenv("WEBSITE_OS", "").strip() or ("Windows" if os.name == "nt" else "Linux")
    stack = os.getenv("WEBSITE_STACK", "").strip() or "Python"
    version = f"Python {os.sys.version_info.major}.{os.sys.version_info.minor}.{os.sys.version_info.micro}"
    stack_value = build_stack_display_value(stack, version)
    return [
        {"label": "OS Type", "value": os_type},
        {"label": "Stack", "value": stack_value},
    ]


def build_stack_display_value(stack: str, version: str) -> str:
    normalized_stack = stack.strip()
    normalized_version = version.strip()
    stack_key = "".join(ch for ch in normalized_stack.lower() if ch.isalnum())
    version_key = "".join(ch for ch in normalized_version.lower() if ch.isalnum())

    if not normalized_stack:
        return normalized_version

    if not normalized_version or stack_key in version_key:
        return normalized_version or normalized_stack

    return f"{normalized_stack} {normalized_version}"


def get_site_name_from_host() -> str:
    host_without_port = request.host.split(":", 1)[0]
    return host_without_port.split(".", 1)[0]


def build_easy_auth_login_url(app: Flask, post_login_redirect_uri: str) -> str:
    query = urlencode({"post_login_redirect_uri": post_login_redirect_uri})
    return f"{app.config['EASY_AUTH_LOGIN_PATH']}?{query}"


def build_easy_auth_logout_url(app: Flask, post_logout_redirect_uri: str) -> str:
    query = urlencode({"post_logout_redirect_uri": post_logout_redirect_uri})
    return f"{app.config['EASY_AUTH_LOGOUT_PATH']}?{query}"


def get_easy_auth_user() -> dict:
    principal_header = request.headers.get("X-MS-CLIENT-PRINCIPAL", "")
    if not principal_header:
        return {}

    try:
        payload = base64.b64decode(principal_header)
        principal = json.loads(payload)
    except (ValueError, json.JSONDecodeError):
        return {}

    claims = principal.get("claims", [])
    claim_map = {c.get("typ"): c.get("val") for c in claims if c.get("typ") and c.get("val")}

    def first_claim(*keys: str) -> str:
        for key in keys:
            value = claim_map.get(key)
            if value:
                return value
        return ""

    return {
        "name": first_claim(
            "name",
            "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name",
        ) or principal.get("userDetails", ""),
        "preferred_username": (
            first_claim(
                "preferred_username",
                "upn",
                "email",
                "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/upn",
                "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress",
            )
            or principal.get("userDetails", "")
        ),
        "tid": first_claim(
            "tid",
            "tenantid",
            "http://schemas.microsoft.com/identity/claims/tenantid",
        ),
        "oid": first_claim(
            "oid",
            "objectidentifier",
            "http://schemas.microsoft.com/identity/claims/objectidentifier",
            "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/nameidentifier",
        ) or principal.get("userId"),
        "identity_provider": principal.get("identityProvider", ""),
        "authentication_type": principal.get("auth_typ", ""),
        "user_id": principal.get("userId", ""),
        "user_details": principal.get("userDetails", ""),
        "claims": claim_map,
    }


def build_claim_items(claims: dict) -> list:
    items = []
    for key in sorted(claims.keys()):
        value = claims.get(key)
        if isinstance(value, (str, int, float, bool)):
            text = str(value)
            if text:
                items.append((key, text))
    return items


def add_timeline_event(event: str, mode: str = "", detail: str = "") -> None:
    timeline = session.get("session_timeline", [])
    timeline.append(
        {
            "event": event,
            "mode": mode,
            "detail": detail,
            "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    )
    session["session_timeline"] = timeline[-12:]
    session.modified = True


def get_session_timeline() -> list:
    timeline = session.get("session_timeline", [])
    return list(reversed(timeline))


def build_auth_health(app: Flask) -> list:
    configured_redirect_uri = app.config["AAD_REDIRECT_URI"].strip() or "auto from host + path"
    secret_is_explicit = bool(os.getenv("FLASK_SECRET_KEY", "").strip())
    return [
        {
            "name": "AAD_CLIENT_ID",
            "ok": bool(app.config["AAD_CLIENT_ID"].strip()),
            "value": mask_value(app.config["AAD_CLIENT_ID"].strip()),
        },
        {
            "name": "AAD_CLIENT_SECRET",
            "ok": bool(app.config["AAD_CLIENT_SECRET"].strip()),
            "value": "configured" if app.config["AAD_CLIENT_SECRET"].strip() else "missing",
        },
        {
            "name": "AAD_TENANT_ID",
            "ok": bool(app.config["AAD_TENANT_ID"].strip()),
            "value": app.config["AAD_TENANT_ID"].strip() or "missing",
        },
        {
            "name": "AAD_REDIRECT_PATH",
            "ok": app.config["AAD_REDIRECT_PATH"].startswith("/"),
            "value": app.config["AAD_REDIRECT_PATH"],
        },
        {
            "name": "AAD_REDIRECT_URI",
            "ok": True,
            "value": configured_redirect_uri,
        },
        {
            "name": "FLASK_SECRET_KEY",
            "ok": secret_is_explicit,
            "value": "explicit" if secret_is_explicit else "demo fallback",
        },
    ]


def mask_value(value: str) -> str:
    if not value:
        return "missing"
    if len(value) <= 8:
        return value
    return f"{value[:4]}...{value[-4:]}"


def build_identity_badges(user: dict) -> dict:
    tenant = []
    roles = []

    tid = (user.get("tid") or "").strip()
    if tid:
        tenant.append(tid)

    claims_source = user.get("claims", {})
    if isinstance(claims_source, dict):
        role_values = normalize_claim_values(
            claims_source.get("roles")
            or claims_source.get("role")
            or claims_source.get("http://schemas.microsoft.com/ws/2008/06/identity/claims/role")
        )
        group_values = normalize_claim_values(claims_source.get("groups"))
    else:
        role_values = normalize_claim_values(user.get("roles"))
        group_values = normalize_claim_values(user.get("groups"))

    if not role_values:
        role_values = normalize_claim_values(user.get("roles"))
    roles.extend(role_values[:8])

    if group_values:
        roles.extend([f"group:{value}" for value in group_values[:4]])

    return {"tenant": dedupe_values(tenant), "roles": dedupe_values(roles)}


def normalize_claim_values(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, (int, float, bool)):
        return [str(value)]
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if text.startswith("[") and text.endswith("]"):
            try:
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    return [str(v).strip() for v in parsed if str(v).strip()]
            except json.JSONDecodeError:
                pass
        if "," in text:
            return [part.strip() for part in text.split(",") if part.strip()]
        return [text]
    return []


def dedupe_values(values: list) -> list:
    seen = set()
    unique = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
