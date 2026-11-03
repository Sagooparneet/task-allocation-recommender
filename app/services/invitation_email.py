"""Gmail invitation delivery. No credentials or invitation bodies are logged."""
from datetime import timedelta
from email.message import EmailMessage
import re
import base64
import threading
from urllib.parse import quote, urlsplit
from flask import current_app
from app.services.independent_workers import valid_email


class EmailConfigurationError(ValueError):
    pass


class EmailDeliveryError(Exception):
    pass


def email_settings(config=None):
    config = current_app.config if config is None else config
    sender = config.get('INTELLITASK_GMAIL_ADDRESS', '').strip().lower()
    credentials = current_app.extensions.get('intellitask_gmail_credentials')
    base = config.get('INTELLITASK_INVITATION_BASE_URL', '').strip().rstrip('/')
    if not valid_email(sender) or credentials is None or not getattr(credentials, 'refresh_token', None):
        raise EmailConfigurationError('Gmail invitation delivery has not been configured. Use manual sharing or configure the sender account.')
    try:
        parsed = urlsplit(base)
        port = parsed.port
    except ValueError:
        raise EmailConfigurationError('The invitation website address is invalid.') from None
    local = parsed.hostname in ('localhost', '127.0.0.1', '::1')
    if (not parsed.hostname or parsed.username is not None or parsed.password is not None
            or parsed.query or parsed.fragment or parsed.path not in ('', '/')
            or any(c.isspace() for c in base) or '\\' in base
            or parsed.scheme not in ('https', 'http')
            or (parsed.scheme == 'http' and not local)):
        raise EmailConfigurationError('Use an HTTPS website address, or localhost for testing on this computer.')
    return sender, credentials, base


def send_setup_email(recipient, name, token, expiry, settings):
    return _send_invitation_email(recipient, name, token, expiry, settings, 'worker')


def send_supervisor_setup_email(recipient, name, token, expiry, settings):
    return _send_invitation_email(recipient, name, token, expiry, settings, 'supervisor')


def _send_invitation_email(recipient, name, token, expiry, settings, role):
    sender, credentials, base = settings
    if not valid_email(recipient) or not re.fullmatch(r'[A-Za-z0-9_-]{43}', token):
        raise EmailConfigurationError('The registered recipient or invitation is invalid.')
    # Use only the explicitly configured origin, never a request Host header.
    link = base + '/auth/' + role + '-setup#' + token
    expiry_eat = (expiry + timedelta(hours=3)).strftime('%d %b %Y at %H:%M EAT')
    message = EmailMessage()
    message['Subject'] = 'Set up your IntelliTask ' + role + ' account'
    message['From'] = sender
    message['To'] = recipient
    introduction = ('Your administrator invited you to IntelliTask. ' if role == 'worker' else
                    'Your administrator invited you to IntelliTask as a supervisor. ')
    message.set_content(f"Hello {name},\n\n{introduction}"
        f"Choose your own password using this one-time link:\n\n{link}\n\n"
        f"Enter your registered email: {recipient}\n"
        f"This invitation expires on {expiry_eat}. A replacement invitation invalidates earlier links.\n\n"
        "If the link does not fill in your setup code, paste this code into the setup form:\n"
        f"{token}\n\nNever share your password or this invitation. "
        "If you were not expecting this invitation, contact the administrator.\n")
    if urlsplit(base).hostname in ('localhost','127.0.0.1','::1'):
        message.set_content(message.get_content() + '\nLocal test: open this link on the computer running IntelliTask on port 5001.\n')
    try:
        # Explicit mailbox ID must match the authorized sender account. The
        # origin is fixed and cannot be supplied by the request or email form.
        endpoint = 'https://gmail.googleapis.com/gmail/v1/users/' + quote(sender, safe='') + '/messages/send'
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode('ascii')
        # Serialize refresh/use of the in-memory credential object. Do not retry
        # a message POST after a timeout: Google may already have accepted it.
        with _send_lock:
            with _authorized_session(credentials) as transport:
                response = transport.post(endpoint, json={'raw': raw},
                    timeout=20, allow_redirects=False, max_allowed_time=40)
                if response.status_code != 200:
                    raise EmailDeliveryError('Email submission was not confirmed.')
                result = response.json()
                if not isinstance(result, dict) or not isinstance(result.get('id'), str) or not result['id']:
                    raise EmailDeliveryError('Email submission was not confirmed.')
    except Exception:
        # Provider exceptions may contain addresses, message data or tokens.
        raise EmailDeliveryError('Email submission was not confirmed.') from None


_send_lock = threading.Lock()


def _authorized_session(credentials):
    from google.auth.transport.requests import AuthorizedSession
    return AuthorizedSession(credentials, max_refresh_attempts=0, refresh_timeout=15)
