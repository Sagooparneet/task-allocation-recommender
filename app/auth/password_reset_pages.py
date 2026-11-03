"""Public password-reset pages with private responses and generic request feedback."""

import secrets

from flask import abort, flash, redirect, render_template, request, session, url_for
from flask_login import current_user

from app.services.independent_workers import valid_email
from app.services.password_reset import INVALID_LINK, ResetUnavailable, redeem_reset, request_reset
from app.services.worker_setup import private_response


def _form_token():
    session.setdefault('password_reset_public_csrf', secrets.token_urlsafe(32))
    return session['password_reset_public_csrf']


def _check_form_token():
    expected = _form_token()
    supplied = request.form.get('csrf_token', '')
    if not secrets.compare_digest(expected.encode(), supplied.encode()):
        abort(400, description='This form expired. Reload the page and try again.')


def forgot_password_page():
    if current_user.is_authenticated:
        return private_response(redirect(url_for('auth.login')))
    errors = {}
    if request.method == 'POST':
        _check_form_token()
        email = request.form.get('email', '').strip().lower()
        if not valid_email(email):
            errors['email'] = 'Enter a valid email address.'
        else:
            request_reset(email, request.remote_addr)
            return private_response(redirect(url_for('auth.forgot_password_sent')))
    body = render_template('auth/forgot_password.html', errors=errors, csrf_token=_form_token())
    return private_response(body, 422 if errors else 200)


def forgot_password_sent_page():
    return private_response(render_template('auth/forgot_password_sent.html'))


def reset_password_page():
    if current_user.is_authenticated:
        return private_response(redirect(url_for('auth.login')))
    errors = {}
    if request.method == 'POST':
        _check_form_token()
        token = request.form.get('reset_token', '')
        password = request.form.get('password', '')
        confirmation = request.form.get('password_confirm', '')
        if not 12 <= len(password) <= 128 or not password.strip():
            errors['password'] = 'Choose a password of 12 to 128 characters.'
        if password != confirmation:
            errors['password_confirm'] = 'Enter the same password again.'
        if not token:
            errors['reset_token'] = INVALID_LINK
        if not errors:
            try:
                redeem_reset(token, password)
            except ResetUnavailable as exc:
                errors['reset_token'] = str(exc)
            else:
                session.clear()
                flash('Your password has been changed. Sign in with your new password.', 'success')
                return private_response(redirect(url_for('auth.login')))
    body = render_template('auth/reset_password.html', errors=errors, csrf_token=_form_token())
    return private_response(body, 422 if errors else 200)
