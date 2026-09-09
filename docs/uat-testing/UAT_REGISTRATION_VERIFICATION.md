# UAT: Registration and Email Verification

## Purpose

This UAT validates the implemented human-facing registration, email
verification, login, account recovery, email change, session restoration, and
logout lifecycle in the local development environment.

## Preconditions

-   The `feature/auth-registration-verification` branch is checked out.
-   The local Compose stack is running and migrations are applied.
-   The readable console email backend is enabled locally.
-   Verified-email login enforcement is enabled for this test.
-   The frontend is available in a browser at <http://localhost:5173>.
-   Backend logs are available so verification URLs can be read.

## Test Data

Use fresh, disposable local-only identities. Do not use personal credentials.

-   Primary username: `uat_auth_01`
-   Primary email: `uat_auth_01@example.com`
-   Changed email: `uat_auth_01_changed@example.com`
-   Alternate identity for conflict checks: `uat_auth_02` /
    `uat_auth_02@example.com`
-   Password: choose a test-only password that satisfies the configured Django
    validators and is not similar to the username.

## Test Scenarios

### Scenario 1 — Logged-out initial page

**Steps**

1. Open <http://localhost:5173> in a logged-out browser session.
2. Observe the page without selecting an authentication control.

**Expected**

-   The catalog is visible.
-   `Login | Register` appears in the upper-right header.
-   The login/register panel is hidden.

**Actual**

- [ ] PASS
- [ ] FAIL

**Notes**

-

### Scenario 2 — Open and close the authentication panel

**Steps**

1. Select `Login | Register`.
2. Switch between Login and Register.
3. Produce harmless validation feedback, then select `Close`.
4. Reopen the authentication panel.

**Expected**

-   The panel opens in the content area and both modes work.
-   Closing returns focus to normal browsing.
-   Reopening does not restore stale feedback.

**Actual**

- [ ] PASS
- [ ] FAIL

**Notes**

-

### Scenario 3 — Registration validation

**Steps**

1. In Register mode, try missing or invalid input.
2. Try a username already reserved by a test account.
3. Try an email already reserved by a test account.
4. Try a weak password or one similar to the username.
5. Correct every field and submit again.

**Expected**

-   Browser validation handles required and malformed inputs where applicable.
-   Backend username, email, and password errors appear beside the correct field.
-   Multiple password messages can be shown together.
-   Django password validation is enforced.
-   A corrected submission clears prior field and global errors.

**Actual**

- [ ] PASS
- [ ] FAIL

**Notes**

-

### Scenario 4 — Successful registration

**Steps**

1. Register the fresh primary test identity with a valid password.
2. Observe the result and header.

**Expected**

-   The account is created.
-   `Registration succeeded. Check your email to verify the account.` appears.
-   The browser remains logged out.
-   Resend is presented only as the secondary
    `Didn't receive the email? Resend verification` action.
-   Selecting resend makes a one-click request for the normalized registration
    email without displaying an email input.
-   The generic response mentions eligibility and cooldown without claiming that
    a message was definitely sent.

**Actual**

- [ ] PASS
- [ ] FAIL

**Notes**

-

### Scenario 5 — Public resend recovery

**Steps**

1. In a fresh logged-out view, open `Login | Register` without registering.
2. Select `Need another verification email?`.
3. Enter an existing unverified test email and submit.
4. Select `Cancel`, then reopen the recovery form.
5. Repeat with an unknown or already-verified disposable address.

**Expected**

-   Public recovery is discoverable without registration or successful login.
-   The form requires an email because no account context is trusted yet.
-   Known, unknown, verified, and cooldown-limited addresses receive the same
    generic response.
-   Invalid email syntax receives normal field validation.
-   Cancel collapses the form and transient feedback does not reappear.

**Actual**

- [ ] PASS
- [ ] FAIL

**Notes**

-

### Scenario 6 — Verify from the local console email

**Steps**

1. Locate the verification message in the backend logs.
2. Copy the exact literal URL printed in the message without editing it.
3. Open the URL in the browser.
4. Observe the address bar after the verification request begins.

**Expected**

-   Verification succeeds and the verified email is displayed correctly.
-   The `uid` and `token` query data are removed from browser history and the
    visible URL after the page captures them.

