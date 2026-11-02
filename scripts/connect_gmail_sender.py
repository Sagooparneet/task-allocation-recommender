"""Authorize the local Gmail sender without importing the application/database.

Stop the port-5001 website first. This temporary, loopback-only callback listener
uses the existing Google Web application client and shuts down after setup.
"""
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import secrets
import time
from urllib.parse import parse_qs, urlsplit
import webbrowser

from google_auth_oauthlib.flow import Flow
from check_gmail_oauth_client import CALLBACK, validate_client
from gmail_local_credentials import SENDING_SCOPE, credential_path, save_credentials

SENDER = 'sagooparneet@gmail.com'


class SetupError(ValueError):
    pass


class AuthorizationAttempt:
    def __init__(self, flow, state, destination, saver=save_credentials):
        self.flow = flow
        self.state = state
        self.destination = destination
        self.saver = saver
        self.deadline = time.monotonic() + 600
        self.used = False
        self.success = False
        self.message = ''

    def complete(self, query):
        if self.used or time.monotonic() >= self.deadline:
            raise SetupError('This setup attempt has expired or has already been used.')
        states = query.get('state', [])
        if (len(states) != 1 or not isinstance(states[0], str)
                or not secrets.compare_digest(states[0].encode(), self.state.encode())):
            raise SetupError('Invalid authorization state. Return to the original Google tab.')
        self.used = True
        if 'error' in query:
            self.message = 'Google authorization was declined or could not be completed. Run setup again.'
            return
        codes = query.get('code', [])
        if len(codes) != 1 or not codes[0] or len(codes[0]) > 4096:
            self.message = 'Google did not return a usable authorization code. Run setup again.'
            return
        try:
            # State was explicitly checked above; the same Flow retains PKCE.
            # The token endpoint is HTTPS. No insecure OAuth transport override.
            self.flow.fetch_token(code=codes[0], timeout=30, allow_redirects=False)
            credentials = self.flow.credentials
            if not credentials.valid:
                raise ValueError('Invalid credentials')
            self.saver(credentials, self.destination)
        except Exception:
            # OAuth/network exceptions can contain codes/tokens/client secrets.
            self.message = ('Authorization could not be saved. Check your connection, approve sending '
                            'permission, and run setup again. Any previous saved connection is retained.')
            return
        self.success = True
        self.message = 'Gmail sending authorization saved. No email was sent. Return to your terminal.'


def handler_for(attempt, authorization_url, start_key):
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(5)

        def log_message(self, *args):
            pass  # Never log OAuth callback query strings.

        def reply(self, status, message='', location=None):
            self.send_response(status)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'none'; frame-ancestors 'none'")
            self.send_header('X-Content-Type-Options', 'nosniff')
            if location:
                self.send_header('Location', location)
            self.end_headers()
            self.wfile.write(message.encode('utf-8'))

        def do_GET(self):
            if self.headers.get('Host') != 'localhost:5001':
                self.reply(400, 'Use the localhost address printed in your terminal.')
                return
            url = urlsplit(self.path)
            if url.path == '/start/' + start_key and not attempt.used:
                self.reply(302, location=authorization_url)
            elif url.path == '/admin/email/oauth/callback':
                try:
                    attempt.complete(parse_qs(url.query, keep_blank_values=True, max_num_fields=20))
                except ValueError:
                    self.reply(400, 'Invalid or expired setup request. Return to the original Google tab.')
                    return
                # Clear the code from the address bar before showing completion.
                self.reply(303, location='/gmail-setup-complete')
            elif url.path == '/gmail-setup-complete' and attempt.used:
                self.reply(200 if attempt.success else 400, attempt.message)
                self.server.finished = True
            else:
                self.reply(404, 'Not found.')
    return Handler


def main():
    project = Path(__file__).resolve().parents[1]
    print('Local Gmail setup. No emails will be sent and no databases will be opened.')
    print('Stop the website on port 5001 first. In Google, choose ' + SENDER + '.')
    entered = input('Paste the full path of the downloaded OAuth JSON file: ').strip().strip('"')
    if not entered:
        raise SystemExit('No file selected.')
    try:
        client_path = Path(entered).expanduser().resolve()
        if client_path.is_relative_to(project):
            raise ValueError('Keep the OAuth JSON outside the project.')
        document = json.loads(client_path.read_text(encoding='utf-8-sig'))
        validate_client(document)
        destination = credential_path(project)
    except (OSError, ValueError, UnicodeError):
        raise SystemExit('Could not validate the private client file or local storage. Run the read-only client check again.') from None
    flow = Flow.from_client_config(document, scopes=[SENDING_SCOPE], redirect_uri=CALLBACK,
                                   code_verifier=secrets.token_urlsafe(64))
    authorization_url, state = flow.authorization_url(
        access_type='offline', prompt='consent select_account',
        login_hint=SENDER, include_granted_scopes='false')
    attempt = AuthorizationAttempt(flow, state, destination)
    start_key = secrets.token_urlsafe(24)
    try:
        server = HTTPServer(('127.0.0.1', 5001), handler_for(attempt, authorization_url, start_key))
    except OSError:
        raise SystemExit('Port 5001 is unavailable. Stop the website with Ctrl+C, then run this setup again.') from None
    server.timeout = 0.5
    server.finished = False
    start_url = 'http://localhost:5001/start/' + start_key
    print('Opening Google authorization. If no browser opens, visit this local address:')
    print(start_url)
    print('Approve sending email only. This setup expires in 10 minutes.')
    try:
        try:
            webbrowser.open(start_url)
        except webbrowser.Error:
            pass
        while not server.finished and time.monotonic() < attempt.deadline:
            server.handle_request()
    except KeyboardInterrupt:
        print('Setup stopped.')
    finally:
        server.server_close()
    if not attempt.success:
        raise SystemExit(attempt.message or 'Authorization was not completed. Run setup again when ready.')
    print('Google authorization and sending scope: PASS')
    print('Encrypted Windows-user credential storage: PASS')
    print('Saved outside the project: ' + str(destination))
    print('No emails sent. Local databases and Neon were not accessed.')
    print('Sending-only permission does not verify the selected account email; confirm you chose ' + SENDER + '.')
    print('Restart your normal website. Invitation delivery will be connected in the next step.')


if __name__ == '__main__':
    main()
