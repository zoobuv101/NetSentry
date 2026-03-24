"""
TP-Link Deco local API cryptographic utilities.

The Deco web admin uses an AES-CBC encrypted JSON payload within
standard HTTP responses, with the AES session key exchanged via RSA.
This module is isolated so it can be replaced if the Deco firmware
changes the encryption scheme.

References:
- ha-tplink-deco (amosyuen): Home Assistant component
- MrMarble/deco: Go implementation
"""

from __future__ import annotations

import base64
import os

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


def generate_aes_key() -> bytes:
    """Generate a random 16-byte AES key."""
    return os.urandom(16)


def generate_aes_iv() -> bytes:
    """Generate a random 16-byte AES IV."""
    return os.urandom(16)


def aes_encrypt(plaintext: bytes, key: bytes, iv: bytes) -> bytes:
    """
    Encrypt plaintext using AES-128-CBC with PKCS7 padding.

    Returns raw ciphertext bytes (not base64 encoded).
    """
    padder = padding.PKCS7(128).padder()
    padded = padder.update(plaintext) + padder.finalize()

    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    return encryptor.update(padded) + encryptor.finalize()


def aes_decrypt(ciphertext: bytes, key: bytes, iv: bytes) -> bytes:
    """
    Decrypt AES-128-CBC ciphertext with PKCS7 unpadding.

    Returns original plaintext bytes.
    """
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()

    unpadder = padding.PKCS7(128).unpadder()
    return unpadder.update(padded) + unpadder.finalize()


def rsa_encrypt(data: bytes, public_key: RSAPublicKey) -> bytes:
    """
    Encrypt data with an RSA public key using PKCS1v15 padding.

    Returns base64-encoded ciphertext (as bytes).
    The Deco expects the AES key to be RSA-encrypted and base64-encoded.
    """
    encrypted = public_key.encrypt(data, asym_padding.PKCS1v15())
    return base64.b64encode(encrypted)


def encode_payload(data: bytes, key: bytes, iv: bytes) -> str:
    """
    Encode a payload for the Deco API:
    1. AES-CBC encrypt the data
    2. Base64 encode the result
    Returns a base64 string.
    """
    encrypted = aes_encrypt(data, key, iv)
    return base64.b64encode(encrypted).decode()


def decode_payload(b64_data: str, key: bytes, iv: bytes) -> bytes:
    """
    Decode a Deco API response payload:
    1. Base64 decode
    2. AES-CBC decrypt
    Returns plaintext bytes.
    """
    ciphertext = base64.b64decode(b64_data)
    return aes_decrypt(ciphertext, key, iv)
