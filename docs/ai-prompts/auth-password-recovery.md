# Implementation Assignment: Password Recovery

> **Status: design approved for implementation planning.** This document defines
> the next authentication slice. It does not describe behavior that is already
> implemented.

## Objective

Add a focused, independently testable password-recovery journey while preserving
the completed registration and session architecture:

```text
Forgot password?
→ submit account email
→ receive a generic response
→ open the delivered frontend recovery link
→ submit a validated new password and confirmation
→ consume the reset token
→ return to login
→ log in with the new password
```

Reset success must not automatically authenticate the user. Requiring a normal
login makes the credential boundary explicit and avoids issuing tokens from a
public recovery endpoint.

## Existing architecture to preserve

- Django's stock `User`; do not introduce a custom user migration.
- Accounts-owned verification and security lifecycle state.
- Provider-neutral Django `MAILERS` delivery through the existing `send_mail()`
  path. Resend SMTP remains a tested provider, not an application dependency.
- Ten-minute SimpleJWT access tokens held only in React memory.
- Rotating, blacklisted seven-day refresh tokens in an HttpOnly cookie.
- Startup session restoration and single-flight access refresh with one retry.
- The current header-driven login/account UX and API naming under `/api/auth/`.
- Case-insensitive normalized-email ownership in `EmailVerification`.

No third-party authentication package is justified for this slice.

## Eligibility and enumeration resistance

Recovery mail is eligible only when all of these are true:

- an active `User` owns the normalized address;
- `User.email`, `EmailVerification.normalized_email`, and the submitted
  normalized address match; and
- that current address is verified.

Unknown, inactive, unverified, stale, cooldown-limited, and accepted addresses
all receive the same HTTP 202 response and body after syntactically valid input:

```json
{
  "detail": "If an eligible account exists, password recovery instructions will be sent."
}
```

Malformed email syntax may return HTTP 400 with an `email` field error. No other
public response, timing-dependent branch where practical, or log entry may
disclose account existence, activity, or verification state.

Use two modest protections without adding CAPTCHA:

- a configurable per-account resend cooldown, initially 60 seconds, stored with
  recovery state for eligible accounts; and
- a DRF scoped request throttle, initially 5 requests per minute per client IP,
  returning ordinary HTTP 429 without account-specific information.

Mail-delivery failure must be logged without recipient, raw token, credentials,
or account-disclosing response detail. The public response remains generic.

## Reset token strategy

### Recommendation

Add one accounts-owned `PasswordRecoveryState` row per user rather than using
Django's `PasswordResetTokenGenerator` alone. Suggested fields are:

- UUID primary key used as the public recovery identifier;
- one-to-one `user` relationship;
- `normalized_email` captured at issuance;
- `token_digest` (64-character SHA-256/HMAC digest), never the raw token;
- `token_created_at`, `last_sent_at`, and nullable `consumed_at`;
- integer `session_generation`, defaulting to zero; and
- normal created/updated timestamps.

Issue at least 256 bits with `secrets.token_urlsafe(32)`. Derive the stored digest
with an HMAC or digest that includes the raw token plus stable, structured values
for user ID, current password hash, normalized email, and the server secret.
Validate with constant-time comparison under `select_for_update()`.

This design gives explicit replacement, audit, cooldown, and concurrency
semantics while storing no bearer secret. One row per user means issuing a new
token atomically overwrites the previous digest, immediately superseding every
older link.

### Comparison with `PasswordResetTokenGenerator`

Django's first-party generator is cryptographically sound and automatically
invalidates a token after password or relevant user-state changes. It is an
excellent default for simple password reset. Used alone, however, it is
stateless: issuing another message does not provide a clear one-outstanding-token
replacement record, per-account cooldown state, consumption audit, or session
generation. Adding separate state around it would approach the same complexity
as the small accounts-owned record while splitting lifecycle logic.

Therefore use the persisted random-token design for consistency with
`EmailVerification`. Reuse Django primitives for password validation and secure
comparison; do not reimplement password hashing.

### Settled lifecycle

- **Lifetime:** 30 minutes, configurable as
  `AUTH_PASSWORD_RECOVERY_TTL_SECONDS` and required to be positive.
- **Replacement:** each eligible request overwrites the active digest and issue
  timestamp; every previous link becomes invalid immediately.
