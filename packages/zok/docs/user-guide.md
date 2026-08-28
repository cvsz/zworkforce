# User Guide: Navigating Zaapi Platform Copy-Clone

This guide explains how to install, run, and interact with the various features of the Zaapi copy-clone application.

---

## 1. Quick Start

### 1.1 Requirements
* **Node.js**: Version 18.0.0 or higher
* **npm**: Version 9.0.0 or higher

### 1.2 Running Development Server
Run the local preview server from the workspace root folder:
```bash
npm install
npm run dev
```
Open **`http://localhost:5175/`** in your browser.

---

## 2. Navigating the Views

### 2.1 Landing Page (Site View)
* **Explore Features**: Scroll down or use the header navigation links to review different product categories. Click different tabs (Unified Inbox, AI Agents Studio, Visual Flow Builder, Broadcast Campaigns) to inspect live feature specs.
* **Theme Switching**: Click the Sun/Moon icons in the navbar to switch the landing page between Light Mode and Dark Mode.
* **Enter Dashboard**: Click **Launch Web App** to transition to the App Clone.

### 2.2 Unified Inbox View
* **Channel Filtering**: Click the channel filter pills (All, WhatsApp, LINE, Messenger, TikTok, Shopify) above the conversation lists to filter records.
* **Messaging Simulator**: Select a customer chat, type a message in the input bar, and press **Send**. The recipient will receive the message, and an automated mock response will reply to keywords like "order", "price", "help", or "warranty" after a 1.5-second timeout.
* **CRM Panel**: Update customer details on the right sidebar. Add custom tags using the inline form. Review order history syncing from Shopify.

### 2.3 AI Agent Studio
* **Persona Configuration**: Select between Sales, Support, and Lead Generator personas to customize automated greetings.
* **Knowledge Training**: Modify the knowledge base textbox or add FAQ rules.
* **Agent Simulator**: Test your AI agent configuration in real-time in the sidebar preview console.

### 2.4 No-Code Flow Builder
* **Drag-and-Drop Canvas**: Press your mouse on any node and drag it across the grid canvas.
* **Add Nodes**: Click **Add Action Node** to generate a step at a random position.
* **Node Inspector**: Click any node on the canvas to configure title text or parameter rules in the sidebar settings.

### 2.5 Broadcast Campaigns
* **Draft Broadcasts**: Select channel targets, tags segments, and promotion templates.
* **Dispatch Simulation**: Click **Send Broadcast Now** to trigger progress meters. Once completed, the campaign statistics log auto-updates.

### 2.6 App & Channel Integrations
* **Channels Toggle**: Switch toggles to simulate linking Shopify or TikTok.
* **Developer Webhook Log**: Review webhook payload logs writing to the debug console in real-time.
