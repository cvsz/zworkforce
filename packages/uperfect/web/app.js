(() => {
  "use strict";

  const state = {
    lang: localStorage.getItem("uperfect-language") || "th",
    view: window.location.hash.slice(1) || "overview",
    dashboard: null,
    products: [],
    conversations: [],
    orders: [],
    integrations: [],
    skills: [],
    agents: [],
    workflows: [],
    salesAssets: null,
    integrationGuides: [],
    settings: null,
    selectedConversation: null,
    loading: false
  };

  const translations = {
    th: {
      "nav.overview": "ภาพรวม", "nav.inbox": "แชตรวม", "nav.memory": "Product Memory", "nav.orders": "ออเดอร์",
      "nav.skills": "Skills", "nav.agents": "Agents", "nav.automations": "n8n Automations", "nav.integrations": "Channels", "nav.settings": "ตั้งค่า",
      "nav.sales-assets": "สื่อปิดการขาย",
      "system.local": "Local workspace", "top.workspace": "OPERATIONS WORKSPACE", "title.overview": "ภาพรวมระบบ",
      "title.inbox": "แชตรวม", "title.memory": "Product Memory", "title.orders": "ออเดอร์และตรวจสอบ",
      "title.skills": "Skills", "title.agents": "Agents", "title.automations": "n8n Automations", "title.integrations": "Channels", "title.sales-assets": "สื่อปิดการขาย", "title.settings": "ตั้งค่าระบบ",
      "status.configured": "ตั้งค่าแล้ว", "status.unconfigured": "ยังไม่ตั้งค่า", "status.degraded": "ต้องตรวจสอบ", "status.verified": "ยืนยันแล้ว", "status.disabled": "ปิดใช้งาน", "status.outbox": "รอส่งออก", "status.draft": "ร่าง", "status.awaiting_payment": "รอชำระเงิน", "status.pending_review": "รอตรวจสอบ", "status.confirmed": "ยืนยันแล้ว", "status.fulfilled": "จัดส่งแล้ว", "status.cancelled": "ยกเลิก", "status.unknown": "ไม่ทราบสถานะ",
      "common.apiOnline": "API online", "common.apiOffline": "API offline", "common.unpriced": "ยังไม่ระบุราคา", "common.active": "พร้อมใช้งาน", "common.paused": "หยุดชั่วคราว", "common.serverSide": "ฝั่ง server", "common.records": "รายการ", "common.empty": "ยังไม่มีข้อมูล", "common.close": "ปิดการขาย", "common.referenceOnly": "ข้อมูลอ้างอิง", "common.catalogReview": "รอตรวจ catalog"
    },
    en: {
      "nav.overview": "Overview", "nav.inbox": "Unified Inbox", "nav.memory": "Product Memory", "nav.orders": "Orders",
      "nav.skills": "Skills", "nav.agents": "Agents", "nav.automations": "n8n Automations", "nav.integrations": "Channels", "nav.settings": "Settings",
      "nav.sales-assets": "Sales Assets",
      "system.local": "Local workspace", "top.workspace": "OPERATIONS WORKSPACE", "title.overview": "System overview",
      "title.inbox": "Unified inbox", "title.memory": "Product Memory", "title.orders": "Orders & review",
      "title.skills": "Skills", "title.agents": "Agents", "title.automations": "n8n Automations", "title.integrations": "Channels", "title.sales-assets": "Sales Assets", "title.settings": "System settings",
      "status.configured": "Configured", "status.unconfigured": "Unconfigured", "status.degraded": "Needs review", "status.verified": "Verified", "status.disabled": "Disabled", "status.outbox": "Outbox", "status.draft": "Draft", "status.awaiting_payment": "Awaiting payment", "status.pending_review": "Pending review", "status.confirmed": "Confirmed", "status.fulfilled": "Fulfilled", "status.cancelled": "Cancelled", "status.unknown": "Unknown status",
      "common.apiOnline": "API online", "common.apiOffline": "API offline", "common.unpriced": "Price not supplied", "common.active": "Active", "common.paused": "Paused", "common.serverSide": "server-side", "common.records": "records", "common.empty": "No data yet", "common.close": "Close sale", "common.referenceOnly": "Reference only", "common.catalogReview": "Catalog review"
    }
  };

  const $ = (selector) => document.querySelector(selector);
  const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#039;"}[char]));
  const tx = (thai, english) => state.lang === "th" ? thai : english;
  const money = (value) => value === null || value === undefined ? t("common.unpriced") : `฿${Number(value).toLocaleString(state.lang === "th" ? "th-TH" : "en-US")}`;
  const t = (key) => translations[state.lang][key] || translations.th[key] || key;
  const localized = (item, field, fallback = "") => item?.[state.lang] || item?.[field] || fallback;
  const assetUrl = (path) => `/${String(path || "").split("/").map(encodeURIComponent).join("/")}`;
  const statusText = (status) => t(`status.${status}`) || t("status.unknown");

  async function api(path, options = {}) {
    const response = await fetch(path, { headers: { "Content-Type": "application/json", ...(options.headers || {}) }, ...options });
    const contentType = response.headers.get("content-type") || "";
    const data = contentType.includes("json") ? await response.json() : await response.text();
    if (!response.ok) {
      const error = data && data.error ? data.error : { code: "NETWORK_ERROR", message: tx("ไม่สามารถเชื่อมต่อ API ได้", "Unable to connect to the API") };
      const failure = new Error(error.message);
      failure.code = error.code;
      throw failure;
    }
    return data;
  }

  function showNotice(message, kind = "error") {
    const notice = $("#notice");
    notice.hidden = !message;
    notice.dataset.kind = kind;
    notice.textContent = message || "";
  }

  function statusBadge(status) {
    const className = String(status || "").replace(/[^a-z_]/g, "_");
    return `<span class="status-badge ${className}">${esc(statusText(status || "unknown"))}</span>`;
  }

  function setApiStatus(ok) {
    const element = $("#api-status");
    element.innerHTML = `<span class="status-dot ${ok ? "" : "is-danger"}"></span>${ok ? t("common.apiOnline") : t("common.apiOffline")}`;
  }

  async function loadDashboard() {
    state.loading = true;
    try {
      const results = await Promise.all([
        api("/api/dashboard"), api("/api/products"), api("/api/conversations"), api("/api/orders"),
        api("/api/integrations"), api("/api/skills"), api("/api/agents"), api("/api/automation/workflows"), api("/api/settings"), api("/api/sales-assets"), api("/api/integration-guides")
      ]);
      [state.dashboard, { items: state.products }, { items: state.conversations }, { items: state.orders },
        { items: state.integrations }, { items: state.skills }, { items: state.agents }, { items: state.workflows }, state.settings,
        state.salesAssets, { items: state.integrationGuides }] = results;
      if (!localStorage.getItem("uperfect-language") && state.settings?.default_language) {
        state.lang = state.settings.default_language;
      }
      if (!state.selectedConversation || !state.conversations.some((item) => item.id === state.selectedConversation)) {
        state.selectedConversation = state.conversations[0]?.id || null;
      }
      setApiStatus(true);
      showNotice("");
      render();
    } catch (error) {
      setApiStatus(false);
      showNotice(`${error.code || "NETWORK_ERROR"}: ${error.message}`);
      $("#view").innerHTML = `<div class="empty-state"><strong>${tx("เชื่อมต่อ workspace ไม่สำเร็จ", "Unable to connect to the workspace")}</strong><span>${tx("ตรวจสอบ API แล้วกดรีเฟรชอีกครั้ง", "Check the API and refresh again")}</span></div>`;
    } finally {
      state.loading = false;
    }
  }

  function render() {
    document.documentElement.lang = state.lang === "th" ? "th" : "en";
    document.querySelectorAll("[data-i18n]").forEach((node) => { node.textContent = t(node.dataset.i18n); });
    document.querySelectorAll(".language-toggle span").forEach((node) => node.classList.toggle("lang-active", node.textContent.toLowerCase() === state.lang));
    $("#mobile-menu").setAttribute("aria-label", tx("เปิดเมนู", "Open menu"));
    $("#language-toggle").setAttribute("aria-label", tx("เปลี่ยนภาษา", "Switch language"));
    $("#refresh-button").setAttribute("title", tx("รีเฟรชข้อมูล", "Refresh data"));
    $("#refresh-button").setAttribute("aria-label", tx("รีเฟรชข้อมูล", "Refresh data"));
    document.querySelectorAll(".nav-item").forEach((node) => node.classList.toggle("is-active", node.dataset.view === state.view));
    $("#view-title").textContent = t(`title.${state.view}`);
    $("#inbox-count").textContent = state.conversations.length;
    const views = { overview: renderOverview, inbox: renderInbox, memory: renderMemory, orders: renderOrders, skills: renderSkills, agents: renderAgents, automations: renderAutomations, integrations: renderIntegrations, "sales-assets": renderSalesAssets, settings: renderSettings };
    (views[state.view] || renderOverview)();
    if (state.view === "integrations") decorateIntegrationGuideActions();
    if (state.view === "settings") decorateSettingsProviderActions();
    const view = $("#view");
    view.focus({ preventScroll: true });
  }

  function renderOverview() {
    const dashboard = state.dashboard || {};
    const channelItems = (dashboard.integrations || []).filter((item) => ["facebook", "tiktok", "shopee", "line", "local_ai"].includes(item.provider));
    $("#view").innerHTML = `
      <div class="view-head"><div><h3>${tx("ศูนย์ควบคุม U.Perfect", "U.Perfect control room")}</h3><p>${tx("ติดตามแชท สินค้า ออเดอร์ และสถานะการเชื่อมต่อจากจุดเดียว", "Monitor conversations, catalogue, orders, and integration truth in one place.")}</p></div><div class="view-actions"><button class="button" data-view-action="inbox">${tx("เปิดแชตรวม", "Open inbox")}</button></div></div>
      <div class="metric-grid">
        ${metric(tx("สินค้าที่จำได้", "Products remembered"), dashboard.products || 0, tx("merchant catalogue", "merchant catalogue"))}
        ${metric(tx("บทสนทนา", "Conversations"), dashboard.conversations || 0, tx("ทุกช่องทาง", "all channels"))}
        ${metric(tx("ออเดอร์", "Orders"), dashboard.orders || 0, tx("workspace ภายใน", "local workspace"))}
        ${metric(tx("รอตรวจสอบ", "Pending review"), dashboard.pending_review || 0, tx("ตรวจหลักฐานการชำระเงิน", "payment review"))}
      </div>
      <div class="dashboard-grid">
        <article class="panel"><div class="panel-title"><h4>${tx("สัญญาณกิจกรรม", "Activity pulse")}</h4><span class="muted small">${tx("รายการภายใน", "local records")}</span></div><div class="sparkline" aria-label="${tx("กราฟกิจกรรม", "activity bars")}"><i class="bar" style="height:28%"></i><i class="bar" style="height:45%"></i><i class="bar" style="height:36%"></i><i class="bar" style="height:63%"></i><i class="bar" style="height:52%"></i><i class="bar" style="height:76%"></i><i class="bar" style="height:68%"></i></div><div class="sparkline-labels"><span>Mon</span><span>Tue</span><span>Wed</span><span>Thu</span><span>Fri</span><span>Sat</span><span>${tx("ปัจจุบัน", "Now")}</span></div></article>
        <article class="panel"><div class="panel-title"><h4>${tx("ช่องทางและสถานะจริง", "Channels and connection truth")}</h4><button class="button-secondary" data-view-action="integrations">${tx("จัดการ", "Manage")}</button></div><div class="status-list">${channelItems.map(integrationRow).join("") || empty(tx("ยังไม่มีข้อมูลช่องทาง", "No channel data yet"))}</div></article>
      </div>
      <div class="two-column" style="margin-top:.85rem"><article class="panel"><div class="panel-title"><h4>${tx("สินค้าในคลัง memory", "Products in memory")}</h4><button class="button-secondary" data-view-action="memory">${tx("เปิด catalog", "Open catalog")}</button></div>${state.products.slice(0, 3).map(productRow).join("") || empty(tx("ยังไม่มีสินค้า", "No products yet"))}</article><article class="panel"><div class="panel-title"><h4>${tx("งานที่ต้องตรวจ", "Work requiring review")}</h4><button class="button-secondary" data-view-action="orders">${tx("ดูออเดอร์", "View orders")}</button></div>${state.orders.filter((item) => item.status === "pending_review").slice(0, 4).map(orderRow).join("") || empty(tx("ไม่มี payment review ค้างอยู่", "No payment review is waiting"))}</article></div>`;
  }

  function metric(label, value, note) {
    return `<article class="metric"><div class="metric-label">${esc(label)}</div><div class="metric-value">${esc(value)}</div><div class="metric-note">${esc(note)}</div></article>`;
  }

  function integrationRow(item) {
    const guide = state.integrationGuides.find((entry) => entry.provider === item.provider);
    const label = state.lang === "th" ? item.label_th : item.label_en;
    const note = state.lang === "th" ? item.setup_note_th : item.setup_note_en;
    return `<div class="status-row"><div class="status-row-main"><span class="status-dot ${item.status === "unconfigured" ? "is-warn" : ""}"></span><div><strong>${esc(label || item.label || item.provider)}</strong><small>${esc(item.webhook_path || t("common.serverSide"))}</small>${guide ? `<small>${esc(localized(guide, "th", ""))}</small>` : note ? `<small>${esc(note)}</small>` : ""}</div></div>${statusBadge(item.status)}</div>`;
  }

  function productRow(product) {
    return `<div class="data-row"><div class="data-row-main"><div><strong>${esc(product.name)}</strong><small>${esc(product.size)} · ${money(product.price_thb)}</small></div></div><span class="status-badge ${product.available ? "ready" : "degraded"}">${product.available ? t("common.active") : t("common.paused")}</span></div>`;
  }

  function orderRow(order) {
    return `<div class="data-row"><div class="data-row-main"><div><strong>${esc(order.customer_name)}</strong><small>${esc(order.product_id)} · ${money(order.total_thb)}</small></div></div>${statusBadge(order.status)}</div>`;
  }

  function empty(message) { return `<div class="empty-state"><strong>${esc(message)}</strong></div>`; }

  function renderInbox() {
    const selected = state.conversations.find((item) => item.id === state.selectedConversation);
    $("#view").innerHTML = `<div class="view-head"><div><h3>${tx("แชตรวม", "Unified inbox")}</h3><p>${tx("รวมข้อความจาก Facebook, TikTok Shop และ Shopee เมื่อ webhook ผ่านการตรวจสอบ", "Messages from Facebook, TikTok Shop, and Shopee after webhook verification")}</p></div><div class="view-actions"><button class="button-secondary" data-view-action="memory">${tx("ดู memory", "View memory")}</button></div></div><div class="inbox-layout"><article class="panel"><div class="panel-title"><h4>${tx("บทสนทนา", "Conversations")}</h4><span class="muted small">${state.conversations.length} ${t("common.records")}</span></div><div class="conversation-list">${state.conversations.map((item) => `<button class="conversation-item ${item.id === state.selectedConversation ? "is-selected" : ""}" data-conversation="${esc(item.id)}"><div class="conversation-item-top"><strong>${esc(item.customer_id)}</strong><small>${esc(item.platform)}</small></div><p class="conversation-preview">${esc(item.messages?.at(-1)?.text || tx("ยังไม่มีข้อความ", "No messages yet"))}</p>${item.human_takeover ? `<span class="status-badge degraded">${tx("แอดมินรับช่วง", "Human takeover")}</span>` : ""}</button>`).join("") || empty(tx("ยังไม่มี conversation", "No conversations yet"))}</div><form id="message-form" class="form-grid" style="margin-top:.75rem"><div class="field"><label for="message-platform">${tx("ช่องทาง", "Channel")}</label><select id="message-platform"><option value="facebook">Facebook</option><option value="tiktok">TikTok Shop</option><option value="shopee">Shopee</option></select></div><div class="field"><label for="message-customer">Customer ID</label><input id="message-customer" required placeholder="local-customer"></div><div class="field"><label for="message-text">${tx("ข้อความทดสอบใน local memory", "Local memory test message")}</label><input id="message-text" required placeholder="${tx("เช่น สนใจวิตซีโลเอ้", "e.g. interested in Loe Vit C Serum")}"></div><div class="form-actions"><button class="button" type="submit">${tx("ส่งเข้า Autobot", "Send to Autobot")}</button></div></form></article>${selected ? renderConversation(selected) : `<article class="panel">${empty(tx("เลือก conversation หรือเริ่มข้อความใหม่", "Select a conversation or start a new message"))}</article>`}</div>`;
  }

  function renderConversation(conversation) {
    return `<article class="panel conversation-body"><div class="conversation-header"><div><h4>${esc(conversation.customer_id)}</h4><span class="muted small">${esc(conversation.platform)} · ${esc(conversation.active_product_id || tx("ยังไม่มีสินค้าที่กำลังคุย", "no active product"))}</span></div><label class="takeover-control"><input type="checkbox" data-takeover="${esc(conversation.id)}" ${conversation.human_takeover ? "checked" : ""}> ${tx("แอดมินรับช่วง", "Human takeover")}</label></div><div class="message-stream">${(conversation.messages || []).map((message) => `<div class="message ${message.direction === "outbound" ? "outbound" : "inbound"}">${esc(message.text)}<span class="message-meta">${esc(message.intent)} · ${message.automated ? "autobot" : message.direction}</span></div>`).join("") || empty(tx("ยังไม่มีข้อความ", "No messages yet"))}</div><div class="callout ${conversation.human_takeover ? "" : "teal"}">${conversation.human_takeover ? tx("Autobot หยุดตอบสำหรับบทสนทนานี้ แอดมินเป็นผู้รับช่วง", "Autobot is paused for this conversation while a human admin takes over.") : tx("Autobot ทำงานตาม product memory และกฎ payment review", "Autobot follows product memory and the payment-review gate.")}</div></article>`;
  }

  function renderMemory() {
    $("#view").innerHTML = `<div class="view-head"><div><h3>Product Memory</h3><p>${tx("ข้อมูลสินค้าจาก merchant brief และ TikTok listing ที่ผู้ใช้ให้มา คำอธิบายทุกชิ้นแก้ไขได้จาก API", "Product facts from the merchant brief and supplied TikTok listings. Records can be edited through the API.")}</p></div><div class="view-actions"><button class="button" data-view-action="orders">${tx("สร้างออเดอร์", "Create order")}</button></div></div><div class="callout">${tx("ข้อมูลสื่อสินค้าจาก TikTok บางรายการยังถูกบล็อกด้วย Security Check CAPTCHA จึงแสดงเฉพาะสื่อ local ที่ได้รับมาและ source link โดยไม่อ้างว่าดึงจาก TikTok สำเร็จ", "Some TikTok media retrieval was blocked by Security Check CAPTCHA. The app shows only supplied local media and source links; it does not claim a successful TikTok export.")}</div><div class="product-grid" style="margin-top:.85rem">${state.products.map(productCard).join("") || empty(tx("ยังไม่มีสินค้า", "No products yet"))}</div>`;
  }

  function productCard(product) {
    const ingredients = (product.ingredients || []).map((item) => `<li><b>${esc(item.name)}</b>${esc(item.benefit_copy)}</li>`).join("");
    const aliases = (product.aliases || []).slice(0, 8).map((alias) => `<span class="tag">${esc(alias)}</span>`).join("");
    const sources = (product.source_urls || []).map((url) => `<a class="source-link" href="${esc(url)}" target="_blank" rel="noreferrer">${tx("TikTok listing ↗", "TikTok listing ↗")}</a>`).join(" ");
    return `<article class="product-card"><div class="product-marker">${product.id === "MALA_CHILI_OIL" ? "M" : "L"}</div><h4>${esc(product.name)}</h4><p>${esc(product.size)} · ${esc(product.seller || "U.Perfect")}</p><div class="product-price">${money(product.price_thb)}</div><p>${esc(product.description)}</p><div class="tag-list">${aliases}</div>${product.warning ? `<p class="small muted">${esc(product.warning)}</p>` : ""}${product.allergen_warning ? `<div class="callout" style="margin-top:.65rem">${esc(product.allergen_warning)}</div>` : ""}<details class="details-block"><summary>${tx("ส่วนผสมและแหล่งข้อมูล", "Ingredients & source facts")}</summary>${ingredients ? `<ol class="ingredient-list">${ingredients}</ol>` : `<p class="small muted">${tx("ยังไม่มี ingredient matrix สำหรับสินค้านี้", "No ingredient matrix is available for this product")}</p>`}<p class="small muted">${esc(product.price_note || "")}</p><div>${sources}</div></details></article>`;
  }

  function renderOrders() {
    const priced = state.products.filter((product) => product.price_thb !== null);
    $("#view").innerHTML = `<div class="view-head"><div><h3>${tx("ออเดอร์และตรวจสอบ", "Orders & review")}</h3><p>${tx("สร้างร่างออเดอร์ ตรวจหลักฐานการชำระเงิน และเลื่อนสถานะอย่างมี guard", "Create draft orders, review payment evidence, and move status through guarded transitions.")}</p></div><div class="view-actions"><button class="button-secondary" data-view-action="inbox">${tx("กลับแชต", "Back to inbox")}</button></div></div><div class="two-column"><article class="panel"><div class="panel-title"><h4>${tx("สร้าง draft order", "Create draft order")}</h4><span class="status-badge pending_review">${tx("รอตรวจสอบการชำระเงิน", "Payment review")}</span></div><form id="order-form"><div class="form-grid"><div class="field"><label for="order-product">${tx("สินค้า", "Product")}</label><select id="order-product" required>${priced.map((product) => `<option value="${esc(product.id)}">${esc(product.name)} · ${money(product.price_thb)}</option>`).join("")}</select></div><div class="field"><label for="order-quantity">${tx("จำนวน", "Quantity")}</label><input id="order-quantity" type="number" min="1" max="100" value="1" required></div><div class="field"><label for="order-customer">${tx("ชื่อลูกค้า", "Customer name")}</label><input id="order-customer" required placeholder="${tx("ชื่อลูกค้า", "Customer name")}"></div></div><div class="form-actions"><button class="button" type="submit">${tx("สร้าง awaiting payment", "Create awaiting payment")}</button></div></form></article><article class="panel"><div class="panel-title"><h4>LINE notification outbox</h4><button class="button-secondary" data-view-action="integrations">${tx("สถานะ", "Status")}</button></div><p class="muted small">${tx("ออเดอร์ที่ยืนยันแล้วจะถูกเขียนลง outbox ก่อนส่ง LINE เมื่อบัญชีพร้อม", "Confirmed orders enter the outbox before LINE delivery when the account is configured.")}</p><div class="data-row"><div><strong>Pending events</strong><small>${tx("ไม่ส่งออกจาก browser", "Never sent from the browser")}</small></div><span class="status-badge">${esc(state.dashboard?.pending_notifications || 0)}</span></div></article></div><article class="panel" style="margin-top:.85rem"><div class="panel-title"><h4>${tx("รายการออเดอร์", "Orders")}</h4><span class="muted small">${state.orders.length} ${t("common.records")}</span></div>${state.orders.length ? `<div class="table-wrap"><table class="data-table"><thead><tr><th>${tx("ลูกค้า", "Customer")}</th><th>${tx("สินค้า", "Product")}</th><th>${tx("ยอดรวม", "Total")}</th><th>${tx("สถานะ", "Status")}</th><th>${tx("การทำงาน", "Action")}</th></tr></thead><tbody>${state.orders.map((order) => `<tr><td><strong>${esc(order.customer_name)}</strong><span class="muted small">${esc(order.id.slice(0, 8))}</span></td><td>${esc(order.product_id)} × ${esc(order.quantity)}</td><td>${money(order.total_thb)}</td><td>${statusBadge(order.status)}</td><td>${order.status === "awaiting_payment" ? `<button class="button-secondary" data-payment="${esc(order.id)}">${tx("รับหลักฐาน", "Receive evidence")}</button>` : order.status === "pending_review" ? `<button class="button" data-confirm="${esc(order.id)}">${tx("ยืนยัน", "Confirm")}</button>` : ""}</td></tr>`).join("")}</tbody></table></div>` : empty(tx("ยังไม่มีออเดอร์", "No orders yet"))}</article>`;
  }

  function renderSkills() { renderEntities("Skills", tx("ความสามารถแบบ rule-based ที่ผูกกับ service ภายใน", "Rule-based capabilities bound to local services"), state.skills, "skill"); }
  function renderAgents() { renderEntities("Agents", tx("ขอบเขต agent และสถานะ runtime ที่ตรวจสอบได้", "Operational agents and their truthful runtime state"), state.agents, "agent"); }

  function renderEntities(title, subtitle, items, type) {
    $("#view").innerHTML = `<div class="view-head"><div><h3>${esc(title)}</h3><p>${esc(subtitle)}</p></div></div><div class="entity-grid">${items.map((item) => `<article class="panel"><div class="panel-title"><h4>${esc(localized(item, "name", ""))}</h4>${statusBadge(item.status)}</div><p class="muted small">${esc(localized(item, "description", item.scope || ""))}</p><span class="code-line">${esc(item.id)}</span></article>`).join("") || empty(t("common.empty"))}</div><article class="panel" style="margin-top:.85rem"><div class="callout teal">${type === "skill" ? tx("Skills ใช้ deterministic rules และ product facts ใน SQLite; ไม่มี model key ใน browser", "Skills use deterministic rules and SQLite product facts; no model key is exposed in the browser.") : tx("Agents แสดงขอบเขตการทำงานและสถานะจาก server โดยไม่แสดง secret", "Agents show server-side scope and truthful state without exposing secrets.")}</div></article>`;
  }

  function renderAutomations() {
    $("#view").innerHTML = `<div class="view-head"><div><h3>n8n Automations</h3><p>${tx("Auto post, comment reply, schedule และ Auto Update อยู่หลัง webhook/account verification", "Auto post, comment reply, scheduling, and Auto Update remain behind webhook/account verification.")}</p></div><div class="view-actions"><button class="button-secondary" data-view-action="integrations">${tx("ตรวจ Channels", "Review channels")}</button></div></div><div class="entity-grid">${state.workflows.map((item) => `<article class="panel"><div class="panel-title"><h4>${esc(localized(item, "name", ""))}</h4>${statusBadge(item.status)}</div><p class="muted small">${esc(localized(item, state.lang === "th" ? "th_note" : "en_note", item.note || ""))}</p><span class="code-line">workflow: ${esc(item.id)}</span></article>`).join("") || empty(t("common.empty"))}</div>`;
  }

  function decorateIntegrationGuideActions() {
    const grids = document.querySelectorAll("#view .entity-grid");
    const cards = grids[1]?.querySelectorAll("article.panel") || [];
    state.integrationGuides.forEach((guide, index) => {
      const actions = cards[index]?.querySelector(".view-actions");
      if (!actions || actions.querySelector("[data-approval-form]")) return;
      [["approval_th", tx("แบบฟอร์ม TH ↗", "TH approval ↗")], ["approval_en", tx("แบบฟอร์ม EN ↗", "EN approval ↗")]].forEach(([field, label]) => {
        if (!guide[field]) return;
        const link = document.createElement("a");
        link.className = "button-secondary";
        link.dataset.approvalForm = "true";
        link.target = "_blank";
        link.rel = "noreferrer";
        link.href = guide[field];
        link.textContent = label;
        actions.appendChild(link);
      });
    });
    const heading = document.querySelector("#view > h3");
    if (heading) heading.textContent = tx("คู่มือขอ API และแบบฟอร์มอนุมัติ", "API onboarding and approval workbooks");
    cards.forEach((card) => {
      const badge = card.querySelector(".status-badge");
      if (badge) badge.textContent = tx("คู่มือและแบบฟอร์ม", "Guides & form");
    });
  }

  function decorateSettingsProviderActions() {
    const form = $("#settings-form");
    const anchor = form?.querySelector(".settings-actions");
    if (!form || !anchor || form.querySelector("[data-provider-docs]")) return;
    const panel = document.createElement("article");
    panel.className = "panel";
    panel.dataset.providerDocs = "true";
    const title = document.createElement("div");
    title.className = "panel-title";
    const heading = document.createElement("h4");
    heading.textContent = tx("ขอ API และอนุมัติ provider", "Provider API access and approval");
    const badge = document.createElement("span");
    badge.className = "status-badge";
    badge.textContent = tx("เจ้าของบัญชีดำเนินการ", "Owner action required");
    title.append(heading, badge);
    const note = document.createElement("p");
    note.className = "muted small";
    note.textContent = tx("เปิดคู่มือหรือแบบฟอร์ม TH/EN ได้จากที่นี่ ห้ามใส่ token หรือ secret ใน Dashboard", "Open the TH/EN guides or approval workbook here. Never enter tokens or secrets in the Dashboard.");
    const actions = document.createElement("div");
    actions.className = "view-actions";
    const channels = document.createElement("button");
    channels.type = "button";
    channels.className = "button-secondary";
    channels.dataset.viewAction = "integrations";
    channels.textContent = tx("ดู Channels", "View Channels");
    const th = document.createElement("a");
    th.className = "button-secondary";
    th.target = "_blank";
    th.rel = "noreferrer";
    th.href = "/guides/PROVIDER-APPROVAL-FORM_TH.md";
    th.textContent = tx("แบบฟอร์ม TH ↗", "TH approval ↗");
    const en = document.createElement("a");
    en.className = "button-secondary";
    en.target = "_blank";
    en.rel = "noreferrer";
    en.href = "/guides/PROVIDER-APPROVAL-FORM_EN.md";
    en.textContent = tx("แบบฟอร์ม EN ↗", "EN approval ↗");
    actions.append(channels, th, en);
    panel.append(title, note, actions);
    anchor.before(panel);
  }

  function renderIntegrations() {
    const guides = state.integrationGuides.map((guide) => `<article class="panel"><div class="panel-title"><h4>${esc(guide.name)}</h4><span class="status-badge">${tx("คู่มือ API", "API guide")}</span></div><p class="muted small">${esc(localized(guide, "th", ""))}</p><div class="view-actions"><a class="button-secondary" href="${esc(guide.guide_th)}" target="_blank" rel="noreferrer">TH ↗</a><a class="button-secondary" href="${esc(guide.guide_en)}" target="_blank" rel="noreferrer">EN ↗</a></div></article>`).join("");
    $("#view").innerHTML = `<div class="view-head"><div><h3>${tx("Channels และสถานะการเชื่อมต่อ", "Channels & connection truth")}</h3><p>${tx("สถานะจะเปลี่ยนเมื่อ credentials และ verification ถูกตั้งค่าที่ server เท่านั้น", "Status changes only after server-side credentials and verification.")}</p></div><div class="view-actions"><button class="button-secondary" data-view-action="agents">${tx("ดู agents", "View agents")}</button></div></div><div class="entity-grid">${state.integrations.map((item) => { const label = state.lang === "th" ? item.label_th : item.label_en; const note = state.lang === "th" ? item.setup_note_th : item.setup_note_en; return `<article class="panel"><div class="panel-title"><h4>${esc(label || item.label || item.provider)}</h4>${statusBadge(item.status)}</div><p class="muted small">${esc(note || item.setup_note || tx("ตรวจ setup ที่ server", "Review server-side setup"))}</p><span class="code-line">${esc(item.webhook_path)}</span></article>`; }).join("")}</div><h3 style="margin:1.25rem 0 .75rem">${tx("คู่มือขอ API", "API onboarding guides")}</h3><div class="entity-grid">${guides || empty(tx("ยังไม่มีคู่มือ", "No guides yet"))}</div><article class="panel" style="margin-top:.85rem"><div class="callout">${tx("Facebook Page: @spookyuperfect · TikTok Shop และ Shopee ต้องผ่าน account-owner setup ก่อนรับส่งข้อความจริง ระบบ local ยังไม่อ้างว่าเชื่อมต่อแล้ว", "Facebook Page: @spookyuperfect. TikTok Shop and Shopee require account-owner setup before real messaging. The local system does not claim they are connected.")}</div></article>`;
  }

  function renderSalesAssets() {
    const pack = state.salesAssets || {};
    const products = Object.entries(pack.products || {});
    const intents = Object.entries(pack.intents || {});
    const productCards = products.map(([id, product]) => {
      const media = (product.assets || []).slice(0, 4).map((asset) => `<figure class="asset-card"><img src="${esc(assetUrl(asset.path))}" alt="${esc(asset.alt || id)}" loading="lazy"><figcaption>${esc(asset.kind || "product media")}</figcaption></figure>`).join("");
      const points = (product.selling_points?.[state.lang] || product.selling_points?.th || []).map((point) => `<li>${esc(point)}</li>`).join("");
      const productName = state.products.find((item) => item.id === id)?.name || id;
      const cta = (product.closing_cta?.[state.lang] || product.closing_cta?.th || "").replaceAll("{{product_name}}", productName);
      const status = product.catalog_status === "active" ? t("common.active") : t("common.referenceOnly");
      return `<article class="panel asset-product"><div class="panel-title"><div><h4>${esc(id)}</h4><span class="muted small">${esc(status)} · ${esc(product.close_mode || t("common.catalogReview"))}</span></div><span class="status-badge ${product.catalog_status === "active" ? "ready" : "degraded"}">${esc(product.price_note || status)}</span></div><div class="asset-gallery">${media || empty(tx("ยังไม่มีภาพ local", "No local media"))}</div><ul class="asset-points">${points}</ul><div class="callout teal"><strong>${tx("CTA ปิดการขาย", "Closing CTA")}</strong><br>${esc(cta)}</div></article>`;
    }).join("");
    const intentRows = intents.map(([id, intent]) => `<div class="data-row"><div><strong>${esc(id)}</strong><small>${(intent.keywords?.[state.lang] || intent.keywords?.th || []).map(esc).join(", ")}</small></div><span class="status-badge ready">${tx("ตอบได้", "Ready")}</span></div>`).join("");
    $("#view").innerHTML = `<div class="view-head"><div><h3>${tx("Sales Assets และข้อความปิดการขาย", "Sales assets and closing replies")}</h3><p>${tx("ชุดข้อความ TH/EN และภาพสินค้าที่ตรวจสอบแล้วจากไฟล์ local สำหรับ Autobot และแอดมิน", "Validated TH/EN response copy and local product media for the Autobot and admins.")}</p></div><div class="view-actions"><button class="button-secondary" data-view-action="integrations">${tx("ดูคู่มือ API", "View API guides")}</button></div></div><div class="callout">${tx("โทนแอดมินเป็นมิตร น่ารัก ชวนซื้อ และมี CTA แต่จะไม่แต่งราคา สต็อก ค่าส่ง ผลลัพธ์ทางการแพทย์ หรือการอนุมัติชำระเงินที่ยังไม่ยืนยัน", "The admin tone is warm, friendly, purchase-oriented, and CTA-led, while never inventing prices, stock, shipping, medical outcomes, or payment approval.")}</div><div class="asset-grid" style="margin-top:.85rem">${productCards || empty(t("common.empty"))}</div><article class="panel" style="margin-top:.85rem"><div class="panel-title"><h4>${tx("Intents ที่ Autobot รองรับ", "Supported Autobot intents")}</h4><span class="muted small">${intents.length} ${t("common.records")}</span></div><div class="data-list">${intentRows || empty(t("common.empty"))}</div></article>`;
  }

  function renderSettings() {
    const settings = state.settings || {};
    const th = state.lang === "th";
    const localAi = state.integrations.find((item) => item.provider === "local_ai") || {};
    const checked = (key) => settings[key] ? "checked" : "";
    $("#view").innerHTML = `
      <div class="view-head"><div><h3>${th ? "ตั้งค่าระบบ" : "System settings"}</h3><p>${th ? "กำหนดโปรไฟล์ร้าน พฤติกรรม Autobot และการแจ้งเตือน" : "Configure the store profile, Autobot behavior, and notifications."}</p></div><div class="view-actions"><span class="status-badge ready">${th ? "บันทึกที่ server" : "Server persisted"}</span></div></div>
      <form id="settings-form" class="settings-grid">
        <article class="panel"><div class="panel-title"><h4>${th ? "โปรไฟล์ร้าน" : "Store profile"}</h4><span class="muted small">U.Perfect</span></div>
          <div class="form-grid">
            <div class="field"><label for="setting-store-name">${th ? "ชื่อร้าน" : "Store name"}</label><input id="setting-store-name" value="${esc(settings.store_name)}" required maxlength="120"></div>
            <div class="field"><label for="setting-store-handle">${th ? "บัญชีผู้ดูแล" : "Store handle"}</label><input id="setting-store-handle" value="${esc(settings.store_handle)}" required maxlength="120"></div>
            <div class="field"><label for="setting-timezone">${th ? "เขตเวลา" : "Timezone"}</label><select id="setting-timezone"><option value="Asia/Bangkok" ${settings.timezone === "Asia/Bangkok" ? "selected" : ""}>Asia/Bangkok</option><option value="Asia/Singapore" ${settings.timezone === "Asia/Singapore" ? "selected" : ""}>Asia/Singapore</option><option value="UTC" ${settings.timezone === "UTC" ? "selected" : ""}>UTC</option></select></div>
            <div class="field"><label for="setting-language">${th ? "ภาษาเริ่มต้น" : "Default language"}</label><select id="setting-language"><option value="th" ${settings.default_language === "th" ? "selected" : ""}>ไทย (TH)</option><option value="en" ${settings.default_language === "en" ? "selected" : ""}>English (EN)</option></select></div>
            <div class="field"><label for="setting-tone">${th ? "โทนคำตอบ Autobot" : "Assistant tone"}</label><select id="setting-tone"><option value="warm" ${settings.assistant_tone === "warm" ? "selected" : ""}>${th ? "เป็นมิตร" : "Warm"}</option><option value="formal" ${settings.assistant_tone === "formal" ? "selected" : ""}>${th ? "สุภาพทางการ" : "Formal"}</option><option value="concise" ${settings.assistant_tone === "concise" ? "selected" : ""}>${th ? "กระชับ" : "Concise"}</option></select></div>
          </div>
          <div class="setting-reference"><span class="muted small">Facebook reference</span><a href="${esc(settings.facebook_page_url)}" target="_blank" rel="noreferrer">${esc(settings.facebook_page_url)} ↗</a></div>
        </article>
        <article class="panel"><div class="panel-title"><h4>${th ? "พฤติกรรม Autobot" : "Autobot behavior"}</h4><span class="status-badge ${settings.autobot_enabled ? "ready" : "degraded"}">${settings.autobot_enabled ? (th ? "เปิด" : "On") : (th ? "ปิด" : "Off")}</span></div>
          <div class="switch-list">
            ${settingSwitch("setting-autobot", "autobot_enabled", checked("autobot_enabled"), th ? "เปิด Autobot" : "Enable Autobot", th ? "ตอบตาม product memory และกฎความปลอดภัย" : "Reply using product memory and safety rules")}
            <div class="field"><label for="setting-timeout">${th ? "เวลาส่งต่อให้แอดมิน (นาที)" : "Human takeover timeout (minutes)"}</label><input id="setting-timeout" type="number" min="1" max="1440" value="${esc(settings.human_takeover_timeout_minutes)}" required></div>
          </div>
        </article>
        <article class="panel"><div class="panel-title"><h4>${th ? "Automation" : "Automation"}</h4><span class="muted small">n8n</span></div>
          <div class="switch-list">
            ${settingSwitch("setting-n8n-post", "n8n_auto_post_enabled", checked("n8n_auto_post_enabled"), th ? "อนุญาต Auto post" : "Allow auto post", th ? "ยังต้องผ่าน n8n credential และการตรวจสอบบัญชี" : "Requires n8n credentials and account verification")}
            ${settingSwitch("setting-n8n-comment", "n8n_comment_reply_enabled", checked("n8n_comment_reply_enabled"), th ? "อนุญาตตอบ comment" : "Allow comment replies", th ? "เป็น preference เท่านั้นจนกว่า workflow จะ verified" : "Preference only until the workflow is verified")}
          </div>
        </article>
        <article class="panel"><div class="panel-title"><h4>${th ? "การแจ้งเตือน" : "Notifications"}</h4><span class="muted small">LINE</span></div>
          <div class="switch-list">
            ${settingSwitch("setting-line", "line_notifications_enabled", checked("line_notifications_enabled"), th ? "แจ้งเตือนผ่าน LINE" : "LINE notifications", th ? "จะส่งได้เมื่อ LINE integration ถูกตั้งค่าที่ server" : "Delivery starts only after LINE is configured server-side")}
            ${settingSwitch("setting-payment-alert", "payment_review_alerts_enabled", checked("payment_review_alerts_enabled"), th ? "แจ้งเตือนรอตรวจสลิป" : "Payment review alerts", th ? "แจ้งเตือนเมื่อมีหลักฐานรอตรวจสอบ" : "Notify when payment evidence needs review")}
          </div>
        </article>
        <article class="panel"><div class="panel-title"><h4>${th ? "Runtime แบบ local-only" : "Local-only runtime"}</h4>${statusBadge(localAi.status || "unconfigured")}</div>
          <div class="data-row"><div><strong>${th ? "เครื่องที่อนุญาต" : "Allowed host"}</strong><small>${th ? "ทุก service ในชุดนี้ใช้ LAN host เดียว" : "All runtime services use one LAN host."}</small></div><code class="code-line">${esc(settings.local_host || "192.168.74.130")}</code></div>
          <div class="data-row"><div><strong>Ollama</strong><small>${th ? "AI แบบไม่เสียค่าใช้จ่าย ไม่ส่งข้อมูลออกนอกเครื่อง" : "No-cost AI with no external provider."}</small></div><code class="code-line">${esc(settings.local_ai_base_url || "http://192.168.74.130:11434")}</code></div>
          <div class="data-row"><div><strong>${th ? "โมเดล" : "Model"}</strong><small>${th ? "ตรวจจาก /api/tags แบบ live" : "Checked live from /api/tags."}</small></div><code class="code-line">${esc(settings.local_ai_model || "zCoder:latest")}</code></div>
          <div class="callout teal">${th ? "โหมดนี้ไม่เก็บ API key และไม่เปิดใช้ Gemini, LINE, n8n หรือ marketplace credentials โดยอัตโนมัติ" : "This mode stores no API key and does not enable Gemini, LINE, n8n, or marketplace credentials."}</div>
        </article>
        <div class="settings-actions"><button class="button" type="submit">${th ? "บันทึกการตั้งค่า" : "Save settings"}</button><span class="muted small">${th ? "ข้อมูลตั้งค่าจะไม่เก็บ token หรือ secret" : "Credentials and secrets are never stored here."}</span></div>
      </form>`;
  }

  function settingSwitch(id, key, checkedAttribute, label, note) {
    return `<label class="switch-row" for="${id}"><span><strong>${esc(label)}</strong><small>${esc(note)}</small></span><span class="switch-control"><input id="${id}" data-setting-key="${key}" type="checkbox" ${checkedAttribute}><span class="switch-track" aria-hidden="true"><span class="switch-thumb"></span></span></span></label>`;
  }

  async function submitMessage(payload) {
    const result = await api("/api/messages", { method: "POST", body: JSON.stringify(payload) });
    state.selectedConversation = result.conversation.id;
    await loadDashboard();
    state.view = "inbox";
    render();
    return result;
  }

  async function setTakeover(id, enabled) {
    await api(`/api/conversations/${encodeURIComponent(id)}/takeover`, { method: "POST", body: JSON.stringify({ enabled }) });
    await loadDashboard();
    state.view = "inbox";
    render();
  }

  function setView(view) {
    state.view = view;
    window.location.hash = view;
    render();
  }

  document.addEventListener("click", async (event) => {
    const viewButton = event.target.closest("[data-view], [data-view-action]");
    if (viewButton) { setView(viewButton.dataset.view || viewButton.dataset.viewAction); return; }
    const conversation = event.target.closest("[data-conversation]");
    if (conversation) { state.selectedConversation = conversation.dataset.conversation; render(); return; }
    const paymentButton = event.target.closest("[data-payment]");
    if (paymentButton) {
      const reference = window.prompt(tx("เลขอ้างอิงหลักฐานการชำระเงิน", "Payment evidence reference"));
      if (!reference) return;
      try { await api(`/api/orders/${paymentButton.dataset.payment}/payment-evidence`, { method: "POST", body: JSON.stringify({ reference }) }); await loadDashboard(); state.view = "orders"; render(); } catch (error) { showNotice(`${error.code}: ${error.message}`); }
      return;
    }
    const confirmButton = event.target.closest("[data-confirm]");
    if (confirmButton) {
      try { await api(`/api/orders/${confirmButton.dataset.confirm}/transition`, { method: "POST", body: JSON.stringify({ target: "confirmed", actor: "admin" }) }); await loadDashboard(); state.view = "orders"; render(); } catch (error) { showNotice(`${error.code}: ${error.message}`); }
    }
  });

  document.addEventListener("change", async (event) => {
    const takeover = event.target.closest("[data-takeover]");
    if (!takeover) return;
    try { await setTakeover(takeover.dataset.takeover, takeover.checked); } catch (error) { showNotice(`${error.code}: ${error.message}`); }
  });

  document.addEventListener("submit", async (event) => {
    if (event.target.id === "message-form") {
      event.preventDefault();
      try { await submitMessage({ platform: $("#message-platform").value, customer_id: $("#message-customer").value, text: $("#message-text").value }); } catch (error) { showNotice(`${error.code}: ${error.message}`); }
    }
    if (event.target.id === "order-form") {
      event.preventDefault();
      try {
        await api("/api/orders", { method: "POST", body: JSON.stringify({ product_id: $("#order-product").value, quantity: Number($("#order-quantity").value), customer_name: $("#order-customer").value }) });
        await loadDashboard(); state.view = "orders"; render(); showNotice(tx("สร้าง awaiting payment แล้ว", "Awaiting-payment order created"), "success");
      } catch (error) { showNotice(`${error.code}: ${error.message}`); }
    }
    if (event.target.id === "settings-form") {
      event.preventDefault();
      const payload = {
        store_name: $("#setting-store-name").value.trim(),
        store_handle: $("#setting-store-handle").value.trim(),
        timezone: $("#setting-timezone").value,
        default_language: $("#setting-language").value,
        assistant_tone: $("#setting-tone").value,
        autobot_enabled: $("#setting-autobot").checked,
        human_takeover_timeout_minutes: Number($("#setting-timeout").value),
        n8n_auto_post_enabled: $("#setting-n8n-post").checked,
        n8n_comment_reply_enabled: $("#setting-n8n-comment").checked,
        line_notifications_enabled: $("#setting-line").checked,
        payment_review_alerts_enabled: $("#setting-payment-alert").checked
      };
      try {
        state.settings = await api("/api/settings", { method: "PATCH", body: JSON.stringify(payload) });
        if (state.settings.default_language !== state.lang) {
          state.lang = state.settings.default_language;
          localStorage.setItem("uperfect-language", state.lang);
        }
        render();
        showNotice(state.lang === "th" ? "บันทึกการตั้งค่าแล้ว" : "Settings saved", "success");
      } catch (error) { showNotice(`${error.code}: ${error.message}`); }
    }
  });

  $("#refresh-button").addEventListener("click", loadDashboard);
  $("#language-toggle").addEventListener("click", () => { state.lang = state.lang === "th" ? "en" : "th"; localStorage.setItem("uperfect-language", state.lang); render(); });
  $("#mobile-menu").addEventListener("click", () => { $(".sidebar").classList.toggle("is-mobile-open"); });
  window.addEventListener("hashchange", () => { state.view = window.location.hash.slice(1) || "overview"; render(); });
  if ("serviceWorker" in navigator) window.addEventListener("load", () => navigator.serviceWorker.register("/service-worker.js?v=20260810-local-v7").catch(() => {}));

  window.UperfectApp = { loadDashboard, setTakeover, submitMessage };
  loadDashboard();
})();
