# Local RPC contract

CudyPy implements the local app RPC interface inferred from Cudy app behavior.
It is not an official protocol specification or a guarantee of firmware parity.

## Endpoints and envelopes

- Authentication: `/cgi-bin/luci/rpc/auth`.
- App operations: `/cgi-bin/luci/rpc/app`, with the session token in the
  `auth` query parameter.
- Request body: `{"method": "system.info", "params": []}`.
- Responses contain a `result` or an `error`; numeric error codes are preserved.
  The client does not rely on response IDs.
- Local requests omit device IDs. Browser HTML forms are a different interface;
  their form/CSRF fields are not copied into app RPC calls.

Tokens are credentials. Do not publish request URLs, debug logs or private
configuration. The client rejects redirects and does not use environment proxies.

## Authentication

Password login requests a challenge with `token`, then sends `login` with
`["admin", digest]`. The digest is calculated as
`sha256(sha256(password + salt).hexdigest() + challenge).hexdigest()`.
The salt can be supplied or discovered through mDNS. A supplied session token
bypasses password login and discovery. See [compatibility](compatibility.md)
for verification limits.

## Client pagination

`devices.get_devlist_ex` accepts no arguments for the full-list request, or
inclusive `[start, end]` ranges. A response contains `devlist` and may contain
`devcnt`. `[1, 1]` means one client, not all clients.

The wrapper starts with the full-list request and follows ranges when the
reported count exceeds the returned list. Duplicate records, inconsistent
counts and malformed pages raise errors rather than silently truncating data.
Mesh client pages prepend a caller-selected node identifier to the bounds.

## Retry and mutation boundaries

Only known read operations may retry once after explicit authentication
rejection when a password is available. Transport failures and writes are never
automatically replayed. A lost response does not prove a mutation failed.

The generic `call_api` returns the full envelope and may invoke mutations.
It is not a safe way to probe unknown operations. Use only documented payloads
whose effects you understand.

See [feature reads](feature-reads.md), [client controls](client-controls.md),
[wireless configuration](wireless.md), and [device semantics](device-semantics.md)
for method-specific parameters, types and interpretation limits.
