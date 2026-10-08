const state = {
  categories: [], products: [], locations: [], activeCategory: "all", search: "", cart: loadCart(), mode: "demo",
  selectedLocation: localStorage.getItem("root-river-location") || "",
  cartLocation: localStorage.getItem("root-river-cart-location") || "",
};
const currency = new Intl.NumberFormat("nb-NO", { style: "currency", currency: "NOK" });
const productGrid = document.querySelector("#product-grid");
const categoryList = document.querySelector("#category-list");
const requestView = document.querySelector("#request-view");
const orderStatusView = document.querySelector("#order-status-view");
const catalogView = document.querySelector("#catalog-view");

function loadCart() {
  try { return JSON.parse(localStorage.getItem("root-river-cart") || "{}"); }
  catch { return {}; }
}

function saveCart() {
  localStorage.setItem("root-river-cart", JSON.stringify(state.cart));
  if (Object.keys(state.cart).length) localStorage.setItem("root-river-cart-location", state.cartLocation);
  else localStorage.removeItem("root-river-cart-location");
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, character => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[character]);
}

function getImageUrl(value) {
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) ? url.href : "";
  } catch { return ""; }
}

async function loadCatalog() {
  const parameters = new URLSearchParams();
  if (state.activeCategory !== "all" && state.activeCategory !== "requests" && state.activeCategory !== "track-order") parameters.set("category", state.activeCategory);
  if (state.search) parameters.set("search", state.search);
  if (state.selectedLocation) parameters.set("location_id", state.selectedLocation);
  const [response, locationsResponse] = await Promise.all([
    fetch(`/api/catalog?${parameters}`),
    state.locations.length ? Promise.resolve(null) : fetch("/api/delivery-locations"),
  ]);
  if (!response.ok) {
    const result = await response.json();
    throw new Error(result.detail || "The market is having trouble loading.");
  }
  if (locationsResponse && !locationsResponse.ok) {
    const result = await locationsResponse.json();
    throw new Error(result.detail || "Delivery locations are temporarily unavailable.");
  }
  const [catalog, locationsResult] = await Promise.all([
    response.json(),
    locationsResponse ? locationsResponse.json() : Promise.resolve({ locations: state.locations }),
  ]);
  state.categories = catalog.categories;
  state.products = catalog.products;
  state.locations = locationsResult.locations;
  state.mode = catalog.mode;
  renderRequestCategories();
  renderDeliveryLocations();
  document.querySelector("#connection-status").textContent = state.mode === "demo" ? "Preview market · connect Supabase to take live orders" : "Market is open · items updated live";
  renderCategories();
  renderProducts();
}

function renderCategories() {
  const options = [{ id: "all", name: "Everything" }, ...state.categories, { id: "requests", name: "Customer requests" }, { id: "track-order", name: "Check order status" }];
  categoryList.innerHTML = options.map(item => `<button class="category-chip ${state.activeCategory === item.id ? "is-active" : ""}" data-category="${escapeHtml(item.id)}" aria-pressed="${state.activeCategory === item.id}">${escapeHtml(item.name)}${item.id === "requests" ? " <span aria-hidden=\"true\">↗</span>" : ""}</button>`).join("");
  categoryList.querySelectorAll("button").forEach(button => button.addEventListener("click", () => {
    state.activeCategory = button.dataset.category;
    document.querySelector("#request-message").textContent = "";
    document.querySelector("#order-status-message").textContent = "";
    document.querySelector("#section-title").textContent = state.activeCategory === "requests" ? "Customer requests" : state.activeCategory === "track-order" ? "Check order status" : state.activeCategory === "all" ? "Shop the market" : state.categories.find(item => item.id === state.activeCategory)?.name || "Shop the market";
    catalogView.hidden = state.activeCategory === "requests" || state.activeCategory === "track-order";
    requestView.hidden = state.activeCategory !== "requests";
    orderStatusView.hidden = state.activeCategory !== "track-order";
    renderCategories();
    if (state.activeCategory !== "requests" && state.activeCategory !== "track-order") loadCatalog().catch(showCatalogError);
  }));
}

