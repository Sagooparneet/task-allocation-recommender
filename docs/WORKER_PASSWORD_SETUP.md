# Initial password setup for new workers

Administrators can create a setup invitation from a pending independent worker profile. The invitation is shown once and must be shared privately with that worker. No email is sent automatically and this does not verify ownership of the email address.

The link expires after 24 hours. Creating a replacement invalidates the previous link. Only a SHA-256 hash of the random 256-bit secret is stored. The link carries the secret in its fragment, which the browser removes after filling the form. It is submitted in the POST body, not a query string. Invitation pages use no-store and no-referrer headers.

The worker opens the link while signed out, enters the registered email and chooses a password of 12 to 128 characters. Passwords are hashed. CSRF checks protect both forms. Redemption and password creation commit together; conditional updates prevent reuse and simultaneous redemption. Password setup enables login but leaves availability off for administrator review.

Existing accounts and dataset identities cannot use this flow to reset credentials. Worker source mappings, services, assignments and recommendation scores are unchanged. New workers still need the separate service-matching assignment workflow; this feature does not invent a model score.

## Local check

Use port 5001 and an administrator-added worker marked awaiting account setup. Create an invitation, open it in a private window on the same computer, set a password, and sign in normally. Confirm availability remains off. Reusing the link must fail. A localhost link does not work on a different device.

## Hosting

Use HTTPS for hosted invitations and password submission. This stage does not deploy code or change Neon. Automated delivery, email verification, password recovery and account self-service are separate work.

## Validation

Python tests cover access controls, expiry, replacement, replay, validation, transaction rollback, concurrent redemption and identity preservation. JavaScript tests cover fragment handling and same-origin link construction. PostgreSQL concurrency and browser presentation require separate validation before hosted rollout.
