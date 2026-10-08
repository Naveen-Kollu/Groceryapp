# Tellabelli Village Market

A Python grocery storefront with category-based shopping, product photos and prices in Norwegian kroner (NOK), stock-aware multi-item orders, and a separate customer item-request flow. Supabase stores the catalog, inventory, orders, and requests. The storefront runs in demo mode until you add Supabase credentials. Prices are formatted as NOK; changing the currency display does not convert existing stored prices.

## Run locally

From this folder, create and activate a virtual environment, then install dependencies:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Start the site on your computer:

```powershell
uvicorn main:app --reload
```

Open http://127.0.0.1:8000. Without Supabase credentials, sample products and demo checkout are shown; demo orders and price changes are held in memory and reset when the server restarts.

To test the responsive storefront from an iPhone on the same Wi-Fi, stop the server with Ctrl+C and start it listening on your local network:

```powershell
uvicorn main:app --host 0.0.0.0 --port 8000
```

Run `ipconfig` in PowerShell, find the computer's **IPv4 Address** under its Wi-Fi adapter, and open `http://<that-ip-address>:8000` in iPhone Safari while both devices are on the same Wi-Fi. If Windows asks, allow Python/Uvicorn on **Private networks only**. Keep the server running while testing. This is local-network access only; it is not a public URL, and PWA service-worker installation requires HTTPS (or localhost on the same device). For an installable iPhone home-screen app that works away from your Wi-Fi, deploy the site to a public HTTPS host.

## Use the market on iPhone

