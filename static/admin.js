const loginPanel = document.querySelector("#login-panel");
const dashboard = document.querySelector("#admin-dashboard");
const currency = new Intl.NumberFormat("nb-NO", { style: "currency", currency: "NOK" });
const orderStatuses = ["placed", "confirmed", "packing", "out_for_delivery", "completed", "cancelled"];
const adminState = { role: null, locations: [], locationIds: [], orders: [], hasMoreOrders: false };

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, character => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[character]);
}

function showMessage(selector, message, isError = false) {
  const element = document.querySelector(selector);
  element.textContent = message;
  element.classList.toggle("is-error", isError);
}

async function apiRequest(url, options = {}) {
  const response = await fetch(url, { credentials: "same-origin", ...options });
  const result = await response.json();
  if (!response.ok) {
    const error = new Error(result.detail || "The request could not be completed.");
    error.status = response.status;
    throw error;
  }
  return result;
}

function setSignedIn(signedIn, session = {}) {
  loginPanel.hidden = signedIn;
  dashboard.hidden = !signedIn;
  document.querySelector("#logout-button").hidden = !signedIn;
  adminState.role = signedIn ? session.role || "owner" : null;
  adminState.locationIds = signedIn ? session.location_ids || [] : [];
  document.querySelector("#owner-requests-section").hidden = !signedIn || adminState.role !== "owner";
  document.querySelector("#owner-prices-section").hidden = !signedIn || adminState.role !== "owner";
  document.querySelector("#location-admins-section").hidden = !signedIn || adminState.role !== "owner";
  document.querySelector("#inventory-section").hidden = !signedIn;
}

function setLoginTab(role) {
  const ownerSelected = role === "owner";
  document.querySelector("#owner-login-tab").classList.toggle("is-active", ownerSelected);
  document.querySelector("#owner-login-tab").setAttribute("aria-selected", String(ownerSelected));
  document.querySelector("#location-login-tab").classList.toggle("is-active", !ownerSelected);
  document.querySelector("#location-login-tab").setAttribute("aria-selected", String(!ownerSelected));
  document.querySelector("#owner-login-panel").hidden = !ownerSelected;
  document.querySelector("#location-login-panel").hidden = ownerSelected;
}

function renderOrders(orders) {
  const container = document.querySelector("#orders-list");
  document.querySelector("#load-more-orders").hidden = !adminState.hasMoreOrders;
  if (!orders.length) {
    container.innerHTML = '<p class="admin-empty">No orders match these filters.</p>';
    return;
  }
  const groups = new Map();
  orders.forEach(order => {
    const location = order.delivery_location_name || order.delivery_location || "Unassigned";
    if (!groups.has(location)) groups.set(location, []);
    groups.get(location).push(order);
  });
  container.innerHTML = [...groups.entries()].map(([location, locationOrders]) => `<section class="location-order-group">
    <h3>${escapeHtml(location)}</h3>
    ${locationOrders.map(order => {
    const items = order.order_items || [];
    const placedAt = order.created_at ? new Date(order.created_at).toLocaleString() : "Time unavailable";
    return `<article class="order-card">
      <div class="order-topline"><div><span class="order-reference">ORDER ${escapeHtml(String(order.id).slice(0, 8).toUpperCase())}</span><span class="order-date">${escapeHtml(placedAt)}</span></div><div class="order-status-control"><span class="order-status">${escapeHtml((order.status || "placed").replaceAll("_", " "))}</span><label class="sr-only" for="status-${escapeHtml(order.id)}">Update order status</label><select id="status-${escapeHtml(order.id)}" class="order-status-select" data-order-status="${escapeHtml(order.id)}">${orderStatuses.map(status => `<option value="${status}" ${status === order.status ? "selected" : ""}>${escapeHtml(status.replaceAll("_", " "))}</option>`).join("")}</select><button class="save-price-button" type="button" data-save-status="${escapeHtml(order.id)}">Update</button></div></div>
      <div class="order-body"><div class="order-customer"><h3>${escapeHtml(order.customer_name)}</h3><p>${escapeHtml(order.customer_phone)}${order.customer_email ? ` · ${escapeHtml(order.customer_email)}` : ""}</p><p>Delivery location: ${escapeHtml(order.delivery_location_name || order.delivery_location || "Unassigned")}</p><p>${escapeHtml(order.delivery_address)}</p></div>
      <ul class="order-items">${items.map(item => `<li><span>${escapeHtml(item.product_name)} <small>× ${Number(item.quantity)}</small></span><strong>${currency.format(Number(item.line_total ?? Number(item.unit_price) * Number(item.quantity)))}</strong></li>`).join("")}</ul></div>
      <div class="order-total"><span>${items.length} ${items.length === 1 ? "line item" : "line items"} · completed orders remain in records</span><strong>${currency.format(Number(order.total))}</strong></div><p class="order-update-message form-message" data-status-message="${escapeHtml(order.id)}" role="status"></p>
    </article>`;
    }).join("")}
  </section>`).join("");
  container.querySelectorAll("[data-save-status]").forEach(button => button.addEventListener("click", () => saveOrderStatus(button.dataset.saveStatus, button)));
}

