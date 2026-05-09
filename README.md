---
title: Kernl Backend
emoji: 🧠
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# Kernl Backend

An operational knowledge to skill converter. Converts raw company documents, playbooks, SOPs, and chat logs into clean, structured, executable agent skills.

## Architecture
* **FastAPI**: Backend web framework
* **LangGraph**: Orchestrates the compilation DAG
* **Supabase**: Persistent knowledge base & session state
* **vLLM**: Serves open-source reasoning models (Qwen 2.5)
