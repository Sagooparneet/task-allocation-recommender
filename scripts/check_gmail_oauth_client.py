"""Read-only check of a private Google OAuth web-client download."""
import json
from pathlib import Path

CALLBACK = 'http://localhost:5001/admin/email/oauth/callback'


def validate_client(document):
    if not isinstance(document, dict) or not isinstance(document.get('web'), dict):
        raise ValueError('This must be the JSON download for a Web application OAuth client.')
    client = document['web']
    client_id = client.get('client_id')
    secret = client.get('client_secret')
    if not isinstance(client_id, str) or not client_id.endswith('.apps.googleusercontent.com'):
        raise ValueError('The download does not contain a valid Google OAuth client ID.')
    if (not isinstance(secret, str) or len(secret.strip()) < 16
            or '*' in secret or '•' in secret or any(ch.isspace() for ch in secret)):
        raise ValueError('The download has no usable client secret. Download the newly generated secret while its creation dialog is open.')
    redirects = client.get('redirect_uris', [])
    if not isinstance(redirects, list) or CALLBACK not in redirects:
        raise ValueError('The download is missing the required localhost callback. Check the redirect URI in Google Cloud.')
    if client.get('token_uri') != 'https://oauth2.googleapis.com/token':
        raise ValueError('The download has an unexpected Google token endpoint.')
    if client.get('auth_uri') not in ('https://accounts.google.com/o/oauth2/auth', 'https://accounts.google.com/o/oauth2/v2/auth'):
        raise ValueError('The download has an unexpected Google authorization endpoint.')


def main():
    print('Read-only check: no credentials will be displayed or saved, and no network requests will be made.')
    entered = input('Paste the full path of the downloaded JSON file: ').strip().strip('"')
    if not entered:
        raise SystemExit('No file selected.')
    project = Path(__file__).resolve().parents[1]
    path = Path(entered).expanduser().resolve()
    if path.is_relative_to(project):
        raise SystemExit('Keep the credentials outside your project folder, then run this check again.')
    try:
        document = json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, UnicodeError, ValueError):
        raise SystemExit('Could not read a JSON file at that path. Use Copy as path on the downloaded file.') from None
    try:
        validate_client(document)
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    print('Web application OAuth client: PASS')
    print('Client ID and private secret present: PASS')
    print('Local callback matches: PASS')
    print('Google authorization endpoints: PASS')
    print('Credential file outside the project: PASS')
    print('Finished. No files, accounts or database records were changed.')
    print('This checks the file structure only; Google authorization will be tested next.')


if __name__ == '__main__':
    main()