**Actual**

- [ ] PASS
- [ ] FAIL

**Notes**

-

### Scenario 7 — Invalid or superseded verification link

**Steps**

1. Register a second fresh identity and preserve its initial verification URL.
2. After the configured resend cooldown, request a new verification message.
3. Open the older URL, then open the newest URL.

**Expected**

-   The superseded link fails safely as invalid or expired.
-   The invalid-link page provides resend recovery and a return path.
-   The newest token verifies the account successfully.

**Actual**

- [ ] PASS
- [ ] FAIL

**Notes**

-

### Scenario 8 — Login before verification

**Steps**

1. Register a fresh identity but do not verify it.
2. Attempt to log in with its correct credentials.

**Expected**

-   Login is rejected while verified-email enforcement is enabled.
-   No authenticated session is created.
-   The public resend recovery form is available without revealing whether an
    account exists.

**Actual**

- [ ] PASS
- [ ] FAIL

**Notes**

-

### Scenario 9 — Login after verification

**Steps**

1. Open the authentication panel.
2. Log in with the verified primary identity.

**Expected**

-   Login succeeds.
-   The authentication panel collapses.
-   `uat_auth_01` appears in the upper-right header.

**Actual**

- [ ] PASS
- [ ] FAIL

**Notes**

-

### Scenario 10 — Restore an authenticated session

**Steps**

1. While authenticated, refresh the browser page.
2. Observe the header and content during restoration.

**Expected**

-   The refresh-cookie session restores successfully.
-   The username returns to the header.
-   The login/register form does not flash unnecessarily.

**Actual**

- [ ] PASS
- [ ] FAIL

**Notes**

-

### Scenario 11 — Open the Account panel

**Steps**

1. Select the username in the header.
2. Review the Account panel.

**Expected**

-   The panel heading is `Account`.
-   It shows the username, current email, and `Account status: Verified`.
-   `Update account` and `Logout` are available inside the panel.
-   Logout is not displayed in the header.

**Actual**

- [ ] PASS
- [ ] FAIL

**Notes**

-

### Scenario 12 — Verified account resend visibility

**Steps**

1. Review the Account panel while the current email is verified.

**Expected**

-   `Resend verification email` is not shown.

**Actual**

- [ ] PASS
- [ ] FAIL

**Notes**

-

### Scenario 13 — Update account and change email

**Steps**

1. Log in and leave the page open for more than 10 minutes so the in-memory
   access token is stale while the 7-day refresh cookie remains valid.
2. Select `Update account`, then `Change email`.
3. Confirm Cancel and `Back to account` close their respective views cleanly.
4. Reopen the workflow and submit an invalid or already-reserved email.
5. Correct it to `uat_auth_01_changed@example.com` and submit.
6. In browser network tools, confirm the stale access request receives 401,
   one `POST /api/auth/refresh/` succeeds, and change-email is retried once.

**Expected**

-   Email controls are absent from the default Account summary.
-   Invalid changes display a clear error.
-   A corrected successful change removes the prior error and shows only success.
-   The expired access token is replaced silently from the still-valid HttpOnly
    refresh-cookie session; the action succeeds and the user remains logged in.
-   No raw JWT/token-library error is displayed.
-   The current email updates and account status immediately becomes
    `Not Verified`.

**Actual**

- [ ] PASS
- [ ] FAIL

**Notes**

-

### Scenario 14 — Resend for an authenticated unverified account

**Steps**

1. Open Account after changing the email.
2. Select `Resend verification email` immediately after the email change.
3. If cooldown feedback appears, wait the stated interval and select it again.
4. Inspect the destination of the new console email.

**Expected**

-   `Account status: Not Verified` and the resend action are visible.
-   No email input is requested.
-   The message targets only the account's current changed email.
-   The response truthfully reports either sent, cooldown, or delivery failure.
-   After the cooldown, success corresponds to a new console email and token.
-   Resending does not itself change verification state.

**Actual**

- [ ] PASS
- [ ] FAIL

**Notes**

-

### Scenario 15 — Reverify after changing email

**Steps**

1. Try a preserved verification URL issued for the old address.
2. Open the newest console verification URL for the changed address.
3. Return to the app, restore or log in, and open Account.

