# Local Gmail sender authorization — issue 56

This stage authorizes sending through Google's Gmail API, using the Web
application OAuth client already registered in Google Cloud. It replaces the
earlier, uninstalled SMTP approach. This authorization helper does not send mail or import the Flask application.
Administrator email delivery is now implemented separately; see [Gmail API invitations](GMAIL_API_INVITATIONS.md).

## Setup on Windows

Install the recorded dependency versions with
`python -m pip install -r requirements-gmail.txt` if not already installed.

1. Keep the downloaded OAuth JSON outside the project.
2. Stop the port-5001 website with Ctrl+C in its running terminal.
3. Run `python scripts/connect_gmail_sender.py` in the project's virtual environment.
4. Paste the JSON file path. Choose `sagooparneet@gmail.com` in Google's account
   selector and approve Gmail sending. No mailbox-reading permission is requested.
5. Return to the terminal after the browser reports completion. Start the
   email-enabled site with `python scripts/run_5001_with_gmail_api.py`.
   The ordinary `python run_netease_test.py` launcher supports manual sharing only.

The temporary listener binds only 127.0.0.1:5001 and uses exactly
`http://localhost:5001/admin/email/oauth/callback`. It times out after ten minutes.
The local setup operator authorizes this connection; this standalone utility
does not use an administrator website session. Do not expose it on a public host.

## Storage and limitations

- Only the Gmail `gmail.send` scope is accepted. The selected account is guided
  by a login hint; sending-only access does **not** verify its email address.
  Confirm the account selected in Google. The project owner subsequently confirmed real invitation delivery and successful
  account setup. Sending permission itself still does not verify the account address.
- State validation, PKCE, one-use callbacks, a timeout, no callback request logs,
  and a redirect to a clean completion URL protect the authorization flow.
- Credentials (including the refresh token and client secret) are encrypted with
  Windows DPAPI for the current Windows user, saved as
  `%LOCALAPPDATA%\IntelliTask\gmail\sender.dpapi`, outside Git and OneDrive project
  folders. Encryption is verified before atomic replacement. A failed attempt
  retains any previous connection. The original downloaded JSON remains private
  and unchanged; DPAPI does not encrypt that separate download.
- DPAPI protects the saved file at rest; software running as this Windows user
  can decrypt it. Never share or commit credential files or browser callback URLs.
- The encrypted Windows file is **not** a Render deployment credential. Hosted
  secrets and the deployed callback will be configured separately, without
  copying this Windows file to Render.
- External Google OAuth apps in Testing generally receive refresh tokens that
  expire after seven days for Gmail scopes. Reauthorization may be needed.
  Production OAuth configuration remains a deployment task.
- Workers, dataset mappings, assignments, all databases, and Neon remain untouched.

## Verification

Run `python -m pytest tests/test_gmail_sender_authorization.py -q`.
Tests use fake OAuth responses and temporary files. The Windows encryption
roundtrip test uses real DPAPI with fake credentials. Tests send no mail and do
not access Google. A successful browser authorization is a separate manual check.

References:
- https://developers.google.com/identity/protocols/oauth2/web-server
- https://developers.google.com/identity/protocols/oauth2#expiration
- https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata
