# API Sync Strategy: E-Commerce & Conversational Channels

This document outlines the conceptual API integration guidelines, webhook routing mechanisms, and database syncing pipeline strategies required to transition the Zaapi clone mockup into a production-ready software suite.

---

## 1. Webhook Routing Pipeline

To support centralized instant messaging, the Zaapi platform relies on receiving real-time webhook callbacks from WhatsApp, Facebook, LINE, and TikTok APIs.

```text
  [Customer Messaging Channels]
   (WhatsApp, Messenger, LINE OA)
                │
                ▼ (POST Callback JSON payload)
   [Zaapi API Gateway / Webhooks Route]
                │
                ▼ (Publish Message Event)
       [RabbitMQ / Redis Queue]
                │
                ▼ (Consume Message)
   [Zaapi Chat Sync / CRM Service]
                │
                ├───────────► [Database Sync System]
                │
                ▼ (WebSocket Broadcast)
   [Client App Operator Dashboard]
```

### 1.1 Webhook Callback Example (WhatsApp Business Cloud API)
```json
{
  "object": "whatsapp_business_account",
  "entry": [{
    "id": "WHATSAPP_BUSINESS_ACCOUNT_ID",
    "changes": [{
      "value": {
        "messaging_product": "whatsapp",
        "metadata": {
          "display_phone_number": "16505550300",
          "phone_number_id": "PHONE_NUMBER_ID"
        },
        "contacts": [{
          "profile": { "name": "Wilfried Buiron" },
          "wa_id": "16508821190"
        }],
        "messages": [{
          "from": "16508821190",
          "id": "wamid.HBgLMTY1MDg4MjExOTAVAgASGBQzQjE2RkI1NjJDMDQ4...",
          "timestamp": "1783772810",
          "text": { "body": "Do you offer custom API endpoints for Shopify syncing?" },
          "type": "text"
        }]
      },
      "field": "messages"
    }]
  }]
}
```

---

## 2. Shopify Store Sync Engine
To show customer purchases inside the chat view, the Zaapi sync engine subscribes to Shopify webhook notifications:

* **Webhook Event**: `orders/create` & `orders/updated`
* **Trigger Event**: Updates the internal database conversation orders sync record, prompting an alert notification to operators.

### Sync Pipeline Sequence
1. Customer initiates chat from Shopify webstore widget, sending their browser-stored session token.
2. Zaapi correlates customer database records with Shopify email/phone payloads.
3. Chat operator sidebar fetches corresponding customer order history from database caches (re-synchronized every 15 minutes).
4. Automated Flow Builder references orders tags to verify if the customer qualifies for promotional rewards or refund waivers.
