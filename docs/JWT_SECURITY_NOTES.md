# JWT Security Notes

## Token Types

Access Token: - Short-lived (10 minutes) - Sent via Authorization
header - Not stored server-side

Refresh Token: - Long-lived (7 days) - Stored in HttpOnly cookie -
Rotated and blacklisted after use

## Security Guarantees

-   Refresh token theft window minimized via rotation.
-   Blacklisted tokens cannot be reused.
-   HttpOnly prevents JavaScript access to refresh token.
-   SameSite=Strict reduces CSRF risk.
-   Secure flag ensures HTTPS-only transmission.

## Logout Semantics

Logout blacklists the refresh token and clears the cookie. The session
is effectively terminated for that token.
