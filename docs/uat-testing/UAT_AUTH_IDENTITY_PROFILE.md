# UAT: Account Identity and Credential Management

## Purpose and Preconditions

Validate the deployed registration, identity, profile, email, and password
workflows with disposable accounts. Use a narrow iPhone 12 mini-class viewport
for mobile checks. Never record credentials or verification tokens in results.

## Registration and Login

- [ ] 1. Register with required first/last names and no phone.
- [ ] 2. Register with a valid optional phone.
- [ ] 3. Confirm missing or whitespace-only first name is rejected.
- [ ] 4. Confirm missing or whitespace-only last name is rejected.
- [ ] 5. Confirm malformed nonblank phone is rejected.
- [ ] 6. Complete the existing email-verification workflow.
- [ ] 7. Log in with the username.
- [ ] 8. Log out and log in with the account email.
- [ ] 9. Confirm supported email case/normalization behavior.
- [ ] 10. Confirm invalid identifiers and passwords produce the same generic failure.

## Account and Profile

- [ ] 11. Confirm Account displays Username, Name, Phone, then Email.
- [ ] 12. Update first name, last name, and phone successfully.
- [ ] 13. Submit a blank phone and confirm an existing phone is preserved.
- [ ] 14. Reject an invalid phone without changing either name or phone.
- [ ] 15. Confirm Personal Information, Email, and Password forms appear immediately.
- [ ] 16. Confirm no Change Email reveal button remains.
- [ ] 17. Confirm no form-specific Cancel buttons remain.
- [ ] 18. Use Back to account and confirm the authenticated session remains active.

## Email and Password

- [ ] 19. Complete the existing verified email-change workflow.
- [ ] 20. Reject a wrong current password without logging out.
- [ ] 21. Reject a weak new password without logging out.
- [ ] 22. Reject mismatched password confirmation without logging out.
- [ ] 23. Change the password with valid inputs.
- [ ] 24. Confirm success returns the user to Login with a sign-in-again message.
- [ ] 25. Confirm the old password no longer authenticates.
- [ ] 26. Confirm the new password authenticates.
- [ ] 27. Confirm an old refresh session cannot restore authentication.

## Mobile and Regression

- [ ] 28. Confirm there is no horizontal overflow at the narrow viewport.
- [ ] 29. Confirm Back to account remains fully visible.
- [ ] 30. Confirm all three forms and phone hint remain readable and usable.
- [ ] 31. Confirm registration verification still works.
- [ ] 32. Confirm forgot/reset-password still works.
- [ ] 33. Confirm logout and ordinary session restoration still work.
- [ ] 34. Confirm Django admin login still works through the production proxy.

Record the environment, build/commit, browser, viewport, PASS/FAIL state, and
non-sensitive notes for each run. Automated component and API coverage supports
these scenarios but does not replace deployed or real-layout acceptance.
