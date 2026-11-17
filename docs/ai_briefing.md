# What the AI assistant gets

When an AI assistant connects to HeatTransPlan's MCP server (at the app's `/mcp` address, see [API and AI assistants](api_and_mcp.md)), it receives everything on this page: what the app does, how to work with you, the steps of a study and what each tool does. Nothing else tells it about the app.

This page is built from the MCP server's own code (`mcp_server/heattransplan_mcp/texts.py` and `server.py`) each time the documentation is built, so it always shows exactly what an assistant gets.

**How it fits together.** The assistant reads the **instructions** as soon as it connects. When you give it the Connect AI code, it calls **`start`**, which shows what your page holds and offers the **ways of working**, along with its **rules**. For the method behind a result it reads the documentation pages through **`explain`**. In a guided study it asks the questions from **`guide`**, step by step. Everything it does on your page goes through the **tools**.

---

## Instructions on connect

The text the assistant receives the moment it connects, word for word.

<!-- briefing:INSTRUCTIONS -->

## When you give it the code: `start`

`start` tells the assistant what your open page holds, then it offers you these ways of working:

<!-- briefing:MODES -->

and states the rules it keeps to, whichever you pick:

<!-- briefing:RULES -->

## The explanations it can read: `explain`

For the method and the meaning of a result, the assistant reads the same documentation pages you can read here. It's told to read them before explaining a result or when one surprises it.

<!-- briefing:TOPICS -->

## The steps of a guided study: `guide`

In a guided study, the assistant goes page by page as the app does and asks these questions. It asks only what your documents don't already answer.

<!-- briefing:GUIDE -->

## The tools

<!-- briefing:TOOLS -->
