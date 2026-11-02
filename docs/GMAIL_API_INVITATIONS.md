# Gmail API worker invitations — issue 56

## What this stage installs

The administrator's existing initial-setup form can either create a link for
private sharing or submit an invitation through the Gmail HTTPS API. The sender
for this local installation is `sagooparneet@gmail.com`.

This supersedes the uninstalled stage-65 SMTP implementation. No Google app
password, SMTP connection, new database table, or migration is needed.

## Local startup

After completing `scripts/connect_gmail_sender.py` with the selected account:

1. Stop the current port-5001 website.
2. Install dependencies: `python -m pip install -r requirements.txt`.
3. Run `python scripts/run_5001_with_gmail_api.py`.
4. Open `http://127.0.0.1:5001` and sign in as the administrator.

The launcher decrypts the local Windows-user credential file into server memory.
It uses the original `run_netease_test.py` to select the existing port-5001 SQLite
database and instance directory. It does not alter environment variables, write
Google tokens into the database, or access Neon. It does not send on startup.
The ordinary launcher still supports manual invitation sharing without Gmail.

## One real invitation check

Use an independent worker whose registered email you control and whose account
still shows awaiting setup. Do not change a dataset worker's identity for this
test. If the previous test worker already chose a password, create another
independent worker with a different email address you control.

1. Open that worker's profile and the setup invitation form.
2. Select **Email to [registered address]**.
3. Confirm the worker and registered email are correct, then create the invitation.
4. A success message means Gmail returned a message ID; it does not prove inbox
   delivery. Check the recipient inbox and spam folder, and verify the From address.
5. Open the link in a private browser window **on this computer**, enter the
   registered email, and choose a password. Sign in as the worker.
6. Reusing the same invitation must fail. Existing dataset mappings and other
   worker accounts must remain unchanged.

Local email links point to `http://127.0.0.1:5001` and cannot open this website
from a phone or another computer. Sending to a real inbox does not make the
local website public.

## Delivery behavior

- Only authenticated administrators can issue invitations. The existing CSRF,
  confirmation, independent-worker, pending-setup, and disabled-account checks
  remain in place.
- Recipient comes from the worker record, not a posted email field. Email links
  use a configured website origin, never the incoming Host header.
- A single-use invitation hash is committed before contacting Gmail. Initial
  setup retains the existing 24-hour expiry and password/account safeguards.
- Email reissues require one minute since the last invitation issuance. A
  replacement invalidates the previous link. The guard runs under the worker
  transaction lock and does not require schema changes.
- The send endpoint includes the configured sender's mailbox ID, rather than
  accepting a user-selected endpoint. Google must authorize access to that
  mailbox. Only the `gmail.send` permission is used.
- The API POST is not automatically retried after uncertain failure. Provider
  errors are not displayed or logged. The form reports an unconfirmed submission
  and preserves the newly created link for manual sharing. Check the inbox before
  creating a replacement, since a timeout can occur after Google accepted mail.
- Sending does not enable login, consume the invitation, change the worker's
  password, make them available, or alter recommendations. Redeeming the setup
  invitation remains the step that enables the independent worker's account.

## Deployment remains separate

This stage enables local sending. The Windows DPAPI file cannot be copied to
Render for use there. Hosted credential storage, configured public invitation
origin, production OAuth consent/verification requirements, and actual hosted
delivery must be completed during deployment preparation. External OAuth apps
in Testing generally have a seven-day refresh-token lifetime for Gmail scopes;
rerun local authorization if Google requires it.

## Automated checks

`python -m pytest tests/test_worker_invitation_email.py tests/test_worker_password_setup.py -q`

These tests use simulated Gmail responses and disposable databases; they do not
send real mail. Coverage includes registered recipients, trusted link origins,
role restrictions, CSRF, database failure, token redemption, reissue throttling,
API rejection/timeouts, redacted errors, and manual fallback.

Google API references:
- https://developers.google.com/workspace/gmail/api/guides/sending
- https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/send

Before final issue-56 release, run the full application/ML and JavaScript suites
and record the manual delivery result in the README/checkpoint notes.
