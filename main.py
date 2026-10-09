import os
import base64
import hashlib
import json
import logging
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from email.message import EmailMessage
from secrets import compare_digest, token_urlsafe
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlencode
from urllib.request import Request as UrlRequest, urlopen
from uuid import uuid4
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from starlette.middleware.sessions import SessionMiddleware

load_dotenv()
BASE_DIR = Path(__file__).resolve().parent
logger = logging.getLogger(__name__)
app = FastAPI(title="Tellabelli Village Market", version="1.0.0")
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET") or token_urlsafe(32),
    same_site="lax",
    https_only=os.getenv("COOKIE_SECURE", "false").casefold() == "true",
)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

CATEGORIES = [
    {"id": "vegetables", "name": "Indian Breakfast", "slug": "indian-breakfast"},
    {"id": "fruits", "name": "Indian Snacks", "slug": "indian-snacks"},
    {"id": "indian-lunch-dinner", "name": "Indian Lunch/Dinner", "slug": "indian-lunch-dinner"},
    {"id": "lentils", "name": "Lentils & pulses", "slug": "lentils"},
    {"id": "grains", "name": "Rice & grains", "slug": "grains"},
    {"id": "pantry", "name": "Pantry", "slug": "pantry"},
]
DELIVERY_LOCATIONS = [
    {"id": "skullerud", "name": "Skullerud"},
    {"id": "solli", "name": "Solli"},
    {"id": "sagane", "name": "Sagane"},
    {"id": "fornebu", "name": "Fornebu"},
    {"id": "veitvet", "name": "Veitvet"},
]

DEMO_PRODUCTS = [
    {"id": "demo-tomatoes", "category_id": "vegetables", "name": "Idli & sambar", "description": "Soft steamed rice cakes with lentil stew", "price": 6.50, "unit": "portion", "stock_quantity": 18, "image_url": "https://images.unsplash.com/photo-1589301760014-d929f3979dbc?auto=format&fit=crop&w=700&q=80"},
    {"id": "demo-spinach", "category_id": "vegetables", "name": "Masala dosa", "description": "Crispy dosa with spiced potato filling", "price": 7.50, "unit": "portion", "stock_quantity": 12, "image_url": "https://images.unsplash.com/photo-1668236543090-82eba5ee5976?auto=format&fit=crop&w=700&q=80"},
    {"id": "demo-apples", "category_id": "fruits", "name": "Vegetable samosa", "description": "Crisp pastry filled with spiced potato", "price": 2.50, "unit": "2 pieces", "stock_quantity": 20, "image_url": "https://images.unsplash.com/photo-1601050690597-df0568f70950?auto=format&fit=crop&w=700&q=80"},
    {"id": "demo-oranges", "category_id": "fruits", "name": "Onion pakora", "description": "Crispy onion fritters with Indian spices", "price": 4.50, "unit": "portion", "stock_quantity": 14, "image_url": "https://images.unsplash.com/photo-1601050690597-df0568f70950?auto=format&fit=crop&w=700&q=80"},
    {"id": "demo-biryani", "category_id": "indian-lunch-dinner", "name": "Vegetable biryani", "description": "Fragrant basmati rice with vegetables and spices", "price": 10.90, "unit": "portion", "stock_quantity": 15, "image_url": "https://images.unsplash.com/photo-1589301760014-d929f3979dbc?auto=format&fit=crop&w=700&q=80"},
    {"id": "demo-paneer-curry", "category_id": "indian-lunch-dinner", "name": "Paneer curry", "description": "Paneer in a creamy tomato curry", "price": 11.50, "unit": "portion", "stock_quantity": 10, "image_url": "https://images.unsplash.com/photo-1589301760014-d929f3979dbc?auto=format&fit=crop&w=700&q=80"},
    {"id": "demo-lentils", "category_id": "lentils", "name": "Red lentils", "description": "Quick-cooking, protein-rich", "price": 4.60, "unit": "500 g", "stock_quantity": 16, "image_url": "https://images.unsplash.com/photo-1515543904379-3d757afe72e4?auto=format&fit=crop&w=700&q=80"},
    {"id": "demo-chickpeas", "category_id": "lentils", "name": "Chickpeas", "description": "Creamy, versatile pantry staple", "price": 3.85, "unit": "500 g", "stock_quantity": 9, "image_url": "https://images.unsplash.com/photo-1515543904379-3d757afe72e4?auto=format&fit=crop&w=700&q=80"},
    {"id": "demo-rice", "category_id": "grains", "name": "Basmati rice", "description": "Fragrant long grain · aged", "price": 8.50, "unit": "2 kg", "stock_quantity": 10, "image_url": "https://images.unsplash.com/photo-1586201375761-83865001e31c?auto=format&fit=crop&w=700&q=80"},
    {"id": "demo-oats", "category_id": "grains", "name": "Rolled oats", "description": "Wholegrain breakfast oats", "price": 3.40, "unit": "1 kg", "stock_quantity": 0, "image_url": "https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?auto=format&fit=crop&w=700&q=80"},
    {"id": "demo-oil", "category_id": "pantry", "name": "Extra virgin olive oil", "description": "Cold pressed · smooth finish", "price": 9.90, "unit": "500 ml", "stock_quantity": 7, "image_url": "https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?auto=format&fit=crop&w=700&q=80"},
]
DEMO_LOCATION_STOCK = {
    product["id"]: {location["id"]: product["stock_quantity"] for location in DELIVERY_LOCATIONS}
    for product in DEMO_PRODUCTS
}
DEMO_ORDERS: list[dict[str, Any]] = []
DEMO_ITEM_REQUESTS: list[dict[str, Any]] = []
DEMO_ADMIN_USERS: list[dict[str, Any]] = []
PASSWORD_HASH_ITERATIONS = 310_000
ADMIN_ORDER_PAGE_SIZE = 10
MARKET_TIMEZONE = ZoneInfo("Europe/Oslo")


class OrderItem(BaseModel):
    product_id: str = Field(min_length=1, max_length=80)
    quantity: int = Field(ge=1, le=99)


class OrderRequest(BaseModel):
    customer_name: str = Field(min_length=2, max_length=120)
    customer_phone: str = Field(min_length=7, max_length=40)
    customer_email: str | None = Field(default=None, max_length=254)
    sms_consent: bool = False
    delivery_address: str = Field(min_length=5, max_length=500)
    delivery_location_id: str = Field(min_length=1, max_length=40)
    items: list[OrderItem] = Field(min_length=1, max_length=60)


class ItemRequest(BaseModel):
    customer_name: str = Field(min_length=2, max_length=120)
    customer_phone: str = Field(min_length=7, max_length=40)
    requested_name: str = Field(min_length=2, max_length=160)
    category_id: str = Field(min_length=1, max_length=60)
    delivery_location_id: str = Field(min_length=1, max_length=40)
    delivery_address: str = Field(min_length=5, max_length=500)
    note: str | None = Field(default=None, max_length=500)


class AdminLogin(BaseModel):
    password: str = Field(min_length=1, max_length=256)
    username: str | None = Field(default=None, min_length=3, max_length=40)


class LocationAdminCreate(BaseModel):
    username: str = Field(min_length=3, max_length=40, pattern=r"^[A-Za-z0-9._-]+$")
    display_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=12, max_length=256)
    location_ids: list[str] = Field(min_length=1, max_length=5)


class LocationAdminActiveUpdate(BaseModel):
    is_active: bool


class LocationAdminLocationsUpdate(BaseModel):
    location_ids: list[str] = Field(min_length=1, max_length=5)


class PriceUpdate(BaseModel):
    price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)


class ProductCreate(BaseModel):
    category_id: str = Field(min_length=1, max_length=60)
    name: str = Field(min_length=2, max_length=160)
    description: str = Field(default="", max_length=1000)
    price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    unit: str = Field(default="each", min_length=1, max_length=60)
    image_url: str = Field(default="", max_length=2048)
    location_stock: dict[str, int] = Field(min_length=1, max_length=5)

    @field_validator("location_stock")
    @classmethod
    def validate_selected_stock(cls, values: dict[str, int]) -> dict[str, int]:
        if any(isinstance(quantity, bool) or quantity < 1 or quantity > 1_000_000 for quantity in values.values()):
            raise ValueError("Selected locations must have between 1 and 1,000,000 items in stock.")
        return values


class StockQuantityUpdate(BaseModel):
    stock_quantity: int = Field(ge=0, le=1_000_000)


class OrderStatusUpdate(BaseModel):
    status: Literal["placed", "confirmed", "packing", "out_for_delivery", "completed", "cancelled"]


def hash_admin_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PASSWORD_HASH_ITERATIONS)
    return "pbkdf2_sha256${}${}${}".format(
        PASSWORD_HASH_ITERATIONS,
        base64.urlsafe_b64encode(salt).decode(),
        base64.urlsafe_b64encode(digest).decode(),
    )


def verify_admin_password(password: str, encoded_hash: str) -> bool:
    try:
        algorithm, iterations_text, salt_text, digest_text = encoded_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iterations_text)
        if iterations < 100_000 or iterations > 2_000_000:
            return False
        salt = base64.urlsafe_b64decode(salt_text.encode())
        expected = base64.urlsafe_b64decode(digest_text.encode())
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
        return compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def normalize_order_items(items: list[OrderItem]) -> list[dict[str, Any]]:
    quantities: dict[str, int] = {}
    for item in items:
        quantities[item.product_id] = quantities.get(item.product_id, 0) + item.quantity
    if any(quantity > 99 for quantity in quantities.values()):
        raise ValueError("The maximum quantity per item is 99.")
    return [{"product_id": product_id, "quantity": quantity} for product_id, quantity in quantities.items()]