async function saveOrderStatus(orderId, button) {
  const select = document.querySelector(`[data-order-status="${CSS.escape(orderId)}"]`);
  const message = document.querySelector(`[data-status-message="${CSS.escape(orderId)}"]`);
  button.disabled = true;
  message.textContent = "Updating status...";
  message.classList.remove("is-error");
  try {
    await apiRequest(`/api/admin/orders/${encodeURIComponent(orderId)}/status`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: select.value }),
    });
    await loadDashboard();
  } catch (error) {
    message.textContent = error.message;
    message.classList.add("is-error");
  } finally { button.disabled = false; }
}

function renderItemRequests(requests) {
  const container = document.querySelector("#item-requests-list");
  if (!requests.length) {
    container.innerHTML = '<p class="admin-empty">No customer item requests yet.</p>';
    return;
  }
  container.innerHTML = requests.map(request => {
    const createdAt = request.created_at ? new Date(request.created_at).toLocaleString() : "Time unavailable";
    return `<article class="order-card">
      <div class="order-topline"><div><span class="order-reference">ITEM REQUEST</span><span class="order-date">${escapeHtml(createdAt)}</span></div><span class="order-status">${escapeHtml(request.status || "new")}</span></div>
      <div class="request-body"><div class="order-customer"><h3>${escapeHtml(request.requested_name)}</h3><p>Category: ${escapeHtml(request.category_name || request.category_id || "Unspecified")}</p><p>Requested for: ${escapeHtml(request.delivery_location_name || "Unknown location")}</p><p>Requested by ${escapeHtml(request.customer_name)} · ${escapeHtml(request.customer_phone)}</p><p>Delivery address: ${escapeHtml(request.delivery_address || "Not provided")}</p>${request.note ? `<p>${escapeHtml(request.note)}</p>` : ""}</div></div>
    </article>`;
  }).join("");
}

function renderProducts(products) {
  document.querySelector("#products-list").innerHTML = products.map(product => `<tr>
    <td data-label="Product"><strong>${escapeHtml(product.name)}</strong><small>${escapeHtml(product.unit || "each")}</small></td>
    <td data-label="Category">${escapeHtml(product.category_name)}</td>
    <td data-label="Price"><label class="sr-only" for="price-${escapeHtml(product.id)}">${escapeHtml(product.name)} price</label><input id="price-${escapeHtml(product.id)}" class="price-input" type="number" min="0.01" max="99999999.99" step="0.01" required value="${Number(product.price).toFixed(2)}"></td>
    <td data-label="Save"><button class="save-price-button" type="button" data-save-price="${escapeHtml(product.id)}">Save</button></td>
    <td data-label="Customer ordering"><span class="product-availability ${product.is_available ? "is-available" : "is-hidden"}">${product.is_available ? "Available" : "Hidden"}</span><button class="save-price-button" type="button" data-toggle-availability="${escapeHtml(product.id)}" data-next-availability="${!product.is_available}">${product.is_available ? "Disable" : "Enable"}</button></td>
    <td data-label="Delete"><button class="delete-product-button" type="button" data-delete-product="${escapeHtml(product.id)}" data-product-name="${escapeHtml(product.name)}">Delete</button></td>
  </tr>`).join("");
  document.querySelectorAll("[data-save-price]").forEach(button => button.addEventListener("click", () => savePrice(button.dataset.savePrice, button)));
  document.querySelectorAll("[data-toggle-availability]").forEach(button =>
    button.addEventListener("click", () => saveProductAvailability(button))
  );
  document.querySelectorAll("[data-delete-product]").forEach(button =>
    button.addEventListener("click", () => deleteProduct(button))
  );
}

