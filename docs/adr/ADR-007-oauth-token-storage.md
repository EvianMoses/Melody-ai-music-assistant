# ADR-007: OAuth token storage — Fernet-encrypted columns in PostgreSQL

- **Status:** Accepted
- **Date:** 2026-07-25
- **Phase / tasks:** Phase 5 §5.2 (`AUTH-001`…`AUTH-007`), Section 2.3 data model (`oauth_accounts`)
- **Relates to:** ADR-001 (architecture boundaries), ADR-002 (provider mode — direct YouTube), ADR-005 (n8n deployment mode)

## Context

Section 2.3 lists nineteen tables. Eighteen were implemented in Phase 2; the
nineteenth — `oauth_accounts`, *"Provider, encrypted token material/reference,
scopes, expiry, revocation state"* — was explicitly **deferred to Phase 5
"where the encrypted-token-storage decision is made."** This ADR is that
decision.

The constraint is stated as an absolute rule in the same section:

> OAuth token values are encrypted or stored in an approved secret store; never
> plaintext columns.

Two further facts shape the decision:

1. **The existing Spotify path does the opposite of what we need.** `app.py`
   uses spotipy's `FlaskSessionCacheHandler`, which stores the access **and
   refresh** token inside the Flask session cookie. Flask cookies are *signed,
   not encrypted* — the contents are base64-readable by anyone holding the
   cookie, and a refresh token is a long-lived credential. This is a real
   weakness in the legacy path, which the July 25 decision deliberately leaves
   unrepaired (Section 2.3 scopes AWS/Spotify legacy to "a known-good rollback"
   that "must not define the new design"). It must not be the pattern for
   Google.
2. **More than one component will need these tokens.** Flask performs the OAuth
   dance (Section 2.2: *"OAuth start/callback UX"*), but `provider-gateway`
   needs the access token for authorized YouTube calls in §5.5 export, and
   WF-009 reads connection state from n8n's Postgres nodes. Whatever holds the
   tokens must be reachable by all three — which a Flask session cookie is not.

## Decision

1. **Tokens are stored in PostgreSQL, in the `oauth_accounts` table, encrypted
   at the application layer.** Never in the session cookie; the cookie carries
   only `user_id`, an opaque reference.
2. **Fernet (AES-128-CBC + HMAC-SHA256) via the `cryptography` package** is the
   encryption scheme, implemented once in `contracts/token_crypto.py`. Both
   `encrypted_access_token` and `encrypted_refresh_token` hold ciphertext.
3. **The key comes from `OAUTH_TOKEN_ENCRYPTION_KEY`, which accepts a
   comma-separated list.** `MultiFernet` encrypts with the first key and
   decrypts with any, so rotation is: prepend a new key, re-encrypt rows in the
   background, drop the old key. Each row records `encryption_key_id` — a
   SHA-256 prefix of the key, not the key itself — so it is always knowable
   which key sealed a given row.
4. **There is no plaintext fallback.** A missing or malformed key raises
   `TokenCryptoError`; the sign-in fails with `SERVER_MISCONFIGURED` rather
   than storing an unencrypted token.
5. **The helper lives in `contracts/`, not `shared_lib/`.** It encrypts a column
   defined next door in `contracts/db_models.py`, and services already
   `COPY contracts /app/contracts`.

## Rationale

**Why Fernet rather than raw AES-GCM.** Fernet is misuse-resistant: it is
authenticated by construction and derives a fresh IV per message internally.
Raw AES-GCM requires the caller to manage nonces, and nonce reuse under GCM is
catastrophic *and silent* — it leaks the authentication key. There is no
performance argument at this volume that outweighs removing an entire class of
implementation error. Fernet also produces a self-describing urlsafe-base64
token, so the column is plain `Text` with no binary-encoding concerns.

**Why an env-var key rather than a managed secret store.** Section 2.3 permits
"an approved secret store" as the alternative. It is rejected *for now* on
deployment-target grounds: §9.7 names a single economical VPS as the production
host, and ADR-005 already moved the stack toward "no public ports except
Flask." Introducing KMS/Vault would add a cloud dependency the project is
deliberately shedding, plus an availability dependency on the auth path. The
`encryption_key_id` column is the hedge: because every row records which key
sealed it, migrating to a KMS later is a re-encryption migration, not a
redesign.

**Why the application layer rather than PostgreSQL `pgcrypto`.** Column-level
encryption inside the database means the key must be supplied to the database —
in a query string, a session variable, or a config file — which puts key
material into query logs and `pg_stat_activity`. Encrypting before the value
leaves the application keeps the database a pure ciphertext store, which is
also what makes the ADR-005 topology meaningful: a database compromise alone
does not yield usable tokens.

**Why `sub` and not email is the account key.** `oauth_accounts` is unique on
`(provider, provider_account_id)`, where `provider_account_id` is the OIDC
`sub` claim. Email addresses are mutable on the provider side; `sub` is stable
for the life of the account.

## Alternatives considered

- **Flask session cookie (what legacy Spotify does).** Rejected: signed but not
  encrypted, so a stolen cookie yields a usable refresh token; unreachable by
  `provider-gateway` and n8n; and capped by cookie size.
- **Managed secret store (AWS KMS / Secrets Manager / Vault).** Rejected for the
  submission window — reintroduces the cloud dependency ADR-005 is removing, and
  makes sign-in depend on a second service's availability. Revisit if the
  deployment target changes; `encryption_key_id` makes that migration tractable.
- **PostgreSQL `pgcrypto`.** Rejected: leaks key material into query logs and
  server-side statement views, and negates the "database holds only ciphertext"
  property.
- **Storing only a token *reference* and keeping token material in an external
  vault.** The schema's wording ("token material/**reference**") permits this,
  and it is strictly better if a vault exists — but with no vault selected it
  reduces to the alternative above.

## Consequences

- **`OAUTH_TOKEN_ENCRYPTION_KEY` is backup-critical.** Losing it makes every
  stored connection undecryptable, and every user must reconnect. It belongs in
  the same protected backup path as `N8N_ENCRYPTION_KEY`, and must be added to
  the VPS secret injection documented under `DEP-005`.
- **Key rotation is supported but not automated.** Prepending a key works
  immediately for new writes and keeps old rows readable; a background
  re-encryption job is not written yet. Until it exists, old keys cannot be
  retired.
- **`FLASK_SECRET_KEY` becomes operationally significant.** It protects the
  cookie holding `user_id` and the in-flight OAuth `state`. `app.py` still falls
  back to a random per-start key, which silently invalidates sessions on every
  restart; the app now warns at startup when Google sign-in is configured and
  the key is ephemeral.
- **A database compromise no longer yields usable provider credentials**, which
  is the property that makes `oauth_accounts` safe to expose to n8n's Postgres
  nodes on `melody-net` (ADR-005).
- **Nothing decrypts these tokens yet.** This slice stores them; §5.5 export is
  the first consumer. The decryption path is exercised today only by
  disconnect/revocation.
