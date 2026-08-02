# Security Policy

## Reporting a vulnerability

Please report security issues privately to **epixel@hctbilisim.com** rather than
opening a public issue. Include enough detail to reproduce the problem; we will
acknowledge within five working days and keep you updated until it is resolved.

If you would like credit in the release notes, say so in your report.

## Scope

This policy covers the Home Assistant integration in this repository and the
local protocol it implements ([PROTOCOL.md](PROTOCOL.md)). Findings in the ePiXeL
display firmware or the management platform are equally welcome at the same
address.

## Design notes relevant to security researchers

- All traffic between the display and Home Assistant stays on the local network.
  The display initiates every connection and **opens no listening port**.
- The display connects to **private IP addresses only**; public addresses are
  refused, so a compromised configuration cannot turn the display into an
  outbound request source.
- The integration exposes **only the entities the user selected** — a stolen
  pairing token cannot reach the rest of the Home Assistant instance.
- The display's platform credentials and its serial identity are **never sent**
  to Home Assistant, and Home Assistant data is **never forwarded** to ePiXeL
  servers.
- Pairing is limited by a 180-second window, five attempts and three concurrent
  pending requests.

**Known and accepted:** the pairing token travels over plain HTTP on the local
network. An attacker already able to observe LAN traffic could capture it. The
token's authority is limited to the selected entities and can be revoked by
deleting the integration. Support for TLS-only Home Assistant installations is
on the roadmap.