async function deleteProduct(button) {
  const productName = button.dataset.productName;
  if (!window.confirm(`Permanently delete "${productName}" from the catalog? Past order records will be retained.`)) return;

  button.disabled = true;
  try {
    await apiRequest(`/api/admin/products/${encodeURIComponent(button.dataset.deleteProduct)}`, {
      method: "DELETE",
    });
    showMessage("#price-message", `Deleted "${productName}". Past order records are preserved.`);
    await loadDashboard();
  } catch (error) {
    showMessage("#price-message", error.message, true);
  } finally {
    button.disabled = false;
  }
}

async function saveProductAvailability(button) {
  button.disabled = true;
  try {
    await apiRequest(`/api/admin/products/${encodeURIComponent(button.dataset.toggleAvailability)}/availability`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_available: button.dataset.nextAvailability === "true" }),
    });
    showMessage("#price-message", "Customer ordering availability updated.");
    await loadDashboard();
  } catch (error) {
    showMessage("#price-message", error.message, true);
  } finally {
    button.disabled = false;
  }
}

function renderInventory(products) {
  const locations = adminState.locations.filter(location =>
    adminState.role === "owner" || adminState.locationIds.includes(location.id)
  );
  document.querySelector("#inventory-head").innerHTML = `<tr><th>Product</th><th>Category</th>${locations.map(location => `<th>${escapeHtml(location.name)}</th>`).join("")}</tr>`;
  document.querySelector("#inventory-list").innerHTML = products.map(product => `<tr>
    <td data-label="Product"><strong>${escapeHtml(product.name)}</strong><small>${escapeHtml(product.unit || "each")}</small></td>
    <td data-label="Category">${escapeHtml(product.category_name)}</td>
    ${locations.map(location => {
      const quantity = Number(product.location_inventory?.[location.id] || 0);
      const inputId = `stock-${product.id}-${location.id}`;
      return `<td data-label="${escapeHtml(location.name)}"><div class="inventory-cell"><label class="sr-only" for="${escapeHtml(inputId)}">${escapeHtml(product.name)} stock at ${escapeHtml(location.name)}</label><input id="${escapeHtml(inputId)}" class="stock-input" type="number" min="0" max="1000000" step="1" required value="${quantity}"><button class="save-price-button" type="button" data-save-stock="${escapeHtml(product.id)}" data-stock-location="${escapeHtml(location.id)}">Save</button></div></td>`;
    }).join("")}
  </tr>`).join("");
  document.querySelectorAll("[data-save-stock]").forEach(button =>
    button.addEventListener("click", () => saveStock(button.dataset.saveStock, button.dataset.stockLocation, button))
  );
}

function renderLocationOptions(locations) {
  document.querySelector("#admin-location-options").innerHTML = locations.map(location =>
    `<label class="location-option"><input type="checkbox" name="location_ids" value="${escapeHtml(location.id)}"><span>${escapeHtml(location.name)}</span></label>`
  ).join("");
}

function renderProductForm(categories, locations) {
  document.querySelector("#product-category").innerHTML = categories.map(category =>
    `<option value="${escapeHtml(category.id)}">${escapeHtml(category.name)}</option>`
  ).join("");
  document.querySelector("#product-location-options").innerHTML = locations.map(location =>
    `<label class="product-location-option"><span><input type="checkbox" data-product-location="${escapeHtml(location.id)}"> ${escapeHtml(location.name)}</span><input type="number" data-product-stock="${escapeHtml(location.id)}" min="1" max="1000000" step="1" value="1" disabled aria-label="Starting stock at ${escapeHtml(location.name)}"></label>`
  ).join("");
  document.querySelectorAll("[data-product-location]").forEach(checkbox =>
    checkbox.addEventListener("change", () => {
      const stockInput = document.querySelector(`[data-product-stock="${CSS.escape(checkbox.dataset.productLocation)}"]`);
      stockInput.disabled = !checkbox.checked;
      stockInput.required = checkbox.checked;
    })
  );
}

