"""Tie each login session to the account's current password hash."""

import hashlib
import hmac

from flask import current_app


def session_id_for(account):
    key = current_app.secret_key
    if isinstance(key, str):
        key = key.encode('utf-8')
    message = f'{account.role}:{account.id}:{account.password_hash}'.encode('utf-8')
    proof = hmac.new(key, message, hashlib.sha256).hexdigest()
    return f'{account.role}:{account.id}:{proof}'


def session_id_matches(account, supplied):
    return hmac.compare_digest(session_id_for(account), supplied)