def send_order_email(recipient: str, subject: str, body: str) -> None:
    provider = os.getenv("EMAIL_PROVIDER", "smtp").strip().casefold()
    sender = os.getenv("SMTP_FROM_EMAIL")
    if provider == "brevo":
        api_key = os.getenv("BREVO_API_KEY")
        if not api_key or not sender:
            raise RuntimeError("BREVO_API_KEY and SMTP_FROM_EMAIL must be configured for Brevo.")

        request = UrlRequest(
            "https://api.brevo.com/v3/smtp/email",
            data=json.dumps({
                "sender": {"email": sender},
                "to": [{"email": recipient}],
                "subject": subject,
                "textContent": body,
            }).encode(),
            headers={
                "api-key": api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        with urlopen(request, timeout=8) as response:
            if response.status < 200 or response.status >= 300:
                raise RuntimeError(f"Brevo returned HTTP {response.status}.")
        return

    if provider != "smtp":
        raise RuntimeError("EMAIL_PROVIDER must be set to 'smtp' or 'brevo'.")

    host = os.getenv("SMTP_HOST")
    if not host or not sender:
        raise RuntimeError("SMTP_HOST and SMTP_FROM_EMAIL must be configured.")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = recipient
    message.set_content(body)

    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME")
    password = os.getenv("SMTP_PASSWORD")
    use_ssl = os.getenv("SMTP_USE_SSL", "false").casefold() == "true"
    smtp_class = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
    options: dict[str, Any] = {"timeout": 8}
    if use_ssl:
        options["context"] = ssl.create_default_context()
    with smtp_class(host, port, **options) as server:
        if not use_ssl:
            server.starttls(context=ssl.create_default_context())
        if username:
            server.login(username, password or "")
        server.send_message(message)


def send_order_sms(recipient: str, body: str) -> None:
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_FROM_NUMBER")
    if not account_sid or not auth_token or not from_number:
        raise RuntimeError("Twilio account SID, auth token, and sender number must be configured.")

    credentials = base64.b64encode(f"{account_sid}:{auth_token}".encode()).decode()
    request = UrlRequest(
        f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json",
        data=urlencode({"To": recipient, "From": from_number, "Body": body}).encode(),
        headers={"Authorization": f"Basic {credentials}"},
        method="POST",
    )
    with urlopen(request, timeout=8) as response:
        if response.status < 200 or response.status >= 300:
            raise RuntimeError(f"Twilio returned HTTP {response.status}.")


def order_confirmation_content(
    order_number: str,
    customer_name: str,
    location_name: str,
    items: list[dict[str, Any]],
    total: float,
) -> str:
    def format_nok(amount: float) -> str:
        whole, fractional = f"{amount:,.2f}".split(".")
        return f"{whole.replace(',', '\u00a0')},{fractional} kr"

    lines = [
        f"{int(item['quantity'])} x {item['product_name']} @ {format_nok(float(item['unit_price']))} = {format_nok(float(item['line_total']))}"
        for item in items
    ]
    return "\n".join([
        f"Hi {customer_name},",
        "",
        "Your grocery order has been received.",
        f"Order number: {order_number}",
        f"Delivery location: {location_name}",
        "",
        "Items:",
        *lines,
        "",
        f"Total: {format_nok(total)}",
        "Status: placed",
        "",
        "Use the order number in the market's Check order status section to track your order.",
    ])


def send_order_notifications(
    order_id: str,
    customer_name: str,
    customer_email: str | None,
    customer_phone: str,
    sms_consent: bool,
    location_name: str,
    items: list[dict[str, Any]],
    total: float,
) -> tuple[list[str], list[str]]:
    order_number = order_id[:8].upper()
    body = order_confirmation_content(order_number, customer_name, location_name, items, total)
    sent_channels: list[str] = []
    warnings: list[str] = []

    if customer_email:
        try:
            send_order_email(customer_email, f"Order {order_number} confirmation", body)
            sent_channels.append("email")
        except Exception as exc:
            logger.warning(
                "Order %s email notification failed (%s: %s).",
                order_number,
                type(exc).__name__,
                exc,
            )
            warnings.append("Email confirmation could not be sent; check the SMTP settings.")
    else:
        warnings.append("Email confirmation was not sent because no email address was provided.")

    if sms_consent:
        try:
            send_order_sms(customer_phone, body)
            sent_channels.append("SMS")
        except Exception as exc:
            logger.warning("Order %s SMS notification failed (%s).", order_number, type(exc).__name__)
            warnings.append("SMS confirmation could not be sent; check the Twilio settings.")
    else:
        warnings.append("SMS confirmation was not sent because SMS consent was not given.")
    return sent_channels, warnings


def supabase_client():
    url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not service_key:
        return None
    from supabase import create_client

    return create_client(url, service_key)


def database_setup_error(exc: Exception, operation: str) -> HTTPException:
    error_text = str(exc)
    if any(code in error_text for code in ("PGRST205", "PGRST202", "42P01", "42883")):
        return HTTPException(
            status_code=503,
            detail="Required Supabase database objects are missing or not in the API schema cache. Run the latest sql/schema.sql in the project configured by SUPABASE_URL, then retry. For location inventory, confirm public.product_location_inventory exists.",
        )
    return HTTPException(status_code=503, detail=operation)


@app.get("/")
def home():
    return FileResponse(BASE_DIR / "templates" / "index.html")


@app.get("/manifest.webmanifest", include_in_schema=False)
def web_app_manifest():
    return FileResponse(
        BASE_DIR / "static" / "manifest.webmanifest",
        media_type="application/manifest+json",
    )


@app.get("/service-worker.js", include_in_schema=False)
def service_worker():
    return FileResponse(
        BASE_DIR / "static" / "service-worker.js",
        media_type="application/javascript",
        headers={"Service-Worker-Allowed": "/"},
    )


@app.get("/admin")
def admin_page():
    return FileResponse(BASE_DIR / "templates" / "admin.html")


def require_admin(request: Request) -> None:
    if request.session.get("admin") is not True:
        raise HTTPException(status_code=401, detail="Admin sign-in required.")
    if request.session.get("admin_role", "owner") != "location":
        return
    user_id = request.session.get("admin_user_id")
    client = supabase_client()
    try:
        if client is None:
            user = next((
                item for item in DEMO_ADMIN_USERS
                if item["id"] == user_id and item["is_active"]
            ), None)
            location_ids = user["location_ids"] if user else []
        else:
            user = client.table("market_admin_users").select(
                "id,is_active"
            ).eq("id", user_id).maybe_single().execute().data
            if user and user["is_active"]:
                location_ids = [
                    membership["location_id"]
                    for membership in client.table("market_admin_user_locations").select(
                        "location_id"
                    ).eq("user_id", user_id).execute().data
                ]
            else:
                location_ids = []
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Staff access could not be verified.") from exc
    if not valid_location_ids(location_ids):
        request.session.clear()
        raise HTTPException(status_code=401, detail="This location-team account is inactive or unassigned.")
    request.session["admin_location_ids"] = location_ids


def require_owner(request: Request) -> None:
    require_admin(request)
    if request.session.get("admin_role", "owner") != "owner":
        raise HTTPException(status_code=403, detail="Owner access required.")


def valid_location_ids(location_ids: list[str]) -> bool:
    allowed = {location["id"] for location in DELIVERY_LOCATIONS}
    return bool(location_ids) and len(location_ids) == len(set(location_ids)) and set(location_ids) <= allowed


@app.get("/api/admin/session")
def get_admin_session(request: Request):
    authenticated = request.session.get("admin") is True
    role = request.session.get("admin_role", "owner") if authenticated else None
    return {
        "authenticated": authenticated,
        "configured": bool(os.getenv("ADMIN_PASSWORD")) or bool(
            os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        ),
        "role": role,
        "display_name": request.session.get("admin_display_name") if authenticated else None,
        "location_ids": request.session.get("admin_location_ids", []) if authenticated else [],
    }


@app.post("/api/admin/login")
def admin_login(login: AdminLogin, request: Request):
    username = (login.username or "").strip().casefold()
    if username:
        client = supabase_client()
        if client is None:
            user = next((item for item in DEMO_ADMIN_USERS if item["username"] == username and item["is_active"]), None)
            memberships = user["location_ids"] if user else []
        else:
            try:
                user = client.table("market_admin_users").select(
                    "id,username,display_name,password_hash,is_active"
                ).eq("username", username).maybe_single().execute().data
                memberships = []
                if user and user["is_active"]:
                    memberships = [
                        membership["location_id"]
                        for membership in client.table("market_admin_user_locations").select(
                            "location_id"
                        ).eq("user_id", user["id"]).execute().data
                    ]
            except Exception as exc:
                raise database_setup_error(exc, "Staff sign-in is temporarily unavailable.") from exc
        if not user or not user["is_active"] or not verify_admin_password(login.password, user["password_hash"]):
            raise HTTPException(status_code=401, detail="The username or password is incorrect.")
        if not valid_location_ids(memberships):
            raise HTTPException(status_code=403, detail="This account has no active location assignment.")
        request.session.clear()
        request.session.update({
            "admin": True,
            "admin_role": "location",
            "admin_user_id": user["id"],
            "admin_username": user["username"],
            "admin_display_name": user["display_name"],
            "admin_location_ids": memberships,
        })
        return {"authenticated": True, "role": "location", "display_name": user["display_name"]}

    admin_password = os.getenv("ADMIN_PASSWORD")
    if not admin_password:
        raise HTTPException(status_code=503, detail="Owner sign-in is not configured.")
    if not compare_digest(login.password, admin_password):
        raise HTTPException(status_code=401, detail="The password is incorrect.")
    request.session.clear()
    request.session["admin"] = True
    request.session["admin_role"] = "owner"
    request.session["admin_display_name"] = "Owner"
    return {"authenticated": True, "role": "owner", "display_name": "Owner"}


@app.post("/api/admin/logout")
def admin_logout(request: Request):
    request.session.clear()
    return {"authenticated": False}


@app.get("/api/delivery-locations")
def get_delivery_locations():
    return {"locations": DELIVERY_LOCATIONS}


@app.get("/api/admin/location-admins", dependencies=[Depends(require_owner)])
def get_location_admins():
    client = supabase_client()
    if client is None:
        users = [{
            "id": user["id"],
            "username": user["username"],
            "display_name": user["display_name"],
            "is_active": user["is_active"],
            "location_ids": user["location_ids"],
            "locations": [
                location["name"] for location in DELIVERY_LOCATIONS
                if location["id"] in user["location_ids"]
            ],
        } for user in DEMO_ADMIN_USERS]
        return {"users": users, "mode": "demo"}
    try:
        users = client.table("market_admin_users").select(
            "id,username,display_name,is_active,created_at"
        ).order("created_at", desc=True).execute().data
        memberships = client.table("market_admin_user_locations").select(
            "user_id,location_id"
        ).execute().data
        location_names = {location["id"]: location["name"] for location in DELIVERY_LOCATIONS}
        assigned: dict[str, list[str]] = {}
        assigned_ids: dict[str, list[str]] = {}
        for membership in memberships:
            assigned.setdefault(membership["user_id"], []).append(
                location_names.get(membership["location_id"], membership["location_id"])
            )
            assigned_ids.setdefault(membership["user_id"], []).append(membership["location_id"])
        for user in users:
            user["locations"] = assigned.get(user["id"], [])
            user["location_ids"] = assigned_ids.get(user["id"], [])
        return {"users": users, "mode": "supabase"}
    except Exception as exc:
        raise database_setup_error(exc, "Location-admin accounts are temporarily unavailable.") from exc


@app.post("/api/admin/location-admins", status_code=201, dependencies=[Depends(require_owner)])
def create_location_admin(user: LocationAdminCreate):
    location_ids = list(dict.fromkeys(user.location_ids))
    if not valid_location_ids(location_ids):
        raise HTTPException(status_code=422, detail="Choose one or more valid delivery locations.")
    username = user.username.strip().casefold()
    password_hash = hash_admin_password(user.password)
    client = supabase_client()
    if client is None:
        if any(existing["username"] == username for existing in DEMO_ADMIN_USERS):
            raise HTTPException(status_code=409, detail="That username is already in use.")
        record = {
            "id": str(uuid4()),
            "username": username,
            "display_name": user.display_name.strip(),
            "password_hash": password_hash,
            "is_active": True,
            "location_ids": location_ids,
        }
        DEMO_ADMIN_USERS.append(record)
        return {
            "id": record["id"],
            "username": username,
            "display_name": record["display_name"],
            "is_active": True,
            "location_ids": location_ids,
            "locations": [location["name"] for location in DELIVERY_LOCATIONS if location["id"] in location_ids],
        }
    try:
        created_id = client.rpc("create_market_admin_user", {
            "p_username": username,
            "p_display_name": user.display_name.strip(),
            "p_password_hash": password_hash,
            "p_location_ids": location_ids,
        }).execute().data
        return {
            "id": created_id,
            "username": username,
            "display_name": user.display_name.strip(),
            "is_active": True,
            "location_ids": location_ids,
            "locations": [location["name"] for location in DELIVERY_LOCATIONS if location["id"] in location_ids],
        }
    except Exception as exc:
        if "unique" in str(exc).casefold() or "duplicate" in str(exc).casefold():
            raise HTTPException(status_code=409, detail="That username is already in use.") from exc
        raise database_setup_error(exc, "The location-admin account could not be created.") from exc


@app.patch("/api/admin/location-admins/{user_id}/locations", dependencies=[Depends(require_owner)])
def update_location_admin_locations(user_id: str, update: LocationAdminLocationsUpdate):
    location_ids = list(dict.fromkeys(update.location_ids))
    if not valid_location_ids(location_ids):
        raise HTTPException(status_code=422, detail="Choose one or more valid delivery locations.")
    client = supabase_client()
    if client is None:
        user = next((item for item in DEMO_ADMIN_USERS if item["id"] == user_id), None)
        if user is None:
            raise HTTPException(status_code=404, detail="Location-admin account not found.")
        user["location_ids"] = location_ids
        return {"id": user_id, "location_ids": location_ids}
    try:
        result = client.rpc("replace_market_admin_locations", {
            "p_user_id": user_id,
            "p_location_ids": location_ids,
        }).execute()
        if result.data is False:
            raise HTTPException(status_code=404, detail="Location-admin account not found.")
        return {"id": user_id, "location_ids": location_ids}
    except HTTPException:
        raise
    except Exception as exc:
        raise database_setup_error(exc, "The location assignment could not be updated.") from exc


@app.patch("/api/admin/location-admins/{user_id}/active", dependencies=[Depends(require_owner)])
def set_location_admin_active(user_id: str, update: LocationAdminActiveUpdate):
    client = supabase_client()
    if client is None:
        user = next((item for item in DEMO_ADMIN_USERS if item["id"] == user_id), None)
        if user is None:
            raise HTTPException(status_code=404, detail="Location-admin account not found.")
        user["is_active"] = update.is_active
        return {"id": user_id, "is_active": user["is_active"]}
    try:
        result = client.table("market_admin_users").update(
            {"is_active": update.is_active}
        ).eq("id", user_id).select("id,is_active").execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Location-admin account not found.")
        return result.data[0]
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="The account status could not be updated.") from exc


@app.get("/api/admin/orders", dependencies=[Depends(require_admin)])
def get_admin_orders(
    request: Request,
    status: Literal["all", "placed", "confirmed", "packing", "out_for_delivery", "completed", "cancelled"] = "all",
    period: Literal["today", "all"] = "today",
    offset: int = Query(default=0, ge=0),
):
    role = request.session.get("admin_role", "owner")
    location_ids = request.session.get("admin_location_ids", [])
    today = datetime.now(MARKET_TIMEZONE).date()
    start_of_today = datetime.combine(today, datetime.min.time(), tzinfo=MARKET_TIMEZONE)
    start_of_tomorrow = datetime.combine(today + timedelta(days=1), datetime.min.time(), tzinfo=MARKET_TIMEZONE)
    start_utc = start_of_today.astimezone(timezone.utc).isoformat()
    end_utc = start_of_tomorrow.astimezone(timezone.utc).isoformat()

    client = supabase_client()
    if client is None:
        orders = DEMO_ORDERS
        if role == "location":
            orders = [order for order in orders if order.get("delivery_location_id") in location_ids]
        if status != "all":
            orders = [order for order in orders if order.get("status", "placed") == status]
        if period == "today":
            def was_created_today(order: dict[str, Any]) -> bool:
                created_at = datetime.fromisoformat(order["created_at"].replace("Z", "+00:00"))
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                return created_at.astimezone(MARKET_TIMEZONE).date() == today

            orders = [order for order in orders if was_created_today(order)]
        orders = sorted(orders, key=lambda order: order.get("created_at", ""), reverse=True)
        page = orders[offset:offset + ADMIN_ORDER_PAGE_SIZE + 1]
        return {
            "orders": page[:ADMIN_ORDER_PAGE_SIZE],
            "has_more": len(page) > ADMIN_ORDER_PAGE_SIZE,
            "mode": "demo",
        }
    try:
        query = client.table("customer_orders").select(
            "id,delivery_location_id,customer_name,customer_phone,customer_email,delivery_address,total,status,created_at,"
            "order_items(id,product_name,quantity,unit_price,line_total)"
        )
        if role == "location":
            query = query.in_("delivery_location_id", location_ids)
        if status != "all":
            query = query.eq("status", status)
        if period == "today":
            query = query.gte("created_at", start_utc).lt("created_at", end_utc)
        page = query.order("created_at", desc=True).range(
            offset, offset + ADMIN_ORDER_PAGE_SIZE
        ).execute().data
        has_more = len(page) > ADMIN_ORDER_PAGE_SIZE
        orders = page[:ADMIN_ORDER_PAGE_SIZE]
        location_names = {location["id"]: location["name"] for location in DELIVERY_LOCATIONS}
        for order in orders:
            order["delivery_location_name"] = location_names.get(order["delivery_location_id"], "Unassigned")
        return {"orders": orders, "has_more": has_more, "mode": "supabase"}
    except Exception as exc:
        raise database_setup_error(exc, "Orders are temporarily unavailable.") from exc


@app.patch("/api/admin/orders/{order_id}/status", dependencies=[Depends(require_admin)])
def update_order_status(order_id: str, update: OrderStatusUpdate, request: Request):
    role = request.session.get("admin_role", "owner")
    location_ids = request.session.get("admin_location_ids", [])
    client = supabase_client()
    if client is None:
        order = next((item for item in DEMO_ORDERS if item["id"] == order_id), None)
        if order is None:
            raise HTTPException(status_code=404, detail="Order not found.")
        if role == "location" and order.get("delivery_location_id") not in location_ids:
            raise HTTPException(status_code=403, detail="This order is assigned to another location.")
        order["status"] = update.status
        return {"order_id": order_id, "status": order["status"], "mode": "demo"}
    try:
        existing_order = client.table("customer_orders").select(
            "id,delivery_location_id"
        ).eq("id", order_id).maybe_single().execute().data
        if existing_order is None:
            raise HTTPException(status_code=404, detail="Order not found.")
        if role == "location" and existing_order["delivery_location_id"] not in location_ids:
            raise HTTPException(status_code=403, detail="This order is assigned to another location.")
        result = client.table("customer_orders").update({"status": update.status}).eq("id", order_id).select("id,status").execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Order not found.")
        return {"order_id": order_id, "status": update.status, "mode": "supabase"}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="The order status could not be updated.") from exc


