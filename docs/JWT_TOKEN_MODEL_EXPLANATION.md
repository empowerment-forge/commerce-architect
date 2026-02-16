# JWT Token Model Explanation

## OutstandingToken Table

Every refresh token issued is stored in `OutstandingToken`. This
represents a valid session token unless blacklisted.

Fields include: - user - jti (unique token identifier) - expires_at -
created_at

## BlacklistedToken Table

When a refresh token is rotated or logout is called, the token is added
to `BlacklistedToken`.

The record remains in `OutstandingToken`, but is now invalid.

## Important Behavior

-   Access tokens are NOT stored in the database.
-   Only refresh tokens are persisted.
-   A user may have multiple OutstandingTokens (multiple devices).
-   A token in BlacklistedToken is immediately unusable.
