---
doc_id: KB-IT-001
title: Corporate VPN Setup and Troubleshooting
department: IT
acl: [IT, HR, ALL]
version: "1.2"
source_system: local_files
source_url: https://kb.internal/it/vpn-setup
---
# Corporate VPN Setup

All employees use the corporate VPN client "SecureLink" for remote access.

## Installation
Download SecureLink from the internal software portal. Install requires local admin rights; request them via a hardware/access ticket if missing.

## Connecting
Use your Entra ID credentials with MFA. The client connects to the nearest regional gateway automatically.

## Common issues
- "Gateway unreachable": check your home firewall allows UDP 4500.
- "Certificate expired": run SecureLink update, then reconnect.
- VPN drops every hour: known issue on firmware < 5.1; update the client.
