# Initial setup for independent workers — issue #56

The planned initial-setup flow is now implemented locally. An administrator issues a 24-hour, single-use invitation for a pending independent worker; that worker chooses their own password. Reissuing replaces the previous token. Only the SHA-256 hash of the high-entropy token is stored in the database. Administrators do not choose or see the password.

Migration `56d04a2b7c80`, following `56c03f1a6b70`, adds `worker_setup_invitations`. Its worker foreign key references independent registrations, not the entire directory. One current invitation stores its unique hash, issuer, issue/expiry times and consumption time. The migration preserves existing credentials, availability, history and source bindings.

Application checks enforce administrator permission, form tokens, pending-worker eligibility, expiration and atomic single-use redemption. Setup sets a hashed password and enables sign-in while leaving assignment availability off. It creates no dataset binding or ML score. This is not a password-reset route for existing workers or dataset accounts.

Delivery supports private manual sharing and Gmail API email, with registered recipients, a configured link origin, an email-reissue interval and truthful failure messages. The project owner confirmed actual email receipt, password setup and sign-in, then assignment, start, completion and updated totals for the independent worker. A delivered message is not an application email-verification flag; there is no separate OTP workflow in this feature.

Detailed implementation and operating instructions:

- [Password setup](WORKER_PASSWORD_SETUP.md)
- [Gmail authorization](GMAIL_LOCAL_AUTHORIZATION.md)
- [Gmail invitations](GMAIL_API_INVITATIONS.md)
- [Independent matching](INDEPENDENT_WORKER_MATCHING.md)

Hosted setup, public HTTPS links, PostgreSQL checks and hosted secret storage remain separate. Neon and Render were not changed.