function renderLocationAdmins(users) {
  const container = document.querySelector("#location-admins-list");
  if (!users.length) {
    container.innerHTML = '<p class="admin-empty">No location-team accounts yet.</p>';
    return;
  }
  container.innerHTML = users.map(user => `<article class="location-admin-card">
    <div class="location-admin-heading"><div><strong>${escapeHtml(user.display_name)}</strong><span>@${escapeHtml(user.username)}</span></div><span class="order-status">${user.is_active ? "active" : "disabled"}</span></div>
    <fieldset class="admin-user-locations"><legend>Assigned locations</legend><div class="admin-location-options">${adminState.locations.map(location =>
      `<label class="location-option"><input type="checkbox" name="user-locations-${escapeHtml(user.id)}" value="${escapeHtml(location.id)}" ${user.location_ids.includes(location.id) ? "checked" : ""}><span>${escapeHtml(location.name)}</span></label>`
    ).join("")}</div></fieldset>
    <div class="location-admin-actions"><button class="save-price-button" type="button" data-save-locations="${escapeHtml(user.id)}">Save locations</button><button class="save-price-button" type="button" data-admin-active="${escapeHtml(user.id)}" data-next-active="${!user.is_active}">${user.is_active ? "Disable account" : "Enable account"}</button></div>
  </article>`).join("");
  container.querySelectorAll("[data-save-locations]").forEach(button => button.addEventListener("click", () => saveAdminLocations(button)));
  container.querySelectorAll("[data-admin-active]").forEach(button => button.addEventListener("click", () => setLocationAdminActive(button)));
}

async function saveAdminLocations(button) {
  const userId = button.dataset.saveLocations;
  const locationIds = [...document.querySelectorAll(`input[name="user-locations-${CSS.escape(userId)}"]:checked`)].map(input => input.value);
  button.disabled = true;
  showMessage("#location-admin-message", "Saving location assignments...");
  try {
    await apiRequest(`/api/admin/location-admins/${encodeURIComponent(userId)}/locations`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ location_ids: locationIds }),
    });
    showMessage("#location-admin-message", "Location assignments updated.");
    await loadDashboard();
  } catch (error) {
    showMessage("#location-admin-message", error.message, true);
  } finally { button.disabled = false; }
}

async function setLocationAdminActive(button) {
  button.disabled = true;
  try {
    await apiRequest(`/api/admin/location-admins/${encodeURIComponent(button.dataset.adminActive)}/active`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_active: button.dataset.nextActive === "true" }),
    });
    await loadDashboard();
  } catch (error) {
    showMessage("#location-admin-message", error.message, true);
  } finally { button.disabled = false; }
}

