# NextChat Pattern Upgrade

This upgrade was informed by a full-source review of ChatGPTNextWeb/NextChat at commit `706a18b95b714ab29b2a4842d3b9ff4f887935d5` under its MIT license.

## Adopted patterns

- Full-text conversation search across titles, models, system prompts, and messages
- Per-message copy and reuse-as-draft actions
- Keyboard-first navigation for conversation search and new-chat creation
- Responsive message action controls
- Conversation branching and bounded transcript rendering
- Per-conversation drafts and model selection
- Strictly validated, size-limited JSON import
- Message and conversation deletion with explicit confirmation

The implementation is native to ZChat and does not copy NextChat source code.

## Deliberately excluded patterns

- Browser-managed provider API keys
- Arbitrary provider proxy URLs
- Browser-managed WebDAV credentials
- Untrusted plugin or MCP execution
- Desktop runtime, image-generation, and analytics integrations

ZChat remains a trust-minimized, gateway-only client. Provider credentials and provider routing stay behind the Z Platform AI gateway, while browser persistence is limited to conversation content, preferences, and prompt templates.

## Follow-up candidates

- IndexedDB migration after measured local-storage pressure
- Full virtualized transcript rendering after bounded rendering is insufficient in measured workloads