**Expected**

-   The old-address token fails safely.
-   The newest token for the changed address succeeds.
-   Account status returns to `Verified`.
-   The current changed email remains displayed.

**Actual**

- [ ] PASS
- [ ] FAIL

**Notes**

-

### Scenario 16 — Logout

**Steps**

1. Select `Logout` from the Account panel.
2. Refresh the browser.
3. Confirm an unauthenticated request to `/api/auth/me/` is rejected.

**Expected**

-   Authenticated account UI clears and the header returns to `Login | Register`.
-   Refresh does not restore the logged-out session.
-   Protected `/me` access is unavailable without a valid access token.

**Actual**

- [ ] PASS
- [ ] FAIL

**Notes**

-

### Scenario 17 — Wrong-password login

**Steps**

1. Attempt login with a valid-looking username and an incorrect password.
2. Repeat with an unknown username and the same incorrect password.

**Expected**

-   A concise generic credential error appears.
-   The response does not disclose whether the account exists.
-   No authenticated session is created.

**Actual**

- [ ] PASS
- [ ] FAIL

**Notes**

-

### Scenario 18 — UI state regression checks

**Steps**

1. Move between authentication, registration recovery, Account, and Update
   account views after producing both success and failure feedback.
2. Close and reopen each applicable panel.
3. Return to normal catalog browsing.

**Expected**

-   Success and error messages are never visible simultaneously.
-   Stale registration, email-change, and resend feedback does not reappear.
-   Normal catalog browsing is not dominated by authentication UI.

**Actual**

- [ ] PASS
- [ ] FAIL

**Notes**

-

### Scenario 19 — Session lifecycle refresh and expiry

**Steps**

1. Log in, leave the page open for more than 10 minutes, and perform an
   authenticated action such as opening/restoring Account, changing email, or
   resending verification.
2. Confirm the access request receives 401, refresh succeeds, and the original
   action succeeds on one retry without another login.
3. Log out (or otherwise invalidate/delete the refresh cookie), then repeat an
   authenticated action from a page that still holds a stale access token.

**Expected**

-   Authenticated session → access token expires → authenticated action → one
    silent refresh → one retry → action succeeds → user remains logged in.
-   Concurrent stale authenticated requests share one in-progress refresh and
    do not race refresh-token rotation.
-   Access + refresh unusable → in-memory authentication clears → logged-out UI
    appears → `Your session has expired. Please log in again.` is shown.
-   No raw SimpleJWT error is exposed and no request retries indefinitely.

**Actual**

- [ ] PASS
- [ ] FAIL

**Notes**

-

### Scenario 20 — Real SMTP verification delivery

**Preconditions**

-   Configure the SMTP backend and `SMTP_*` variables outside the repository.
-   Use a real test inbox and the deployment's approved verified sender.

**Steps**

1. Register a new account using the real test inbox.
2. Confirm the configured SMTP provider reports successful delivery and the
   message arrives in the inbox.
3. Confirm the visible sender is the expected Commerce Architect address.
4. Open the verification link from the delivered message.
5. Confirm verification succeeds, then log in with the registered credentials.

**Expected**

-   Registration sends through the configured provider-neutral SMTP mailer.
-   The message arrives from the expected Commerce Architect sender without
    exposing SMTP credentials in UI, application logs, or errors.
-   The delivered link verifies the account and the verified account can log in.

**Actual**

- [ ] PASS
- [ ] FAIL

**Notes**

-

### Scenario 21 — Duplicate normalized email registration

**Steps**

1. Register a user with a new email address.
2. Attempt registration with a different username and the same email using
   different letter casing or surrounding whitespace.

**Expected**

-   The second registration is rejected with a field-level email error.
-   No second `User` or `EmailVerification` account is created.

**Actual**

- [ ] PASS
- [ ] FAIL

**Notes**

-

## UAT Summary

-   Total scenarios: 21
-   Passed:
-   Failed:
-   Blocked:
-   Tester:
-   Date:
-   Branch: `feature/auth-registration-verification`
-   Commit:
-   Notes:

A PR for this feature should not be opened until all blocking UAT scenarios pass
or any accepted exception is explicitly documented.
