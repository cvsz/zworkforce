---
name: zeaz-rag-chatbot
description: Designs grounded RAG and support chatbots with authorization filters, citations, and safe abstention.
version: 1.0.0
---
Define intents, knowledge ownership, access model, freshness SLA, and escalation. Chunk/index documents with stable source IDs. Apply authorization before retrieval; prompt text is not access control. Retrieve relevant chunks, cite sources, and abstain when evidence is absent, conflicting, stale, or weak. Test prompt injection, cross-tenant leakage, stale knowledge, hallucination, and abuse. Measure recall, grounded-answer rate, abstention, latency, and cost.