- **Cooldown:** an eligible account receives at most one new message per
  configured 60-second interval. The public response never reveals cooldown.
- **Single use:** successful confirmation clears the digest, records
  `consumed_at`, changes the password, and increments `session_generation` in
  one transaction.
- **Expiry, reuse, or tampering:** return one generic `invalid_or_expired_token`
  category. Already-used links never change state again.
- **Email change:** `change_email()` explicitly clears recovery token state.
  Confirmation also rejects any mismatch among the bound normalized address,
  current `User.email`, and `EmailVerification.normalized_email`.
- **Password change:** including current-password changes outside recovery,
  invalidates a token because its digest is bound to the password hash. Such a
  change should also clear recovery state through the accounts-owned password
  change service when one is introduced.

## Email-link safety

Send a link such as:

```text
https://<frontend>/reset-password?uid=<recovery-uuid>&token=<raw-secret>
```

Opening the link performs no backend mutation. The React landing page captures
`uid` and `token` once, immediately removes the query string with
`history.replaceState()`, and retains the values only in component memory.
Only an explicit form submission sends the state-changing POST. Mail scanners
that follow the GET cannot consume the token.

Never place reset tokens or passwords in logs, analytics, error messages,
fixtures, local/session storage, or committed configuration. Apply the existing
referrer and same-origin assumptions; the reset page must not load unnecessary
third-party resources while sensitive state is in memory.

## Password validation and confirmation

The confirmation serializer accepts `uid`, `token`, `new_password`, and
`confirm_password`. It must:

1. reject mismatch with field-level confirmation feedback;
2. construct/use the intended user and call Django's configured
   `validate_password(new_password, user=user)`;
3. return useful `new_password` field messages from Django validators;
4. call `user.set_password()` only inside the successful atomic consume path;
   and
5. never echo or log either password or the token.

React should catch mismatch before submission for immediate usability, while the
backend independently enforces it as the authority. Do not create a separate
password policy for recovery.

## Session and JWT security after reset

The security goal is that an attacker holding an older session cannot retain
long-lived access after recovery.

On successful reset:

1. increment the user's accounts-owned `session_generation` atomically with the
   password change;
2. blacklist every current SimpleJWT `OutstandingToken` for that user as
   defense in depth;
3. delete any refresh cookie present on the confirmation response;
4. clear React's in-memory access/user state and return to the login panel; and
5. let already-issued access tokens expire naturally within their existing
   ten-minute maximum.

Blacklisting outstanding refresh tokens alone is not fully race-safe: a refresh
that rotates concurrently with the blacklist sweep could create a later token.
Make session generation authoritative by adding it as a claim when credential
login issues refresh/access tokens and validating it in the cookie refresh
serializer. A legacy token with no claim is generation zero, preserving existing
sessions until that account resets; after increment, every old or concurrently
rotated generation-zero refresh is rejected. Rotated refresh tokens retain the
claim. This requires small custom obtain/refresh serializers and tests, not a
new state-management or authentication package.

Immediate stateless access-token revocation would require checking generation on
every authenticated request or reducing lifetime. That extra database/security
policy is not required here: the ten-minute residual window is explicit, while
all long-lived refresh access is revoked coherently.

## Relationship to verified email

- Send recovery only to the current verified
  `EmailVerification.normalized_email`, never an arbitrary `User.email` value.
- Unverified accounts receive the generic public response but no reset email;
  they continue through verification/resend recovery.
- Password reset never verifies or unverifies an address.
- Email change clears outstanding recovery state before issuing reverification.
- Every recovery token is bound to the normalized current email and becomes
  invalid if that relationship changes.

These invariants keep proof of mailbox ownership in one place and prevent an old
address from recovering an account after an email change.

## Proposed API

Follow the existing verb-oriented auth URL conventions.

### `POST /api/auth/password-reset/request/`

- **Authentication:** `AllowAny`; ignore ambient authentication for response
  semantics.
- **Request:** `{ "email": "person@example.com" }`.
- **202:** always use the generic recovery detail for syntactically valid input,
  whether accepted, unknown, inactive, unverified, cooldown-limited, or mail
  delivery failed.
- **400:** field-level malformed-email errors only.
- **429:** generic scoped-throttle response with no account information.

### `POST /api/auth/password-reset/confirm/`