async function loadDashboard() {
  showMessage("#price-message", "");
  showMessage("#inventory-message", "");
  const owner = adminState.role === "owner";
  const orderParameters = new URLSearchParams({
    period: document.querySelector("#orders-period").value,
    status: document.querySelector("#orders-status").value,
  });
  const tasks = [
    apiRequest(`/api/admin/orders?${orderParameters}`),
    apiRequest("/api/admin/products"),
    apiRequest("/api/delivery-locations"),
  ];
  if (owner) tasks.push(apiRequest("/api/admin/item-requests"), apiRequest("/api/admin/location-admins"));
  const results = await Promise.allSettled(tasks);
  const [ordersResult, productsResult, locationsResult, requestsResult, usersResult] = results;

  if (locationsResult.status === "fulfilled") {
    adminState.locations = locationsResult.value.locations;
    if (owner) renderLocationOptions(adminState.locations);
  }

  if (ordersResult.status === "fulfilled") {
    adminState.orders = ordersResult.value.orders;
    adminState.hasMoreOrders = ordersResult.value.has_more;
    showMessage("#orders-pagination-message", "");
    renderOrders(ordersResult.value.orders);
    document.querySelector("#admin-mode").textContent = ordersResult.value.mode === "demo" ? "DEMO DATA · RESET ON RESTART" : "CONNECTED TO SUPABASE";
  } else {
    adminState.orders = [];
    adminState.hasMoreOrders = false;
    document.querySelector("#orders-list").innerHTML = `<p class="admin-empty is-error">${escapeHtml(ordersResult.reason.message)}</p>`;
    document.querySelector("#load-more-orders").hidden = true;
  }

  if (productsResult.status === "fulfilled" && locationsResult.status === "fulfilled") {
    renderInventory(productsResult.value.products);
    if (owner) renderProductForm(productsResult.value.categories, adminState.locations);
  } else {
    const failure = productsResult.status === "rejected" ? productsResult.reason : locationsResult.reason;
    showMessage("#inventory-message", failure.message, true);
  }

  if (owner) {
    if (requestsResult.status === "fulfilled") {
      renderItemRequests(requestsResult.value.requests);
    } else {
      document.querySelector("#item-requests-list").innerHTML = `<p class="admin-empty is-error">${escapeHtml(requestsResult.reason.message)}</p>`;
    }
    if (productsResult.status === "fulfilled") {
      renderProducts(productsResult.value.products);
    } else {
      showMessage("#price-message", productsResult.reason.message, true);
    }
    if (usersResult.status === "fulfilled") renderLocationAdmins(usersResult.value.users);
    else showMessage("#location-admin-message", usersResult.reason.message, true);
    if (locationsResult.status === "rejected") {
      showMessage("#location-admin-message", locationsResult.reason.message, true);
    }
  }

  if (results.some(result => result.status === "rejected" && result.reason.status === 401)) {
    setSignedIn(false);
  }
}

async function savePrice(productId, button) {
  const input = document.querySelector(`#price-${CSS.escape(productId)}`);
  const price = Number(input.value);
  if (!input.reportValidity()) return;
  button.disabled = true;
  showMessage("#price-message", "Saving price...");
  try {
    await apiRequest(`/api/admin/products/${encodeURIComponent(productId)}/price`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ price }),
    });
    showMessage("#price-message", "Price updated. New orders will use this price.");
    await loadDashboard();
  } catch (error) {
    showMessage("#price-message", error.message, true);
  } finally { button.disabled = false; }
}