function renderRequestCategories() {
  const select = document.querySelector("#request-category");
  const selectedCategory = select.value;
  select.innerHTML = '<option value="">Choose a category</option>' + state.categories.map(category =>
    `<option value="${escapeHtml(category.id)}">${escapeHtml(category.name)}</option>`
  ).join("");
  if (state.categories.some(category => category.id === selectedCategory)) select.value = selectedCategory;
}

function renderDeliveryLocations() {
  const options = '<option value="">Choose your nearest location</option>' + state.locations.map(location =>
    `<option value="${escapeHtml(location.id)}">${escapeHtml(location.name)}</option>`
  ).join("");
  const shopSelect = document.querySelector("#delivery-location");
  if (!state.locations.some(location => location.id === state.selectedLocation)) state.selectedLocation = "";
  shopSelect.innerHTML = options;
  shopSelect.value = state.selectedLocation;
  const requestSelect = document.querySelector("#request-location");
  const previousRequestLocation = requestSelect.value;
  requestSelect.innerHTML = options;
  requestSelect.value = state.locations.some(location => location.id === previousRequestLocation)
    ? previousRequestLocation : state.selectedLocation;
  localStorage.setItem("root-river-location", state.selectedLocation);
  updateLocationNote();
}

function updateLocationNote() {
  const location = state.locations.find(item => item.id === state.selectedLocation);
  document.querySelector("#checkout-location-note").textContent = location
    ? `Delivery from ${location.name}. Change the shop location above to see another location's stock.`
    : "Choose a shop location above to see local stock and place an order.";
  const orderButton = document.querySelector("#checkout-form button[type=submit]");
  if (orderButton) orderButton.disabled = !location;
}

function renderProducts() {
  const count = state.products.length;
  document.querySelector("#product-count").textContent = count === 1 ? "1 good thing, picked for you" : `${count} good things, picked for you`;
  document.querySelector("#empty-state").hidden = count !== 0;
  productGrid.innerHTML = state.products.map((product, index) => {
    const inCart = state.cart[product.id]?.quantity || 0;
    const inStock = Boolean(state.selectedLocation) && product.stock_quantity > 0;
    const availableLocations = (product.available_locations || []).join(", ");
    const image = getImageUrl(product.image_url);
    return `<article class="product-card" style="--card-index:${index}">
      <div class="product-image-wrap">${image ? `<img class="product-image" src="${escapeHtml(image)}" alt="${escapeHtml(product.name)}" loading="lazy">` : `<div class="image-placeholder">FRESH<br>PICK</div>`}<span class="stock-label ${!state.selectedLocation ? "" : inStock ? "" : "is-sold"}">${!state.selectedLocation ? "CHOOSE LOCATION" : inStock ? "IN SEASON" : "SOLD OUT"}</span></div>
      <div class="product-copy"><div class="product-title-row"><h3>${escapeHtml(product.name)}</h3><strong>${currency.format(Number(product.price))}</strong></div><p>${escapeHtml(product.description || "Market favourite")}</p><p class="availability-note">${availableLocations ? `Available at: ${escapeHtml(availableLocations)}` : "Not stocked at a location yet"}</p><div class="product-action"><span>/${escapeHtml(product.unit || "each")}</span>${inStock ? inCart ? `<span class="added-note">${inCart} in basket</span><button class="add-button is-added" data-add="${escapeHtml(product.id)}" aria-label="Add another ${escapeHtml(product.name)}">+</button>` : `<button class="add-button" data-add="${escapeHtml(product.id)}" aria-label="Add ${escapeHtml(product.name)} to basket">+</button>` : `<span class="sold-note">${state.selectedLocation ? "Back soon" : "Choose a location"}</span>`}</div></div>
    </article>`;
  }).join("");
  productGrid.querySelectorAll("[data-add]").forEach(button => button.addEventListener("click", () => addToCart(button.dataset.add)));
}

function addToCart(productId) {
  const product = state.products.find(item => item.id === productId);
  if (!state.selectedLocation || !product || (state.cart[productId]?.quantity || 0) >= product.stock_quantity) return;
  state.cartLocation = state.selectedLocation;
  state.cart[productId] = { product_id: product.id, name: product.name, price: Number(product.price), unit: product.unit, image_url: product.image_url, quantity: (state.cart[productId]?.quantity || 0) + 1 };
  saveCart();
  renderProducts();
  renderCart();
}