@app.get("/api/admin/item-requests", dependencies=[Depends(require_owner)])
def get_admin_item_requests():
    client = supabase_client()
    if client is None:
        return {"requests": DEMO_ITEM_REQUESTS, "mode": "demo"}
    try:
        requests = client.table("customer_item_requests").select(
            "id,customer_name,customer_phone,requested_name,category_id,delivery_location_id,delivery_address,note,status,created_at"
        ).order("created_at", desc=True).execute().data
        categories = client.table("categories").select("id,name").execute().data
        category_names = {category["id"]: category["name"] for category in categories}
        location_names = {location["id"]: location["name"] for location in DELIVERY_LOCATIONS}
        for item_request in requests:
            item_request["category_name"] = category_names.get(item_request["category_id"], "Unknown category")
            item_request["delivery_location_name"] = location_names.get(item_request["delivery_location_id"], "Unknown location")
        return {"requests": requests, "mode": "supabase"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Customer requests are temporarily unavailable.") from exc


@app.get("/api/admin/products", dependencies=[Depends(require_admin)])
def get_admin_products(request: Request):
    role = request.session.get("admin_role", "owner")
    location_ids = request.session.get("admin_location_ids", [])
    allowed_locations = [
        location for location in DELIVERY_LOCATIONS
        if role == "owner" or location["id"] in location_ids
    ]
    client = supabase_client()
    if client is None:
        category_names = {category["id"]: category["name"] for category in CATEGORIES}
        products = [
            {
                **product,
                "category_name": category_names.get(product["category_id"], ""),
                "location_inventory": {
                    location["id"]: DEMO_LOCATION_STOCK.get(product["id"], {}).get(location["id"], 0)
                    for location in allowed_locations
                },
            }
            for product in DEMO_PRODUCTS
        ]
        return {"products": products, "categories": CATEGORIES, "mode": "demo"}
    try:
        products = client.table("products").select(
            "id,category_id,name,price,unit,stock_quantity,is_available"
        ).order("category_id").order("name").execute().data
        inventory_query = client.table("product_location_inventory").select(
            "product_id,location_id,stock_quantity"
        )
        if role == "location":
            inventory_query = inventory_query.in_("location_id", [location["id"] for location in allowed_locations])
        inventory = inventory_query.execute().data
        categories = client.table("categories").select("id,name").execute().data
        category_names = {category["id"]: category["name"] for category in categories}
        product_inventory: dict[str, dict[str, int]] = {}
        for row in inventory:
            product_inventory.setdefault(row["product_id"], {})[row["location_id"]] = row["stock_quantity"]
        for product in products:
            product["category_name"] = category_names.get(product["category_id"], "")
            product["location_inventory"] = {
                location["id"]: product_inventory.get(product["id"], {}).get(location["id"], 0)
                for location in allowed_locations
            }
        return {"products": products, "categories": categories, "mode": "supabase"}
    except Exception as exc:
        raise database_setup_error(exc, "Products and location inventory are temporarily unavailable.") from exc


@app.post("/api/admin/products", status_code=201, dependencies=[Depends(require_owner)])
def create_product(product: ProductCreate):
    category_id = product.category_id.strip()
    location_ids = set(product.location_stock)
    if not location_ids <= {location["id"] for location in DELIVERY_LOCATIONS}:
        raise HTTPException(status_code=422, detail="Choose only valid delivery locations.")

    product_data = {
        "category_id": category_id,
        "name": product.name.strip(),
        "description": product.description.strip(),
        "price": float(product.price),
        "unit": product.unit.strip(),
        "image_url": product.image_url.strip(),
        "stock_quantity": 0,
    }
    if len(product_data["name"]) < 2 or not product_data["unit"]:
        raise HTTPException(status_code=422, detail="Enter a product name and unit.")
    client = supabase_client()
    if client is None:
        if not any(category["id"] == category_id for category in CATEGORIES):
            raise HTTPException(status_code=422, detail="Choose a valid product category.")
        if any(
            existing["category_id"] == category_id
            and existing["name"].casefold() == product_data["name"].casefold()
            for existing in DEMO_PRODUCTS
        ):
            raise HTTPException(status_code=409, detail="A product with this name already exists in that category.")
        product_id = str(uuid4())
        DEMO_PRODUCTS.append({"id": product_id, **product_data, "is_available": True})
        DEMO_LOCATION_STOCK[product_id] = {
            location["id"]: product.location_stock.get(location["id"], 0)
            for location in DELIVERY_LOCATIONS
        }
        return {"product_id": product_id, "mode": "demo"}

    try:
        category = client.table("categories").select("id").eq("id", category_id).maybe_single().execute().data
        if category is None:
            raise HTTPException(status_code=422, detail="Choose a valid product category.")
        product_id = client.rpc("create_market_product", {
            "p_category_id": category_id,
            "p_name": product_data["name"],
            "p_description": product_data["description"],
            "p_price": str(product.price),
            "p_unit": product_data["unit"],
            "p_image_url": product_data["image_url"],
            "p_location_stock": product.location_stock,
        }).execute().data
        return {"product_id": product_id, "mode": "supabase"}
    except HTTPException:
        raise
    except Exception as exc:
        error_text = str(exc).casefold()
        if "unique" in error_text or "duplicate" in error_text:
            raise HTTPException(status_code=409, detail="A product with this name already exists in that category.") from exc
        raise database_setup_error(exc, "The product could not be created.") from exc


@app.patch("/api/admin/products/{product_id}/price", dependencies=[Depends(require_owner)])
def update_product_price(product_id: str, update: PriceUpdate):
    client = supabase_client()
    if client is None:
        product = next((item for item in DEMO_PRODUCTS if item["id"] == product_id), None)
        if product is None:
            raise HTTPException(status_code=404, detail="Product not found.")
        product["price"] = float(update.price)
        return {"product_id": product_id, "price": float(update.price), "mode": "demo"}
    try:
        result = client.table("products").update({"price": str(update.price)}).eq("id", product_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Product not found.")
        return {"product_id": product_id, "price": float(update.price), "mode": "supabase"}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="The product price could not be updated.") from exc


@app.patch("/api/admin/products/{product_id}/stock/{location_id}", dependencies=[Depends(require_admin)])
def update_product_stock(product_id: str, location_id: str, update: StockQuantityUpdate, request: Request):
    role = request.session.get("admin_role", "owner")
    assigned_locations = request.session.get("admin_location_ids", [])
    if not any(location["id"] == location_id for location in DELIVERY_LOCATIONS):
        raise HTTPException(status_code=422, detail="Choose a valid delivery location.")
    if role == "location" and location_id not in assigned_locations:
        raise HTTPException(status_code=403, detail="You can only manage inventory for your assigned locations.")

    client = supabase_client()
    if client is None:
        product = next((item for item in DEMO_PRODUCTS if item["id"] == product_id), None)
        if product is None:
            raise HTTPException(status_code=404, detail="Product not found.")
        DEMO_LOCATION_STOCK.setdefault(product_id, {})[location_id] = update.stock_quantity
        return {"product_id": product_id, "location_id": location_id, "stock_quantity": update.stock_quantity, "mode": "demo"}
    try:
        product = client.table("products").select("id").eq("id", product_id).maybe_single().execute().data
        if product is None:
            raise HTTPException(status_code=404, detail="Product not found.")
        client.table("product_location_inventory").upsert({
            "product_id": product_id,
            "location_id": location_id,
            "stock_quantity": update.stock_quantity,
        }, on_conflict="product_id,location_id").execute()
        return {"product_id": product_id, "location_id": location_id, "stock_quantity": update.stock_quantity, "mode": "supabase"}
    except HTTPException:
        raise
    except Exception as exc:
        raise database_setup_error(exc, "The location inventory could not be updated.") from exc


@app.get("/api/catalog")
def get_catalog(
    category: str | None = Query(default=None, max_length=60),
    search: str | None = Query(default=None, max_length=100),
    location_id: str | None = Query(default=None, max_length=40),
):
    if location_id is not None and not any(location["id"] == location_id for location in DELIVERY_LOCATIONS):
        raise HTTPException(status_code=422, detail="Choose a valid delivery location.")
    client = supabase_client()
    if client is None:
        categories = CATEGORIES
        products = [dict(product) for product in DEMO_PRODUCTS]
        inventory = [
            {"product_id": product["id"], "location_id": location["id"],
             "stock_quantity": DEMO_LOCATION_STOCK.get(product["id"], {}).get(location["id"], 0)}
            for product in products for location in DELIVERY_LOCATIONS
        ]
        mode = "demo"
    else:
        try:
            categories = client.table("categories").select("id,name,slug").order("sort_order").execute().data
            products = client.table("products").select(
                "id,category_id,name,description,price,unit,image_url"
            ).eq("is_available", True).order("name").execute().data
            inventory = client.table("product_location_inventory").select(
                "product_id,location_id,stock_quantity"
            ).execute().data
        except Exception as exc:
            logger.exception("Supabase catalog query failed")
            raise database_setup_error(exc, "The product catalog and location inventory are temporarily unavailable.") from exc
        mode = "supabase"

    product_inventory: dict[str, dict[str, int]] = {}
    for row in inventory:
        product_inventory.setdefault(row["product_id"], {})[row["location_id"]] = row["stock_quantity"]
    location_names = {location["id"]: location["name"] for location in DELIVERY_LOCATIONS}
    for product in products:
        product_locations = product_inventory.get(product["id"], {})
        product["available_locations"] = [
            location_names[location["id"]]
            for location in DELIVERY_LOCATIONS
            if product_locations.get(location["id"], 0) > 0
        ]
        product["stock_quantity"] = product_locations.get(location_id, 0) if location_id else 0
    if location_id:
        products = [product for product in products if product["stock_quantity"] > 0]
    if category:
        products = [product for product in products if product["category_id"] == category]
    if search:
        term = search.strip().casefold()
        products = [product for product in products if term in product["name"].casefold() or term in (product.get("description") or "").casefold()]
    return {"categories": categories, "products": products, "mode": mode}


@app.post("/api/orders")
def create_order(order: OrderRequest):
    location = next((item for item in DELIVERY_LOCATIONS if item["id"] == order.delivery_location_id), None)
    if location is None:
        raise HTTPException(status_code=422, detail="Please choose a valid delivery location.")
    try:
        items = normalize_order_items(order.items)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    client = supabase_client()
    if client is None:
        products = {product["id"]: product for product in DEMO_PRODUCTS}
        order_lines = []
        for item in items:
            product = products.get(item["product_id"])
            stock = DEMO_LOCATION_STOCK.get(item["product_id"], {}).get(location["id"], 0)
            if product is None or stock < item["quantity"]:
                raise HTTPException(status_code=409, detail="A requested item is unavailable or out of stock.")
            unit_price = float(product["price"])
            order_lines.append({
                "product_id": product["id"],
                "product_name": product["name"],
                "quantity": item["quantity"],
                "unit_price": unit_price,
                "line_total": round(unit_price * item["quantity"], 2),
            })
        for item in items:
            DEMO_LOCATION_STOCK[item["product_id"]][location["id"]] -= item["quantity"]
        order_id = str(uuid4())
        DEMO_ORDERS.insert(0, {
            "id": order_id,
            "customer_name": order.customer_name.strip(),
            "customer_phone": order.customer_phone.strip(),
            "customer_email": (order.customer_email or "").strip() or None,
            "sms_consent": order.sms_consent,
            "delivery_address": order.delivery_address.strip(),
            "delivery_location_id": location["id"],
            "delivery_location_name": location["name"],
            "total": round(sum(line["line_total"] for line in order_lines), 2),
            "status": "placed",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "order_items": order_lines,
        })
        notifications_sent, notification_warnings = send_order_notifications(
            order_id,
            order.customer_name.strip(),
            (order.customer_email or "").strip() or None,
            order.customer_phone.strip(),
            order.sms_consent,
            location["name"],
            order_lines,
            round(sum(line["line_total"] for line in order_lines), 2),
        )
        return {
            "order_id": order_id,
            "mode": "demo",
            "message": "Demo order received. Configure Supabase to save real orders.",
            "notifications_sent": notifications_sent,
            "notification_warnings": notification_warnings,
        }

    try:
        result = client.rpc("place_order", {
            "p_customer_name": order.customer_name.strip(),
            "p_customer_phone": order.customer_phone.strip(),
            "p_customer_email": (order.customer_email or "").strip() or None,
            "p_sms_consent": order.sms_consent,
            "p_delivery_address": order.delivery_address.strip(),
            "p_delivery_location_id": location["id"],
            "p_items": items,
        }).execute()
        order_id = str(result.data)
    except Exception as exc:
        error_text = str(exc)
        if any(code in error_text for code in ("PGRST202", "PGRST205", "42P01", "42883")):
            logger.exception("Supabase order RPC/schema is unavailable")
            raise database_setup_error(exc, "The order service is temporarily unavailable.") from exc
        if "unavailable or out of stock" in error_text.casefold():
            raise HTTPException(
                status_code=409,
                detail="One or more items are no longer available at the selected location. Refresh the catalog and try again.",
            ) from exc
        if any(message in error_text.casefold() for message in (
            "item quantity must be",
            "a valid delivery location must be selected",
            "order items must be provided",
            "an order must contain",
        )):
            raise HTTPException(status_code=422, detail="The order details are invalid. Refresh the page and try again.") from exc
        logger.exception("Supabase order creation failed")
        raise HTTPException(
            status_code=503,
            detail="The order service is temporarily unavailable. Check the server log for the Supabase error.",
        ) from exc
    try:
        saved_order = client.table("customer_orders").select(
            "customer_name,customer_phone,customer_email,sms_consent,total,"
            "order_items(product_name,quantity,unit_price,line_total)"
        ).eq("id", order_id).maybe_single().execute().data
        if not saved_order:
            raise RuntimeError("The saved order could not be loaded for notifications.")
    except Exception as exc:
        logger.warning("Order %s notification details could not be loaded (%s).", order_id[:8].upper(), type(exc).__name__)
        return {
            "order_id": order_id,
            "mode": "supabase",
            "message": "Your order has been placed.",
            "notifications_sent": [],
            "notification_warnings": ["Your order was saved, but its email and SMS confirmations could not be prepared."],
        }

    notifications_sent, notification_warnings = send_order_notifications(
        order_id,
        saved_order["customer_name"],
        saved_order.get("customer_email"),
        saved_order["customer_phone"],
        saved_order["sms_consent"],
        location["name"],
        saved_order["order_items"],
        float(saved_order["total"]),
    )
    return {
        "order_id": order_id,
        "mode": "supabase",
        "message": "Your order has been placed.",
        "notifications_sent": notifications_sent,
        "notification_warnings": notification_warnings,
    }


@app.get("/api/order-status")
def get_order_status(order_number: str = Query(min_length=8, max_length=8)):
    order_number = order_number.strip().upper()
    if any(character not in "0123456789ABCDEF" for character in order_number):
        raise HTTPException(status_code=422, detail="Enter the 8-character order number.")
    client = supabase_client()
    if client is None:
        matches = [order for order in DEMO_ORDERS if order["id"][:8].upper() == order_number]
        if not matches:
            raise HTTPException(status_code=404, detail="We couldn't find an order with that number.")
        if len(matches) > 1:
            raise HTTPException(status_code=409, detail="This order number is ambiguous. Please contact the market.")
        order = matches[0]
        return {
            "order_number": order["id"][:8].upper(),
            "status": order["status"],
            "delivery_location": order.get("delivery_location_name", "Unassigned"),
            "created_at": order["created_at"],
        }
    try:
        result = client.rpc("lookup_order_status", {"p_order_number": order_number}).execute().data
        if not result:
            raise HTTPException(status_code=404, detail="We couldn't find an order with that number.")
        if len(result) > 1:
            raise HTTPException(status_code=409, detail="This order number is ambiguous. Please contact the market.")
        order = result[0]
        return {
            "order_number": order["order_number"],
            "status": order["status"],
            "delivery_location": order["delivery_location"],
            "created_at": order["created_at"],
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Order status is temporarily unavailable.") from exc


@app.post("/api/item-requests", status_code=201)
def create_item_request(request: ItemRequest):
    location = next((item for item in DELIVERY_LOCATIONS if item["id"] == request.delivery_location_id), None)
    if location is None:
        raise HTTPException(status_code=422, detail="Please choose a valid delivery location.")
    client = supabase_client()
    if client is None:
        category = next((item for item in CATEGORIES if item["id"] == request.category_id), None)
        if category is None:
            raise HTTPException(status_code=422, detail="Please choose a valid item category.")
        request_id = str(uuid4())
        DEMO_ITEM_REQUESTS.insert(0, {
            "id": request_id,
            "customer_name": request.customer_name.strip(),
            "customer_phone": request.customer_phone.strip(),
            "requested_name": request.requested_name.strip(),
            "category_name": category["name"],
            "category_id": request.category_id,
            "delivery_location_id": location["id"],
            "delivery_location_name": location["name"],
            "delivery_address": request.delivery_address.strip(),
            "note": (request.note or "").strip() or None,
            "status": "new",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        return {"request_id": request_id, "mode": "demo", "message": "Request noted in demo mode. Configure Supabase to save it."}
    try:
        category = client.table("categories").select("id").eq("id", request.category_id).maybe_single().execute().data
        if category is None:
            raise HTTPException(status_code=422, detail="Please choose a valid item category.")
        result = client.table("customer_item_requests").insert({
            "customer_name": request.customer_name.strip(),
            "customer_phone": request.customer_phone.strip(),
            "requested_name": request.requested_name.strip(),
            "category_id": request.category_id,
            "delivery_location_id": location["id"],
            "delivery_address": request.delivery_address.strip(),
            "note": (request.note or "").strip() or None,
        }).execute()
        return {"request_id": result.data[0]["id"], "mode": "supabase", "message": "Thanks. We have added your item request."}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Your request could not be saved right now. Please try again.") from exc
