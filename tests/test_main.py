import json

import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient

import main as app_module
from main import OrderItem, OrderRequest, app, normalize_order_items

client = TestClient(app)


def test_progressive_web_app_files_are_served():
    manifest_response = client.get("/manifest.webmanifest")
    worker_response = client.get("/service-worker.js")
    icon_response = client.get("/static/icons/apple-touch-icon.png")

    assert manifest_response.status_code == 200
    assert manifest_response.headers["content-type"].startswith("application/manifest+json")
    manifest = json.loads(manifest_response.text)
    assert manifest["display"] == "standalone"
    assert manifest["start_url"] == "/"
    assert {icon["sizes"] for icon in manifest["icons"]} == {"192x192", "512x512"}
    assert worker_response.status_code == 200
    assert worker_response.headers["service-worker-allowed"] == "/"
    assert "api" not in worker_response.text.casefold()
    assert icon_response.status_code == 200
    assert icon_response.headers["content-type"] == "image/png"
    assert b"apple-mobile-web-app-capable" in client.get("/").content


def test_order_items_merge_duplicate_products():
    items = [OrderItem(product_id="rice", quantity=2), OrderItem(product_id="rice", quantity=3)]
    assert normalize_order_items(items) == [{"product_id": "rice", "quantity": 5}]


def test_order_items_reject_combined_quantity_over_limit():
    items = [OrderItem(product_id="rice", quantity=60), OrderItem(product_id="rice", quantity=40)]
    with pytest.raises(ValueError, match="maximum quantity"):
        normalize_order_items(items)


def test_order_requires_at_least_one_item():
    with pytest.raises(ValidationError):
        OrderRequest(customer_name="A Customer", customer_phone="1234567", delivery_address="1 Main St", items=[])


def test_missing_supabase_schema_has_actionable_inventory_error():
    error = app_module.database_setup_error(Exception("PGRST205: table not found"), "Unavailable.")
    assert error.status_code == 503
    assert "run the latest sql/schema.sql" in error.detail.casefold()
    assert "product_location_inventory" in error.detail
    assert "location-admin setup" not in error.detail