function updateQuantity(productId, change) {
  const nextQuantity = (state.cart[productId]?.quantity || 0) + change;
  const product = state.products.find(item => item.id === productId);
  if (nextQuantity <= 0) delete state.cart[productId];
  else if (product && nextQuantity <= product.stock_quantity) state.cart[productId].quantity = nextQuantity;
  saveCart();
  renderProducts();
  renderCart();
}

function renderCart() {
  const entries = Object.values(state.cart);
  const totalItems = entries.reduce((sum, item) => sum + item.quantity, 0);
  const total = entries.reduce((sum, item) => sum + item.quantity * item.price, 0);
  document.querySelector("#cart-count").textContent = totalItems;
  document.querySelector("#basket-count").textContent = `${totalItems} ${totalItems === 1 ? "ITEM" : "ITEMS"}`;
  document.querySelector("#basket-empty").hidden = entries.length !== 0;
  document.querySelector("#checkout-area").hidden = entries.length === 0;
  document.querySelector("#basket-lines").innerHTML = entries.map(item => `<div class="basket-line"><div class="basket-line-info"><strong>${escapeHtml(item.name)}</strong><span>${currency.format(item.price)} / ${escapeHtml(item.unit)}</span></div><div class="quantity-control"><button type="button" data-change="-1" data-product="${escapeHtml(item.product_id)}" aria-label="Remove one ${escapeHtml(item.name)}">−</button><span>${item.quantity}</span><button type="button" data-change="1" data-product="${escapeHtml(item.product_id)}" aria-label="Add one ${escapeHtml(item.name)}">+</button></div><strong class="line-price">${currency.format(item.quantity * item.price)}</strong></div>`).join("");
  document.querySelector("#basket-total").textContent = currency.format(total);
  document.querySelector("#order-button-total").textContent = currency.format(total);
  updateLocationNote();
  document.querySelectorAll("[data-change]").forEach(button => button.addEventListener("click", () => updateQuantity(button.dataset.product, Number(button.dataset.change))));
}

function showCatalogError(error) {
  productGrid.innerHTML = `<p class="load-error">${escapeHtml(error.message || "Could not load the market.")}</p>`;
}

function showFormMessage(selector, message, isError = false) {
  const element = document.querySelector(selector);
  element.textContent = message;
  element.classList.toggle("is-error", isError);
}

document.querySelector("#search-input").addEventListener("input", event => {
  state.search = event.target.value.trim();
  if (state.activeCategory !== "requests" && state.activeCategory !== "track-order") loadCatalog().catch(showCatalogError);
});

document.addEventListener("keydown", event => {
  if (event.key === "/" && !["INPUT", "TEXTAREA"].includes(document.activeElement.tagName)) {
    event.preventDefault();
    document.querySelector("#search-input").focus();
  }
});

document.querySelector("#checkout-form").addEventListener("submit", async event => {
  event.preventDefault();
  const form = event.currentTarget;
  const submitButton = form.querySelector("button[type=submit]");
  submitButton.disabled = true;
  showFormMessage("#order-message", "Placing your order...");
  const formData = new FormData(form);
  const payload = Object.fromEntries(formData.entries());
  payload.sms_consent = form.elements.sms_consent.checked;
  if (!state.selectedLocation) {
    showFormMessage("#order-message", "Choose a shop location before placing your order.", true);
    submitButton.disabled = false;
    return;
  }
  payload.delivery_location_id = state.selectedLocation;
  payload.items = Object.values(state.cart).map(item => ({ product_id: item.product_id, quantity: item.quantity }));
  try {
    const response = await fetch("/api/orders", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "We couldn't place your order.");
    state.cart = {};
    state.cartLocation = "";
    saveCart();
    renderCart();
    renderProducts();
    form.reset();
    const orderNumber = String(result.order_id).slice(0, 8).toUpperCase();
    const notificationsSent = (result.notifications_sent || []).join(" and ");
    const notificationSummary = notificationsSent
      ? ` Confirmation sent by ${notificationsSent}.`
      : "";
    const notificationWarnings = (result.notification_warnings || []).join(" ");
    showFormMessage(
      "#order-message",
      `${result.message} Order number: ${orderNumber}. Use “Track an order” to check its status.${notificationSummary}${notificationWarnings ? ` ${notificationWarnings}` : ""}`,
    );
    await loadCatalog();
  } catch (error) {
    showFormMessage("#order-message", error.message, true);
  } finally { submitButton.disabled = false; }
});