async function saveStock(productId, locationId, button) {
  const input = document.querySelector(`#stock-${CSS.escape(productId)}-${CSS.escape(locationId)}`);
  if (!input.reportValidity()) return;
  button.disabled = true;
  showMessage("#inventory-message", "Saving location stock...");
  try {
    await apiRequest(`/api/admin/products/${encodeURIComponent(productId)}/stock/${encodeURIComponent(locationId)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ stock_quantity: Number(input.value) }),
    });
    showMessage("#inventory-message", "Location stock updated.");
    await loadDashboard();
  } catch (error) {
    showMessage("#inventory-message", error.message, true);
  } finally { button.disabled = false; }
}

async function submitLogin(form, role) {
  const submitButton = form.querySelector("button[type=submit]");
  submitButton.disabled = true;
  const message = form.querySelector(".login-message");
  message.textContent = "Signing in...";
  message.classList.remove("is-error");
  try {
    const formData = new FormData(form);
    const password = formData.get("password");
    const username = String(formData.get("username") || "").trim();
    const credentials = role === "location" ? { username, password } : { password };
    await apiRequest("/api/admin/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(credentials),
    });
    form.reset();
    setSignedIn(true, await apiRequest("/api/admin/session"));
    await loadDashboard();
  } catch (error) {
    message.textContent = error.message;
    message.classList.add("is-error");
  } finally { submitButton.disabled = false; }
}

document.querySelector("#owner-login-tab").addEventListener("click", () => setLoginTab("owner"));
document.querySelector("#location-login-tab").addEventListener("click", () => setLoginTab("location"));
document.querySelector("#owner-login-form").addEventListener("submit", event => {
  event.preventDefault();
  submitLogin(event.currentTarget, "owner");
});
document.querySelector("#location-login-form").addEventListener("submit", event => {
  event.preventDefault();
  submitLogin(event.currentTarget, "location");
});

document.querySelector("#logout-button").addEventListener("click", async () => {
  try { await apiRequest("/api/admin/logout", { method: "POST" }); }
  finally { setSignedIn(false); }
});

document.querySelector("#refresh-orders").addEventListener("click", loadDashboard);
document.querySelector("#orders-period").addEventListener("change", loadDashboard);
document.querySelector("#orders-status").addEventListener("change", loadDashboard);
document.querySelector("#load-more-orders").addEventListener("click", async event => {
  const button = event.currentTarget;
  const parameters = new URLSearchParams({
    period: document.querySelector("#orders-period").value,
    status: document.querySelector("#orders-status").value,
    offset: String(adminState.orders.length),
  });
  button.disabled = true;
  showMessage("#orders-pagination-message", "Loading more orders...");
  try {
    const result = await apiRequest(`/api/admin/orders?${parameters}`);
    adminState.orders.push(...result.orders);
    adminState.hasMoreOrders = result.has_more;
    showMessage("#orders-pagination-message", "");
    renderOrders(adminState.orders);
  } catch (error) {
    showMessage("#orders-pagination-message", error.message, true);
  } finally {
    button.disabled = false;
  }
});

document.querySelector("#location-admin-form").addEventListener("submit", async event => {
  event.preventDefault();
  const form = event.currentTarget;
  const submitButton = form.querySelector("button[type=submit]");
  const formData = new FormData(form);
  const payload = {
    display_name: formData.get("display_name"),
    username: formData.get("username"),
    password: formData.get("password"),
    location_ids: formData.getAll("location_ids"),
  };
  submitButton.disabled = true;
  showMessage("#location-admin-message", "Creating location-team account...");
  try {
    await apiRequest("/api/admin/location-admins", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    form.reset();
    showMessage("#location-admin-message", "Location-team account created.");
    await loadDashboard();
  } catch (error) {
    showMessage("#location-admin-message", error.message, true);
  } finally { submitButton.disabled = false; }
});

document.querySelector("#product-create-form").addEventListener("submit", async event => {
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector("button[type=submit]");
  const formData = new FormData(form);
  const locationStock = Object.fromEntries([...document.querySelectorAll("[data-product-location]:checked")].map(checkbox => [
    checkbox.dataset.productLocation,
    Number(document.querySelector(`[data-product-stock="${CSS.escape(checkbox.dataset.productLocation)}"]`).value),
  ]));
  if (!Object.keys(locationStock).length) {
    showMessage("#product-create-message", "Select at least one location and enter its starting stock.", true);
    return;
  }
  const payload = {
    name: formData.get("name"),
    category_id: formData.get("category_id"),
    description: formData.get("description"),
    price: Number(formData.get("price")),
    unit: formData.get("unit"),
    image_url: formData.get("image_url"),
    location_stock: locationStock,
  };
  button.disabled = true;
  showMessage("#product-create-message", "Adding product...");
  try {
    await apiRequest("/api/admin/products", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    form.reset();
    document.querySelectorAll("[data-product-stock]").forEach(input => {
      input.disabled = true;
      input.required = false;
      input.value = "1";
    });
    showMessage("#product-create-message", "Product added with starting stock at the selected locations.");
    await loadDashboard();
  } catch (error) {
    showMessage("#product-create-message", error.message, true);
  } finally { button.disabled = false; }
});

apiRequest("/api/admin/session").then(session => {
  if (!session.configured) {
    const ownerMessage = document.querySelector("#owner-login-form .login-message");
    ownerMessage.textContent = "Admin access is not configured yet. Set ADMIN_PASSWORD in your .env file.";
    ownerMessage.classList.add("is-error");
  }
  setSignedIn(session.authenticated, session);
  if (session.authenticated) loadDashboard();
}).catch(error => {
  const ownerMessage = document.querySelector("#owner-login-form .login-message");
  ownerMessage.textContent = error.message;
  ownerMessage.classList.add("is-error");
});
