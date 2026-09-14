---
doc_id: KB-IT-006
title: VPN Deep Troubleshooting Guide
department: IT
acl: [IT]
version: "2.0"
source_system: local_files
source_url: "https://kb.internal/it/vpn-deep"
---
# VPN Deep Troubleshooting (IT staff only)

## Split tunneling
Split tunneling is enabled for SaaS traffic only. Corporate subnets always route through the tunnel. Verify with `securelink status --routes`.

## DNS resolution failures
If intranet names fail to resolve while connected, flush the client DNS cache and confirm the assigned resolver is 10.0.0.53. Public DNS over HTTPS must be disabled in the client.

## Packet capture
For persistent drops, capture a 60-second packet trace with `securelink diag --capture 60` and attach it to the ticket. Traces auto-expire after 24 hours.

## Escalation
Issues unresolved after client update + DNS flush escalate to the network team with the capture attached. Do not share captures outside IT.