The customer storefront is an installable Progressive Web App (PWA). To use it on an iPhone away from your computer, deploy this FastAPI app to a public host with HTTPS and configure its environment variables there (`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `ADMIN_PASSWORD`, and a persistent `SESSION_SECRET`). Do not upload `.env` or expose secrets in browser code. The manifest and service worker install the storefront shell; catalog, checkout, status lookups, and admin actions still require an internet connection and the live API. API responses and customer/order data are deliberately not cached offline.

On the iPhone, open the deployed HTTPS URL in Safari, tap **Share**, choose **Add to Home Screen**, then tap **Add**. Open the new home-screen icon to launch it in its app-style window. The storefront includes an **Add to iPhone Home Screen** guide. Local `http://127.0.0.1:8000` works only on the computer; a URL on your Wi-Fi is not a secure public deployment and is not suitable for PWA installation.

## Deploy on a free Render URL

The included [`render.yaml`](render.yaml) configures a free Render web service. Render provides a temporary HTTPS address ending in `onrender.com`; you do not need to buy a domain to start. A free service may become idle and take a little while to respond to the next visit, so it is best for testing and temporary use rather than guaranteed always-on access.

1. Push this project to a GitHub repository. Do not commit `.env`; it is excluded by `.gitignore`.
2. Create a Supabase project and run [`sql/schema.sql`](sql/schema.sql) in its SQL Editor so orders and inventory persist when the web service restarts.
3. In Render, create a **Blueprint** from that GitHub repository and deploy the `tellabelli-village-market` service defined by `render.yaml`.
4. When prompted for environment variables, set `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and a strong unique `ADMIN_PASSWORD`. Render generates and stores `SESSION_SECRET`; `COOKIE_SECURE` is enabled in the Blueprint. Keep these values private and do not put them in frontend files.
5. After deployment, open the `onrender.com` URL shown on the Render service page. The public admin page is at `/admin`.

The free web service's local filesystem and in-memory demo data are not durable. Configure Supabase before accepting real orders; Supabase stores the catalog, inventory, orders, and requests across deploys and restarts. Free hosting can also have usage limits or availability changes, so check Render's current plan terms before relying on it.

When you buy a domain, add it to the Render service's **Custom Domains** settings and configure the DNS records Render provides. Render can serve the custom domain over HTTPS; the same app can then use that address without changing its routes. Visitors using the old `onrender.com` address may need to install the PWA again from the new domain.

## Admin area

Copy [`.env.example`](.env.example) to `.env` and set a private `ADMIN_PASSWORD` before signing in at http://127.0.0.1:8000/admin. The sign-in page has separate **Super admin** and **Location team admin** tabs. The super admin uses the owner password; location staff use the username and password created by the owner. Set `SESSION_SECRET` to a long random value so admin sessions remain signed securely across server restarts. When serving over HTTPS, set `COOKIE_SECURE=true`.

The owner admin can review all customer orders and item requests, update product prices, manage location-team accounts, and set stock by location. Location-team admins can manage stock only for their assigned locations and see/update only those locations' orders. All locations share one product catalog, with independent inventory at Skullerud, Solli, Sagane, Fornebu, and Veitvet. Customers choose a shop location to see its available products; each product also lists every location where it is in stock. Item requests require a location too. Admins can update order statuses; orders, including completed orders, are retained and are not automatically deleted. Customers can use the 8-character order number from checkout in the storefront's **Track an order** area or **Check order status** tab. Order confirmations include the order number, item names, quantities, prices, total, and location. Email is sent when the customer supplies an email and SMTP is configured; SMS is sent only when the customer explicitly opts in and Twilio is configured. The order number remains on screen if a notification cannot be sent. In demo mode, orders, item requests, team accounts, inventory, and price updates are temporary and reset when the server restarts. With Supabase configured, records are saved in the database.

## Connect Supabase

1. Create a Supabase project.
2. In the Supabase SQL Editor, run [`sql/schema.sql`](sql/schema.sql). It creates and seeds categories, products, and delivery locations; creates per-location inventory; stores customer orders and item requests; creates location-team account tables; and installs the order, product-creation, team-management, and public status-lookup functions. Re-run it for an existing project to install updates. On the first inventory migration, existing product stock quantities are moved to Skullerud only (not duplicated across locations); admins can then set each location's stock in the **Location inventory** section.
3. Copy [`.env.example`](.env.example) to `.env`. Set `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` from **Project Settings → API**, plus a strong `ADMIN_PASSWORD` and random `SESSION_SECRET`.
4. Restart the server. The market status will show that live catalog data is connected, and submitted orders and requests will be saved in Supabase.

Keep the service-role key and owner admin password only in this backend `.env`. Never put them in browser JavaScript or commit `.env` to source control. Location-team users are created and assigned by the owner in the admin portal; use unique strong passwords. The supplied SQL allows public reads of categories and available products; all writes run through the Python backend.

For a free real-inbox email test, use a separate Gmail test account. Enable 2-Step Verification and create a Google App Password at [Google App Passwords](https://myaccount.google.com/apppasswords). Put the Gmail address in `SMTP_USERNAME` and `SMTP_FROM_EMAIL`, the App Password in `SMTP_PASSWORD`, and set `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`, and `SMTP_USE_SSL=false` in `.env`. Do not use your regular Google password. Google notes that App Passwords are less secure and revokes them if you change your Google password, so this is best for local testing rather than a production sender. Some Google accounts do not offer App Passwords.

Alternatively, configure another SMTP provider in `.env` using `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, and `SMTP_FROM_EMAIL` (STARTTLS is used by default; set `SMTP_USE_SSL=true` for implicit TLS). To send SMS, configure `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, and `TWILIO_FROM_NUMBER`. Keep provider credentials private. Customers must tick the SMS consent checkbox; consent is stored with the order. Restart the server after changing `.env`. The API reports notification delivery failures separately; they do not undo a saved order.

## Catalog and orders

The super admin can add products in the **Product prices** section, choose a category, enter product details, and set starting stock at each selected location. Product and location inventory are saved together. Products with positive stock appear to customers at that location. Set `is_available` to false in Supabase to hide a product globally. In demo mode, new products and stock are held in memory and reset when the server restarts.

Orders capture customer name, phone, optional email, delivery address, selected location, line-item price snapshots, total, status, and time. `place_order` locks the selected product/location inventory rows and decrements stock in the same database transaction, so concurrent checkouts cannot oversell. Requests for missing products go into `customer_item_requests`, separate from the sellable catalog, and include the customer's selected location.

## Tests

```powershell
pytest
```
