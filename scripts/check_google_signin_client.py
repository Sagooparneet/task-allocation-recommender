"""Check a private Google sign-in client file without printing credentials."""

import json
from pathlib import Path


REDIRECT = 'http://127.0.0.1:5001/auth/google/callback'


def main():
    root = Path(__file__).resolve().parents[1]
    raw = input('Paste the full path of the Google sign-in OAuth JSON file: ').strip().strip('"')
    path = Path(raw).expanduser().resolve()
    if path.is_relative_to(root):
        raise SystemExit('Keep the OAuth JSON outside the project folder.')
    try:
        client = json.loads(path.read_text(encoding='utf-8'))['web']
        valid = (bool(client.get('client_id')) and bool(client.get('client_secret'))
                 and REDIRECT in client.get('redirect_uris', [])
                 and client.get('auth_uri') in (
                     'https://accounts.google.com/o/oauth2/auth',
                     'https://accounts.google.com/o/oauth2/v2/auth',
                 )
                 and client.get('token_uri') == 'https://oauth2.googleapis.com/token')
    except (OSError, ValueError, KeyError, TypeError):
        valid = False
    if not valid:
        raise SystemExit('Google sign-in client check failed. Verify the Web application client and redirect URI.')
    print('Separate Google Web sign-in client: PASS')
    print('Exact local callback URI: PASS')
    print('Private client file outside project: PASS')
    print('No credentials were displayed or saved. No accounts or databases were accessed.')


if __name__ == '__main__':
    main()