- **Authentication:** `AllowAny`.
- **Request:**

  ```json
  {
    "uid": "recovery-uuid",
    "token": "raw-secret",
    "new_password": "new value",
    "confirm_password": "new value"
  }
  ```

- **200:** `{ "code": "password_reset", "detail": "Password changed. Please log in." }`;
  clear any refresh cookie.
- **400 `password_mismatch`:** confirmation field feedback without consuming the
  token.
- **400 password validation:** Django validator messages under `new_password`;
  do not consume the token so the user can correct the form.
- **400 `invalid_or_expired_token`:** one safe response for malformed UID,
  tampered, expired, superseded, reused, email-invalidated, password-invalidated,
  and otherwise ineligible tokens.

Neither endpoint issues access tokens or refresh cookies.

## Frontend UX

Keep recovery secondary to normal login:

1. Add an unobtrusive `Forgot password?` action in the login panel.
2. Show a small recovery request view with one email field, Cancel, and the
   generic check-your-email result. Never vary that result by account state.
3. Route `/reset-password` to a focused page. Capture and remove query values
   before rendering the password form.
4. Collect new password and confirmation with accessible field errors. Catch a
   mismatch client-side; display backend Django validator feedback.
5. On success, clear all local authentication state, discard captured secrets,
   and show the login panel with `Password changed. Please log in.`
6. Ensure close/back/new submissions clear stale success and error feedback.

Do not redesign the header, account panel, registration, verification, catalog,
or unrelated authentication surfaces.

## Backend implementation outline

- Add `PasswordRecoveryState` and its migration/admin registration.
- Add positive TTL/cooldown settings and a scoped DRF throttle configuration.
- Add request/confirm serializers and accounts-owned transactional services for
  issue, send, validate, consume, and session revocation.
- Use `transaction.on_commit()` for sending, preserving a retryable state when
  delivery fails while keeping the public response generic.
- Extend `change_email()` to invalidate recovery state in the same transaction.
- Add generation claims and validation to token obtain/refresh serializers.
- Keep all response translation in views and lifecycle invariants in services.
- Add frontend API functions and the two minimal recovery UI states/pages.

## Test and future UAT contract

Create `docs/uat-testing/UAT_PASSWORD_RECOVERY.md` during implementation. It
must cover at least:

- known active verified account and unknown-address requests with
  indistinguishable public responses;
- inactive and unverified accounts with the same public response;
- malformed email and IP throttling;
- cooldown behavior and real provider-neutral email delivery;
- valid, expired, superseded, reused, and tampered tokens;
- mismatch feedback and every configured Django password validator;
- successful reset, old-password rejection, and new-password login;
- token invalidation after email or other password changes;
- blacklisting plus generation-based rejection of existing/rotated refresh
  sessions, with access expiry documented;
- absence of sensitive query data after frontend capture;
- stale UI feedback cleanup and secondary login-panel presentation; and
- final Railway/Resend delivery acceptance without committed credentials.

Automated tests should include transactional/concurrency cases for replacement,
single use, email change, password change, refresh rotation around reset, and
generic public responses.

## Scope exclusions

Keep out of this slice:

- MFA/TOTP, phone verification, OAuth/social login, and CAPTCHA;
- guest checkout or any commerce-domain work;
- general account-profile/header redesign;
- custom `User` migration;
- automatic login after reset; and
- unrelated password-policy expansion.

## Risks and implementation questions

- **Email timing:** asynchronous delivery is absent. Keep public bodies generic
  and avoid deliberate sleeps; infrastructure-level timing resistance can be
  revisited with a queue if measurement shows material leakage.
- **Throttle identity:** proxy-aware client IP handling must use only trusted
  forwarded headers in production.
- **Legacy JWT rollout:** test missing generation claims as generation zero and
  ensure the first recovery increment invalidates them without logging out every
  account at deployment.
- **Admin password changes:** route future first-party password changes through
  the accounts service. The password-bound digest invalidates reset links even
  when an external/admin change bypasses it, but session generation requires an
  explicit hook or service call for full refresh revocation.
- **Delivery failure:** retaining an outstanding token whose email failed is
  acceptable because the token is unknown; cooldown policy should allow a safe
  retry without exposing the failure.

No unresolved question changes the recommended public API or token model; the
implementation must settle proxy throttle configuration and admin-change session
revocation tests before acceptance.
