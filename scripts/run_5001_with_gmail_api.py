"""Run the existing local installation with its encrypted Gmail authorization."""
from pathlib import Path
import runpy
import sys

from gmail_local_credentials import credential_path, load_credentials

SENDER = 'sagooparneet@gmail.com'


def main():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    try:
        credentials = load_credentials(credential_path(root))
        if not credentials.refresh_token:
            raise ValueError('Missing refresh token')
    except Exception:
        raise SystemExit('Could not unlock Gmail authorization. Run scripts/connect_gmail_sender.py as the same Windows user, then try again.') from None
    # Reuse the existing launcher, including its exact SQLite URL and instance
    # directory. Import mode prevents it from starting a second Flask server.
    namespace = runpy.run_path(str(root / 'run_netease_test.py'), run_name='gmail_local_app')
    app = namespace['app']
    app.config.update(INTELLITASK_GMAIL_ADDRESS=SENDER,
                      INTELLITASK_INVITATION_BASE_URL='http://127.0.0.1:5001')
    app.extensions['intellitask_gmail_credentials'] = credentials
    print('Starting the existing port-5001 website with Gmail email delivery.')
    print('Configured sender: ' + SENDER)
    print('Invitations and first-time verification codes are sent only when requested in the website.')
    print('Local invitation links must be opened on this computer. Neon is unchanged.')
    try:
        app.run(host='127.0.0.1', port=5001, debug=False, use_reloader=False)
    finally:
        app.extensions.pop('intellitask_gmail_credentials', None)


if __name__ == '__main__':
    main()