async function checkOrderStatus(form, messageSelector, resultSelector) {
  const submitButton = form.querySelector("button[type=submit]");
  const orderNumber = String(new FormData(form).get("order_number") || "").trim().toUpperCase();
  submitButton.disabled = true;
  document.querySelector(resultSelector).textContent = "";
  showFormMessage(messageSelector, "Looking up your order...");
  try {
    const response = await fetch(`/api/order-status?order_number=${encodeURIComponent(orderNumber)}`);
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "We couldn't find that order.");
    const status = result.status.replaceAll("_", " ");
    const createdAt = result.created_at ? new Date(result.created_at).toLocaleString() : "";
    document.querySelector(resultSelector).innerHTML = `<article class="order-card"><div class="order-topline"><div><span class="order-reference">ORDER ${escapeHtml(result.order_number)}</span>${createdAt ? `<span class="order-date">Placed ${escapeHtml(createdAt)}</span>` : ""}<span class="order-date">Delivery location: ${escapeHtml(result.delivery_location)}</span></div><span class="order-status">${escapeHtml(status)}</span></div></article>`;
    showFormMessage(messageSelector, "");
  } catch (error) {
    showFormMessage(messageSelector, error.message, true);
  } finally { submitButton.disabled = false; }
}

document.querySelector("#order-status-form").addEventListener("submit", event => {
  event.preventDefault();
  checkOrderStatus(event.currentTarget, "#order-status-message", "#order-status-result");
});

document.querySelector("#basket-order-status-form").addEventListener("submit", event => {
  event.preventDefault();
  checkOrderStatus(event.currentTarget, "#basket-order-status-message", "#basket-order-status-result");
});

document.querySelector("#request-form").addEventListener("submit", async event => {
  event.preventDefault();
  const form = event.currentTarget;
  const submitButton = form.querySelector("button[type=submit]");
  submitButton.disabled = true;
  showFormMessage("#request-message", "Sending your request...");
  const payload = Object.fromEntries(new FormData(form).entries());
  try {
    const response = await fetch("/api/item-requests", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "We couldn't save your request.");
    form.reset();
    showFormMessage("#request-message", result.message);
  } catch (error) {
    showFormMessage("#request-message", error.message, true);
  } finally { submitButton.disabled = false; }
});

document.querySelector("#delivery-location").addEventListener("change", event => {
  const nextLocation = event.target.value;
  if (nextLocation === state.selectedLocation) return;
  if (Object.keys(state.cart).length && state.cartLocation !== nextLocation) {
    if (!window.confirm("Changing location will clear your basket so every item matches the new location. Continue?")) {
      event.target.value = state.selectedLocation;
      return;
    }
    state.cart = {};
    state.cartLocation = "";
    saveCart();
    renderCart();
  }
  state.selectedLocation = nextLocation;
  localStorage.setItem("root-river-location", nextLocation);
  updateLocationNote();
  loadCatalog().catch(showCatalogError);
});

document.querySelector("#request-shortcut").addEventListener("click", () => {
  state.activeCategory = "requests";
  document.querySelector("#section-title").textContent = "Customer requests";
  catalogView.hidden = true;
  requestView.hidden = false;
  orderStatusView.hidden = true;
  renderCategories();
});

const installHelpDialog = document.querySelector("#install-help-dialog");
document.querySelector("#install-help-button").addEventListener("click", () => installHelpDialog.showModal());
installHelpDialog.addEventListener("click", event => {
  if (event.target === installHelpDialog) installHelpDialog.close();
});

if ("serviceWorker" in navigator && (location.protocol === "https:" || location.hostname === "localhost")) {
  navigator.serviceWorker.register("/service-worker.js").catch(error => {
    console.warn("The market could not enable its offline app shell.", error);
  });
}

renderCart();
loadCatalog().catch(showCatalogError);
