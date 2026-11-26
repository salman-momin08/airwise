# ADR 0004: Secure HTTP-Only Cookie Sessions with CSRF & Refresh Rotation

- **Status:** Accepted
- **Date:** 2026-11-19

## Context
Storing bearer JWTs in browser `localStorage` exposes user accounts and sensitive household/chat data to token exfiltration if any XSS gadget ever occurs. Furthermore, stateless JWTs alone cannot be immediately revoked on logout, password reset, or compromise.

## Decision
Use **Argon2id** password hashing and **server-tracked sessions (`user_sessions`)** delivered via `HttpOnly`, `Secure`, `SameSite=Lax` cookies, protected by **double-submit CSRF tokens (`X-CSRF-Token`) + `Origin` checks** on all state-changing endpoints, with rotating refresh tokens and instant server-side session invalidation.

## Consequences
- **Positive:** Immune to `localStorage` token theft; supports immediate "log out all devices" and account deletion revocation; works seamlessly with Next.js Server Components and SSE streams.
- **Requirement:** Frontend API client must send `credentials: "include"` and attach `X-CSRF-Token` on `POST`/`PATCH`/`DELETE` requests; CORS must explicitly allow only configured frontend origins.
