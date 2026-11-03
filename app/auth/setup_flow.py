"""First-time account setup with email verification for invited accounts."""

import secrets

from flask import abort, flash, redirect, render_template, request, session, url_for
from flask_login import current_user
from sqlalchemy.exc import SQLAlchemyError

from app.services.independent_workers import valid_email
from app.services.invitation_email import EmailConfigurationError, EmailDeliveryError
from app.services.setup_email_codes import (
    INVALID_SETUP, VerificationUnavailable, request_verification_code,
    check_verification_code,
)
from app.services.worker_setup import private_response
from app.services import worker_setup as worker_service
from app.services import supervisor_setup as supervisor_service


def first_time_setup(role):
    if role not in ('worker', 'supervisor'):
        raise ValueError('Unsupported account role.')
    template = f'auth/{role}_setup.html'
    endpoint = f'auth.{role}_setup'
    csrf_key = f'{role}_setup_public_csrf'
    if current_user.is_authenticated:
        body = render_template(template, signed_in=True, errors={}, email='', csrf_token='', stage='request')
        return private_response(body, 403 if request.method == 'POST' else 200)

    session.setdefault(csrf_key, secrets.token_urlsafe(32))
    errors = {}
    email = session.get(f'{role}_setup_email', '')
    stage = 'verify' if request.args.get('step') == 'verify' else 'request'
    if request.method == 'POST':
        supplied = request.form.get('csrf_token', '')
        if not secrets.compare_digest(session[csrf_key].encode(), supplied.encode()):
            abort(400, description='This form expired. Reload the setup page and try again.')
        token = request.form.get('setup_token', '')
        email = request.form.get('email', '').strip().lower()
        action = request.form.get('action', '')
        stage = 'verify' if action == 'complete' else 'request'
        if not valid_email(email):
            errors['email'] = 'Enter the email address your administrator registered.'
        if not token:
            errors['setup_token'] = 'Open your invitation link or paste your setup code.'
        if action == 'send_code':
            if not errors:
                try:
                    request_verification_code(role, token, email)
                except (VerificationUnavailable, worker_service.SetupUnavailable,
                        supervisor_service.SetupUnavailable) as exc:
                    errors['setup_token'] = str(exc)
                except (EmailConfigurationError, EmailDeliveryError):
                    errors['__all__'] = (
                        'The verification email could not be confirmed. Check your inbox, '
                        'then wait one minute before requesting another code.'
                    )
                except SQLAlchemyError:
                    errors['__all__'] = 'Setup could not continue. Try again or contact your administrator.'
                else:
                    session[f'{role}_setup_email'] = email
                    flash('A six-digit code was sent to your registered email. It expires in 10 minutes.', 'info')
                    # The fragment is not sent to the server on GET. The setup
                    # script fills its field and removes it from browser history.
                    return private_response(redirect(url_for(endpoint, step='verify') + '#' + token))
        elif action == 'complete':
            code = request.form.get('verification_code', '').strip()
            password = request.form.get('password', '')
            confirmation = request.form.get('password_confirm', '')
            if not code.isascii() or not code.isdecimal() or len(code) != 6:
                errors['verification_code'] = 'Enter the six-digit code sent to your email.'
            if not 12 <= len(password) <= 128 or not password.strip():
                errors['password'] = 'Choose a password of 12 to 128 characters.'
            if password != confirmation:
                errors['password_confirm'] = 'Enter the same password again.'
            if not errors:
                service = worker_service if role == 'worker' else supervisor_service
                try:
                    check_verification_code(role, token, email, code)
                    service.redeem_invitation(token, email, password)
                except (VerificationUnavailable, worker_service.SetupUnavailable,
                        supervisor_service.SetupUnavailable) as exc:
                    if str(exc) == INVALID_SETUP or str(exc) == service.INVALID_INVITATION:
                        errors['setup_token'] = INVALID_SETUP
                    else:
                        errors['verification_code'] = str(exc)
                except SQLAlchemyError:
                    errors['__all__'] = 'Setup could not be completed. Try again or contact your administrator.'
                else:
                    session.clear()
                    flash('Your email is verified and your password is set. Sign in to continue.', 'success')
                    return private_response(redirect(url_for('auth.login')))
        else:
            errors['__all__'] = 'Choose a setup action and try again.'

    # Passwords, verification codes and invitation tokens are never rendered
    # back into HTML or stored in Flask's browser session cookie.
    body = render_template(template, signed_in=False, errors=errors, email=email,
                           csrf_token=session[csrf_key], stage=stage)
    return private_response(body, 422 if errors else 200)
