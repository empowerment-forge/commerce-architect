# UAT: Password Recovery

## Purpose and setup

Validate password recovery end to end without exposing account membership or
leaving old long-lived sessions usable. Use disposable accounts and inboxes.
For real delivery, configure provider-neutral SMTP outside the repository; the
tested example is Resend SMTP.

Record each scenario as `PASS`, `FAIL`, or `BLOCKED`, with evidence in Notes.

## Scenario 1 — Logged-out entry and cancellation

**Steps**

1. Open `Login | Register` while logged out.
2. Select `Forgot password?`, then `Back to login`.

**Expected**

- `Forgot password?` and `Need another verification email?` are visually
  distinct secondary actions with spacing and a subtle divider.
- Recovery remains a secondary login action with one email field.
- Back returns to a clean Login view without stale feedback.
- A normal logged-out visit to `/` keeps the authentication panel hidden until
  `Login | Register` is selected.

**Result:** [ ] PASS [ ] FAIL [ ] BLOCKED

**Notes:**

-

## Scenario 2 — Indistinguishable public requests

**Steps**

1. Request recovery separately for a known verified account, unknown address,
   inactive account, and unverified account.
2. Compare status codes, response text, and visible UI.

**Expected**

- Every syntactically valid request returns HTTP 202 and: `If an eligible
  account exists, password recovery instructions will be sent.`
- Only the active account with a current verified normalized email receives mail.

**Result:** [ ] PASS [ ] FAIL [ ] BLOCKED

**Notes:**

-

## Scenario 3 — Validation and throttling

**Steps**

1. Submit malformed email syntax.
2. Submit six syntactically valid requests within one minute from one client.

**Expected**

- Malformed syntax has a field-level email error.
- The scoped policy permits at most five requests/minute/client identity and
  then returns HTTP 429 without disclosing account state.
- Local identity uses the direct peer; Railway trusts one platform proxy hop
  only when forwarded-proto trust is explicitly enabled.

**Result:** [ ] PASS [ ] FAIL [ ] BLOCKED

**Notes:**

-

## Scenario 4 — Cooldown, reissue, and delivery failure

**Steps**

1. Request twice for one eligible account inside 60 seconds.
2. After cooldown, request again and retain both links.
3. In a controlled environment, simulate one mail-delivery failure and retry.

**Expected**

- Cooldown responses remain generic and only one message is sent during it.
- The newest issued token supersedes the older token.
- Failed delivery clears its reserved token/cooldown, allowing immediate retry,
  while the public response remains unchanged.

**Result:** [ ] PASS [ ] FAIL [ ] BLOCKED

**Notes:**

-

## Scenario 5 — Real SMTP delivery and URL safety

**Steps**

1. Request recovery for a real verified test inbox using configured SMTP.
2. Open the delivered `/reset-password?uid=...&token=...` link.
3. Inspect the address bar before entering a password.

**Expected**

- Mail arrives from the expected Commerce Architect sender through the
  configured provider-neutral mailer.
- The frontend captures the credentials and immediately replaces the URL with
  `/reset-password`; no token remains visible or in browser history.
- Merely following the email GET does not consume the token.

**Result:** [ ] PASS [ ] FAIL [ ] BLOCKED

**Notes:**

-

## Scenario 6 — Invalid token categories

**Steps**

1. Exercise expired, superseded, tampered, malformed, and already-used links.

**Expected**

- Each is rejected with the same safe invalid-or-expired message.
- No password or account state changes and no internal token detail appears.

**Result:** [ ] PASS [ ] FAIL [ ] BLOCKED

**Notes:**

-

## Scenario 7 — Password feedback without consumption

**Steps**

1. Submit mismatched password and confirmation values.
2. Correct the mismatch but submit a common, weak, or username-similar password.
3. Correct the password using the same reset link.

**Expected**

- Mismatch appears under confirmation before submission where possible.
- Django validator feedback appears under the new-password field.
- Neither error consumes the token; the corrected submission can succeed.

**Result:** [ ] PASS [ ] FAIL [ ] BLOCKED

**Notes:**

-

## Scenario 8 — Successful reset and login boundary

**Steps**

1. Complete a valid reset.
2. Observe the resulting UI and authentication state.
3. Try login with the old password, then the new password.

**Expected**

- Success says `Password changed. Please log in.` and returns/offers Login.
- `Return to login` opens the existing Commerce Architect Login panel directly,
  with Login selected and its form immediately ready; it does not land on a
  hidden-panel home state.
- No automatic login occurs and local authentication state is empty.
- Old password fails; new password succeeds.

**Result:** [ ] PASS [ ] FAIL [ ] BLOCKED

**Notes:**

-

## Scenario 9 — Email and password-state invalidation

**Steps**

1. Issue a recovery link, then change and reverify the account email before use.
2. Issue another recovery link, then change the password through a controlled
   external/admin path before use.

**Expected**

- Both old links are rejected safely.
- Recovery never changes verification status or targets a prior address.
- External password change invalidates the password-bound recovery digest.

**Result:** [ ] PASS [ ] FAIL [ ] BLOCKED

**Notes:**

-

## Scenario 10 — Existing refresh-session revocation

**Steps**

1. Log in on a second browser and preserve its refresh-cookie session.
2. Reset the password from the recovery browser.
3. Let the second browser attempt refresh/session restoration.

**Expected**

- Reset increments `AccountSecurityState.session_generation`, blacklists
  outstanding refresh tokens, and clears any recovery-browser refresh cookie.
- The older refresh session is rejected and login is required.

**Result:** [ ] PASS [ ] FAIL [ ] BLOCKED

**Notes:**

-

## Scenario 11 — Concurrent rotation and generation enforcement

**Steps**

1. Arrange an old generation-zero refresh at the same time as a successful reset.
2. If rotation completes, attempt to use the resulting rotated refresh token.

**Expected**

- Rotated tokens retain their generation claim.
- Every generation-zero refresh is rejected after the account increments to one,
  including a token created around the blacklist sweep.

**Result:** [ ] PASS [ ] FAIL [ ] BLOCKED

**Notes:**

-

## Scenario 12 — Access-token residual window

**Steps**

1. Preserve an access JWT before resetting the password.
2. Observe it before and after its existing ten-minute expiry.

**Expected**

- The stateless access token may remain usable only for its existing maximum
  lifetime; no database generation lookup was added to every API request.
- It cannot obtain long-lived continuation because refresh generation changed.

**Result:** [ ] PASS [ ] FAIL [ ] BLOCKED

**Notes:**

-

## Scenario 13 — UI regression and deployed acceptance

**Steps**

1. Produce request, mismatch, validator, invalid-link, and success feedback;
   navigate away/back and retry each relevant form.
2. Repeat the complete known-account flow on Railway with real Resend delivery.

**Expected**

- Success/error feedback clears between submissions and transitions.
- Passwords/tokens are never stored in localStorage/sessionStorage or displayed.
- Railway request → delivered email → safe link → reset → new-password login
  succeeds without provider-specific application code.

**Result:** [ ] PASS [ ] FAIL [ ] BLOCKED

**Notes:**

-

## UAT Summary

- Total scenarios: 13
- Passed:
- Failed:
- Blocked:
- Tester:
- Date:
- Branch: `feature/auth-password-recovery`
- Commit:
- Notes:
