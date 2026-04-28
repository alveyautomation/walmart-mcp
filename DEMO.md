# 5-Minute Demo Script

Use this script to record a Loom walkthrough of `walmart-mcp` for the launch posts. Total target: **5 minutes**.

Record in 1080p, monospace terminal at 14pt minimum. Use a sandbox / test Walmart Marketplace account, never the production seller account.

## Setup before hitting record

- Fresh terminal window (cleared scrollback).
- `.env` populated with sandbox consumer ID + private key. Test that `walmart-mcp` runs and Claude Code sees the tools.
- Have the README open in a second tab for the cold open.
- Have one product, one order, and one settlement report pre-identified in the sandbox so live queries return non-empty results.

## Script

### 0:00. 0:30  Cold open

> "If you sell on Walmart Marketplace and you've ever wanted Claude to just *know* what's in your catalog, this is for you. I built `walmart-mcp`, a Model Context Protocol server for Walmart Marketplace. Read-only, MIT-licensed, takes about 90 seconds to install."

Show the README hero section. Pan slowly through the tool table.

### 0:30. 1:30  Install and configure

Show in the terminal:

```bash
pip install walmart-mcp
cp .env.example .env
# edit .env: paste sandbox consumer ID + private key
```

Then show the Claude Code MCP config block, paste it into `~/.claude/claude_code_config.json`. Restart Claude Code. Show the new tools showing up in a new session.

> "Three env vars and one config block. That's it. The signing happens automatically, you don't write a line of crypto code."

### 1:30. 2:30  Live demo: search

Open a fresh Claude Code session. Type:

> "Use walmart to search the catalog for any product matching 'widget' and tell me how many results there are."

Watch Claude call `walmart_search_products`, return results. React to the output. Read off the count.

### 2:30. 3:30  Live demo: orders

> "Show me yesterday's Walmart orders. Group by status."

Claude calls `walmart_search_orders`, gets a list, groups them. Show the resulting summary in the chat.

> "Notice that I never wrote any code. Claude is reading Walmart Marketplace directly through the MCP server."

### 3:30. 4:30  Live demo: combined operation

> "Pick one of those orders. Tell me the line items, then check the current inventory and pricing for each SKU and flag any inventory below 10 units."

Claude calls `walmart_get_order`, then `walmart_get_inventory` and `walmart_get_pricing` per line item. Highlight the multi-step reasoning happening over the MCP surface.

> "This is the unlock. Claude can chain reads across catalog, orders, inventory, and pricing in one conversation. Without an SDK. Without any code I had to write."

### 4:30. 5:00  Close

Show the GitHub repo briefly. Mention:

- MIT-licensed, free to use
- Read-only in v0.1, write tools coming in v0.2
- Open to issues + PRs
- Star + share if it's useful

> "Repo link in the description. v0.2 with write tools is a few weeks out, leave a comment if there's a specific endpoint you'd like exposed first."

End on the README hero shot.

## Post-recording

- Trim silence at start/end.
- Add captions (Loom auto-caption is fine, just review for brand-name accuracy).
- Thumbnail: a screenshot of the multi-step demo with the tool calls visible.

## Distribution

After recording, the launch posts go to:

1. **Twitter/X**, single thread, 6-8 tweets, embed the Loom in tweet 1.
2. **Reddit r/MCP**, title: *"walmart-mcp: Model Context Protocol server for Walmart Marketplace (read-only, MIT)"*. Body: short framing + Loom + GitHub link.
3. **Reddit r/WalmartSellers** (or r/AmazonSeller cross-post for marketplace audience), different framing, lead with the use case (*"Use Claude to query your Walmart catalog, orders, and settlement reports"*), Loom + GitHub link.

Draft copy for all three lives in `LAUNCH_POSTS.md` (to be created).
