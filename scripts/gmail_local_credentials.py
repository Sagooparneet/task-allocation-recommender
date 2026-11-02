"""Windows-only, user-bound storage for the local Gmail sender connection.

This is not the Render credential store. Never copy this file's saved output
into the repository or deploy a Windows credential file to Render.
"""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import tempfile

SENDING_SCOPE = 'https://www.googleapis.com/auth/gmail.send'
MAGIC = b'INTELLITASK-GMAIL-DPAPI-1\n'


def _crypt(data, decrypt=False):
    if os.name != 'nt':
        raise ValueError('Local credential protection requires Windows.')

    class Blob(ctypes.Structure):
        _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]

    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    target = Blob()
    crypt32 = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    function = crypt32.CryptUnprotectData if decrypt else crypt32.CryptProtectData
    function.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p,
                         ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p,
                         wintypes.DWORD, ctypes.POINTER(Blob)]
    function.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    # UI_FORBIDDEN only: do NOT use LOCAL_MACHINE, which permits other users.
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise ValueError('Windows could not protect or unlock the Gmail connection.')
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        kernel32.LocalFree(target.data)


def credential_path(project):
    local = os.environ.get('LOCALAPPDATA')
    if not local or not Path(local).is_absolute():
        raise ValueError('Windows Local AppData is unavailable.')
    destination = (Path(local) / 'IntelliTask' / 'gmail' / 'sender.dpapi').resolve()
    if destination.is_relative_to(Path(project).resolve()):
        raise ValueError('Gmail credentials must stay outside the project.')
    return destination


def save_credentials(credentials, destination):
    """Encrypt and verify before atomically replacing a previous connection."""
    document = json.loads(credentials.to_json())
    if not document.get('refresh_token') or not document.get('token'):
        raise ValueError('Google did not return reusable sending authorization.')
    if document.get('token_uri') != 'https://oauth2.googleapis.com/token':
        raise ValueError('Unexpected token endpoint.')
    granted = credentials.granted_scopes
    scopes = granted if granted is not None else credentials.scopes
    if set(scopes or []) != {SENDING_SCOPE}:
        raise ValueError('Only Gmail sending permission is supported by this setup.')
    raw = json.dumps(document).encode('utf-8')
    encrypted = _crypt(raw)
    if _crypt(encrypted, decrypt=True) != raw:
        raise ValueError('Encrypted credential verification failed.')
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(MAGIC + encrypted)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def load_credentials(destination):
    """For the later local mail integration; never log the returned object."""
    from google.oauth2.credentials import Credentials
    data = Path(destination).read_bytes()
    if not data.startswith(MAGIC):
        raise ValueError('Unsupported local Gmail credential format.')
    document = json.loads(_crypt(data[len(MAGIC):], decrypt=True))
    if document.get('token_uri') != 'https://oauth2.googleapis.com/token':
        raise ValueError('Unexpected token endpoint.')
    if set(document.get('scopes', [])) != {SENDING_SCOPE}:
        raise ValueError('Unexpected Gmail permissions.')
    return Credentials.from_authorized_user_info(document, scopes=[SENDING_SCOPE])
