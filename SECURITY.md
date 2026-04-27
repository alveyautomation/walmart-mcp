# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in `walmart-mcp`, please report it
responsibly. Do **not** open a public GitHub issue for security concerns.

**Contact:** open a private security advisory on the GitHub repository (path TBD
post-launch), or email the maintainer directly. We aim to respond to reports
within 72 hours.

## Scope

In scope:

- The MCP server entry point (`walmart_mcp/server.py`)
- The Walmart Marketplace HTTP client (`walmart_mcp/client.py`)
- Configuration and credential handling (`walmart_mcp/config.py`)
- Packaged dependencies and their pinned versions

Out of scope:

- The upstream Walmart Marketplace REST API itself (report directly to Walmart)
- The MCP protocol specification or the official MCP Python SDK
- Bugs that require an attacker to already control the host running the server

## Credential handling

This project never logs Walmart credentials, never persists them outside the
process, and reads them only from environment variables. The RSA private key
is loaded into memory once at startup; signatures are computed per-request and
discarded. If you find a code path that violates this, report it as a security
issue.

## Disclosure timeline

Our default policy is coordinated disclosure: we will work with the reporter to
ship a fix and credit the discovery on a timeline that gives users time to
upgrade. The default embargo is 30 days from confirmed reproduction.