def test_demo_catalog_has_categories_and_products(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.setattr(app_module, "DEMO_LOCATION_STOCK", {
        product_id: dict(stocks) for product_id, stocks in app_module.DEMO_LOCATION_STOCK.items()
    })
    response = client.get("/api/catalog")
    assert response.status_code == 200
    assert "vegetables" in {category["id"] for category in response.json()["categories"]}
    assert any(product["image_url"] for product in response.json()["products"])
    locations = client.get("/api/delivery-locations").json()["locations"]
    assert [location["name"] for location in locations] == ["Skullerud", "Solli", "Sagane", "Fornebu", "Veitvet"]

    rice = next(product for product in response.json()["products"] if product["id"] == "demo-rice")
    assert rice["stock_quantity"] == 0
    assert rice["available_locations"] == ["Skullerud", "Solli", "Sagane", "Fornebu", "Veitvet"]
    solli_rice = client.get("/api/catalog?location_id=solli").json()["products"]
    assert next(product for product in solli_rice if product["id"] == "demo-rice")["stock_quantity"] == 10
    assert client.get("/api/catalog?location_id=unknown").status_code == 422


def test_catalog_database_error_is_logged_and_actionable(monkeypatch, caplog):
    class FailingQuery:
        def table(self, _name):
            return self

        def select(self, *_args):
            return self

        def order(self, *_args, **_kwargs):
            return self

        def execute(self):
            raise RuntimeError("PGRST205: table not found")

    monkeypatch.setattr(app_module, "supabase_client", FailingQuery)
    response = client.get("/api/catalog")

    assert response.status_code == 503
    assert "product_location_inventory" in response.json()["detail"]
    assert "Supabase catalog query failed" in caplog.text
    assert "PGRST205" in caplog.text


@pytest.mark.parametrize(
    ("rpc_error", "status_code", "detail_part"),
    [
        (
            "PGRST202: Could not find the function public.place_order with parameter p_sms_consent",
            503,
            "Run the latest sql/schema.sql",
        ),
        (
            "A requested item is unavailable or out of stock at the selected location.",
            409,
            "Refresh the catalog",
        ),
        (
            "Unexpected database connection failure",
            503,
            "Check the server log",
        ),
    ],
)
def test_order_rpc_errors_are_not_all_reported_as_conflicts(monkeypatch, caplog, rpc_error, status_code, detail_part):
    class FailingRpc:
        def execute(self):
            raise RuntimeError(rpc_error)

    class FailingClient:
        def rpc(self, *_args, **_kwargs):
            return FailingRpc()

    monkeypatch.setattr(app_module, "supabase_client", FailingClient)
    response = client.post("/api/orders", json={
        "customer_name": "A Customer",
        "customer_phone": "1234567890",
        "delivery_address": "1 Main Street",
        "delivery_location_id": "veitvet",
        "items": [{"product_id": "demo-rice", "quantity": 1}],
    })

    assert response.status_code == status_code
    assert detail_part.casefold() in response.json()["detail"].casefold()
    if status_code == 503:
        assert "Supabase order" in caplog.text or "Supabase order creation failed" in caplog.text


def test_demo_order_and_item_request_are_accepted(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.setattr(app_module, "DEMO_ORDERS", [])
    monkeypatch.setattr(app_module, "DEMO_ITEM_REQUESTS", [])
    monkeypatch.setattr(app_module, "DEMO_LOCATION_STOCK", {
        product_id: dict(stocks) for product_id, stocks in app_module.DEMO_LOCATION_STOCK.items()
    })
    order = client.post("/api/orders", json={
        "customer_name": "A Customer",
        "customer_phone": "1234567890",
        "delivery_address": "1 Main Street",
        "delivery_location_id": "veitvet",
        "items": [{"product_id": "demo-rice", "quantity": 2}],
    })
    request = client.post("/api/item-requests", json={
        "customer_name": "A Customer",
        "customer_phone": "1234567890",
        "requested_name": "Curry leaves",
        "category_id": "vegetables",
        "delivery_location_id": "veitvet",
        "delivery_address": "1 Main Street",
    })
    assert order.status_code == 200
    assert order.json()["mode"] == "demo"
    order_number = order.json()["order_id"][:8].upper()
    assert len(order_number) == 8
    tracking = client.get(f"/api/order-status?order_number={order.json()['order_id'][:8]}")
    assert tracking.status_code == 200
    assert tracking.json()["status"] == "placed"
    assert tracking.json()["delivery_location"] == "Veitvet"
    assert "customer_name" not in tracking.json()
    assert client.get("/api/order-status?order_number=not-valid").status_code == 422
    assert request.status_code == 201
    assert request.json()["mode"] == "demo"
    assert client.get("/api/admin/item-requests").status_code == 401
    page = client.get("/").text
    checkout_form = page.index('id="checkout-form"')
    confirmation = page.index('id="order-message"')
    assert page.rfind("</div>", checkout_form, confirmation) > checkout_form
    assert 'id="basket-order-status-form"' in page
    assert 'name="sms_consent" type="checkbox"' in page
    assert client.get("/api/admin/item-requests").status_code == 401
    invalid_location_order = client.post("/api/orders", json={
        "customer_name": "A Customer",
        "customer_phone": "1234567890",
        "delivery_address": "1 Main Street",
        "delivery_location_id": "not-a-location",
        "items": [{"product_id": "demo-rice", "quantity": 1}],
    })
    assert invalid_location_order.status_code == 422


def test_order_confirmation_sends_details_to_opted_in_channels(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.setattr(app_module, "DEMO_ORDERS", [])
    monkeypatch.setattr(app_module, "DEMO_LOCATION_STOCK", {
        product_id: dict(stocks) for product_id, stocks in app_module.DEMO_LOCATION_STOCK.items()
    })
    sent = {}

    monkeypatch.setattr(
        app_module,
        "send_order_email",
        lambda recipient, subject, body: sent.update(email=(recipient, subject, body)),
    )
    monkeypatch.setattr(
        app_module,
        "send_order_sms",
        lambda recipient, body: sent.update(sms=(recipient, body)),
    )

    response = client.post("/api/orders", json={
        "customer_name": "A Customer",
        "customer_phone": "+4712345678",
        "customer_email": "customer@example.com",
        "sms_consent": True,
        "delivery_address": "1 Main Street",
        "delivery_location_id": "veitvet",
        "items": [{"product_id": "demo-rice", "quantity": 2}],
    })

    assert response.status_code == 200
    order_number = response.json()["order_id"][:8].upper()
    assert response.json()["notifications_sent"] == ["email", "SMS"]
    assert response.json()["notification_warnings"] == []
    assert sent["email"][0] == "customer@example.com"
    assert order_number in sent["email"][1]
    assert "2 x Basmati rice @ 8,50 kr = 17,00 kr" in sent["email"][2]
    assert "Total: 17,00 kr" in sent["email"][2]
    assert sent["sms"][0] == "+4712345678"
    assert order_number in sent["sms"][1]
    assert "2 x Basmati rice @ 8,50 kr = 17,00 kr" in sent["sms"][1]


def test_order_sms_is_not_sent_without_explicit_consent(monkeypatch):
    monkeypatch.setattr(
        app_module,
        "send_order_sms",
        lambda *_args: pytest.fail("SMS must not be sent without consent."),
    )
    sent, warnings = app_module.send_order_notifications(
        "12345678-abcd",
        "A Customer",
        None,
        "+4712345678",
        False,
        "Veitvet",
        [{"product_name": "Basmati rice", "quantity": 1, "unit_price": 8.5, "line_total": 8.5}],
        8.5,
    )
    assert sent == []
    assert any("SMS consent was not given" in warning for warning in warnings)


def test_demo_inventory_is_independent_per_location(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    stock = {
        product["id"]: {location["id"]: 0 for location in app_module.DELIVERY_LOCATIONS}
        for product in app_module.DEMO_PRODUCTS
    }
    stock["demo-rice"]["skullerud"] = 1
    stock["demo-rice"]["solli"] = 4
    monkeypatch.setattr(app_module, "DEMO_LOCATION_STOCK", stock)
    monkeypatch.setattr(app_module, "DEMO_ORDERS", [])

    order = client.post("/api/orders", json={
        "customer_name": "A Customer",
        "customer_phone": "1234567890",
        "delivery_address": "1 Main Street",
        "delivery_location_id": "skullerud",
        "items": [{"product_id": "demo-rice", "quantity": 1}],
    })
    assert order.status_code == 200
    assert client.post("/api/orders", json={
        "customer_name": "A Customer",
        "customer_phone": "1234567890",
        "delivery_address": "1 Main Street",
        "delivery_location_id": "skullerud",
        "items": [{"product_id": "demo-rice", "quantity": 1}],
    }).status_code == 409
    solli_rice = next(
        product for product in client.get("/api/catalog?location_id=solli").json()["products"]
        if product["id"] == "demo-rice"
    )
    assert solli_rice["stock_quantity"] == 4
    assert stock["demo-rice"]["skullerud"] == 0


def test_admin_can_review_orders_and_update_prices(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.setenv("ADMIN_PASSWORD", "test-admin-password")
    monkeypatch.setattr(app_module, "DEMO_ORDERS", [])
    monkeypatch.setattr(app_module, "DEMO_ITEM_REQUESTS", [])
    monkeypatch.setattr(app_module, "DEMO_PRODUCTS", [dict(product) for product in app_module.DEMO_PRODUCTS])
    monkeypatch.setattr(app_module, "DEMO_LOCATION_STOCK", {
        product_id: dict(stocks) for product_id, stocks in app_module.DEMO_LOCATION_STOCK.items()
    })

    with TestClient(app, base_url="https://testserver") as admin_client:
        assert admin_client.get("/api/admin/orders").status_code == 401
        assert admin_client.get("/api/admin/item-requests").status_code == 401
        assert admin_client.patch("/api/admin/products/demo-rice/price", json={"price": 12.5}).status_code == 401
        assert admin_client.patch("/api/admin/orders/test/status", json={"status": "completed"}).status_code == 401
        assert admin_client.post("/api/admin/login", json={"password": "wrong-password"}).status_code == 401
        assert admin_client.post("/api/admin/login", json={"password": "test-admin-password"}).status_code == 200

        order_response = admin_client.post("/api/orders", json={
            "customer_name": "Market Customer",
            "customer_phone": "1234567890",
            "delivery_address": "1 Main Street",
            "delivery_location_id": "solli",
            "items": [{"product_id": "demo-rice", "quantity": 2}],
        })
        order_id = order_response.json()["order_id"]
        orders = admin_client.get("/api/admin/orders").json()["orders"]
        assert orders[0]["id"] == order_id
        assert orders[0]["order_items"][0]["product_name"] == "Basmati rice"
        assert orders[0]["delivery_location_name"] == "Solli"
        status_response = admin_client.patch(f"/api/admin/orders/{order_id}/status", json={"status": "completed"})
        assert status_response.status_code == 200
        assert status_response.json()["status"] == "completed"
        completed_orders = admin_client.get("/api/admin/orders").json()["orders"]
        assert any(order["id"] == order_id and order["status"] == "completed" for order in completed_orders)
        assert admin_client.patch(f"/api/admin/orders/{order_id}/status", json={"status": "invalid"}).status_code == 422
        tracking = admin_client.get(f"/api/order-status?order_number={order_id[:8]}")
        assert tracking.status_code == 200
        assert tracking.json()["status"] == "completed"

        item_request = admin_client.post("/api/item-requests", json={
            "customer_name": "Market Customer",
            "customer_phone": "1234567890",
            "requested_name": "Curry leaves",
            "category_id": "vegetables",
            "delivery_location_id": "solli",
            "delivery_address": "1 Main Street",
            "note": "Fresh, please",
        })
        requests = admin_client.get("/api/admin/item-requests").json()["requests"]
        assert item_request.status_code == 201
        assert requests[0]["id"] == item_request.json()["request_id"]
        assert requests[0]["requested_name"] == "Curry leaves"
        assert requests[0]["category_name"] == "Vegetables"
        assert requests[0]["delivery_address"] == "1 Main Street"
        assert requests[0]["delivery_location_name"] == "Solli"
        assert requests[0]["note"] == "Fresh, please"

        price_response = admin_client.patch("/api/admin/products/demo-rice/price", json={"price": 12.5})
        assert price_response.status_code == 200
        catalog = admin_client.get("/api/catalog").json()["products"]
        rice = next(product for product in catalog if product["id"] == "demo-rice")
        assert rice["price"] == 12.5

        admin_client.post("/api/admin/logout")
        assert admin_client.get("/api/admin/orders").status_code == 401


def test_owner_can_create_product_with_location_specific_stock(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.setenv("ADMIN_PASSWORD", "test-admin-password")
    monkeypatch.setattr(app_module, "DEMO_PRODUCTS", [dict(product) for product in app_module.DEMO_PRODUCTS])
    monkeypatch.setattr(app_module, "DEMO_LOCATION_STOCK", {
        product_id: dict(stocks) for product_id, stocks in app_module.DEMO_LOCATION_STOCK.items()
    })

    payload = {
        "category_id": "fruits",
        "name": "Blood oranges",
        "description": "Sweet seasonal citrus",
        "price": 5.25,
        "unit": "1 kg",
        "image_url": "https://example.com/oranges.jpg",
        "location_stock": {"solli": 7, "veitvet": 3},
    }
    with TestClient(app, base_url="https://testserver") as owner_client:
        assert owner_client.post("/api/admin/products", json=payload).status_code == 401
        assert owner_client.post("/api/admin/login", json={"password": "test-admin-password"}).status_code == 200

        response = owner_client.post("/api/admin/products", json=payload)
        assert response.status_code == 201
        product_id = response.json()["product_id"]
        product = next(
            product for product in owner_client.get("/api/admin/products").json()["products"]
            if product["id"] == product_id
        )
        assert product["category_name"] == "Fruits"
        assert product["location_inventory"] == {
            "skullerud": 0,
            "solli": 7,
            "sagane": 0,
            "fornebu": 0,
            "veitvet": 3,
        }
        solli_catalog = owner_client.get("/api/catalog?location_id=solli").json()["products"]
        assert next(product for product in solli_catalog if product["id"] == product_id)["stock_quantity"] == 7
        sagane_catalog = owner_client.get("/api/catalog?location_id=sagane").json()["products"]
        assert all(product["id"] != product_id for product in sagane_catalog)
        assert owner_client.post("/api/admin/products", json=payload).status_code == 409
        assert owner_client.post("/api/admin/products", json={
            **payload,
            "name": "Invalid stock",
            "location_stock": {"unknown": 1},
        }).status_code == 422
        assert owner_client.post("/api/admin/products", json={
            **payload,
            "name": "No locations",
            "location_stock": {},
        }).status_code == 422


def test_owner_can_create_and_assign_location_admin(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.setenv("ADMIN_PASSWORD", "test-admin-password")
    monkeypatch.setattr(app_module, "DEMO_ADMIN_USERS", [])
    monkeypatch.setattr(app_module, "DEMO_ORDERS", [])
    monkeypatch.setattr(app_module, "DEMO_PRODUCTS", [dict(product) for product in app_module.DEMO_PRODUCTS])
    monkeypatch.setattr(app_module, "DEMO_LOCATION_STOCK", {
        product_id: dict(stocks) for product_id, stocks in app_module.DEMO_LOCATION_STOCK.items()
    })

    with TestClient(app, base_url="https://testserver") as owner_client:
        assert owner_client.post("/api/admin/login", json={"password": "test-admin-password"}).status_code == 200
        response = owner_client.post("/api/admin/location-admins", json={
            "username": "solli-team",
            "display_name": "Solli Team",
            "password": "a-strong-team-password",
            "location_ids": ["solli"],
        })
        assert response.status_code == 201
        assert response.json()["locations"] == ["Solli"]
        assert "password_hash" not in response.json()
        staff_id = response.json()["id"]

        order_response = owner_client.post("/api/orders", json={
            "customer_name": "Solli Customer",
            "customer_phone": "1234567890",
            "delivery_address": "1 Main Street",
            "delivery_location_id": "solli",
            "items": [{"product_id": "demo-rice", "quantity": 1}],
        })
        order_id = order_response.json()["order_id"]
        another_order = owner_client.post("/api/orders", json={
            "customer_name": "Veitvet Customer",
            "customer_phone": "1234567890",
            "delivery_address": "2 Main Street",
            "delivery_location_id": "veitvet",
            "items": [{"product_id": "demo-rice", "quantity": 1}],
        })

    with TestClient(app, base_url="https://testserver") as staff_client:
        login = staff_client.post("/api/admin/login", json={
            "username": "Solli-Team",
            "password": "a-strong-team-password",
        })
        assert login.status_code == 200
        assert login.json()["role"] == "location"
        assert staff_client.get("/api/admin/orders").json()["orders"][0]["id"] == order_id
        assert staff_client.patch(
            f"/api/admin/orders/{another_order.json()['order_id']}/status",
            json={"status": "completed"},
        ).status_code == 403
        staff_products = staff_client.get("/api/admin/products")
        assert staff_products.status_code == 200
        rice = next(product for product in staff_products.json()["products"] if product["id"] == "demo-rice")
        assert set(rice["location_inventory"]) == {"solli"}
        assert staff_client.post("/api/admin/products", json={
            "category_id": "fruits",
            "name": "Staff-created fruit",
            "price": 1,
            "location_stock": {"solli": 1},
        }).status_code == 403
        assert staff_client.patch(
            "/api/admin/products/demo-rice/stock/solli",
            json={"stock_quantity": 6},
        ).json()["stock_quantity"] == 6
        updated_rice = next(
            product for product in staff_client.get("/api/catalog?location_id=solli").json()["products"]
            if product["id"] == "demo-rice"
        )
        assert updated_rice["stock_quantity"] == 6
        assert staff_client.patch(
            "/api/admin/products/demo-rice/stock/veitvet",
            json={"stock_quantity": 6},
        ).status_code == 403
        assert staff_client.patch(
            "/api/admin/products/demo-rice/stock/solli",
            json={"stock_quantity": -1},
        ).status_code == 422
        assert staff_client.get("/api/admin/location-admins").status_code == 403
        assert staff_client.patch(
            f"/api/admin/orders/{order_id}/status",
            json={"status": "packing"},
        ).json()["status"] == "packing"

        with TestClient(app, base_url="https://testserver") as owner_client:
            assert owner_client.post("/api/admin/login", json={"password": "test-admin-password"}).status_code == 200
            assert owner_client.get("/api/admin/orders").json()["orders"][0]["id"] == another_order.json()["order_id"]
            assert len(owner_client.get("/api/admin/location-admins").json()["users"]) == 1
            assignment = owner_client.patch(
                f"/api/admin/location-admins/{staff_id}/locations",
                json={"location_ids": ["veitvet"]},
            )
            assert assignment.status_code == 200

        refreshed_orders = staff_client.get("/api/admin/orders").json()["orders"]
        assert len(refreshed_orders) == 1
        assert refreshed_orders[0]["id"] == another_order.json()["order_id"]
        assert staff_client.patch(
            f"/api/admin/orders/{order_id}/status",
            json={"status": "completed"},
        ).status_code == 403

        with TestClient(app, base_url="https://testserver") as owner_client:
            assert owner_client.post("/api/admin/login", json={"password": "test-admin-password"}).status_code == 200
            assert owner_client.patch(
                f"/api/admin/location-admins/{staff_id}/active",
                json={"is_active": False},
            ).status_code == 200
        assert staff_client.get("/api/admin/orders").status_code == 401
