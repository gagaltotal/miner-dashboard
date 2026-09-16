"""
Optional self-signed TLS, generated on first run when `MINER_DASH_ENABLE_TLS`
is set. Plain HTTP is the default for the easiest local-network setup, but
credentials and the session cookie otherwise travel in the clear over the
LAN/Wi-Fi — enabling this is recommended if the dashboard is reachable on a
network you don't fully trust (shared Wi-Fi, larger household/office LAN).

Browsers will show a "not secure" / self-signed warning on first visit
since there is no public CA involved; that's expected for a private local
device and the same trade-off every self-hosted home-lab tool makes. The
cert/key are generated once and reused afterwards.
"""
from __future__ import annotations

import datetime
import ipaddress
from pathlib import Path

from app.config import settings


def ensure_self_signed_cert() -> tuple[Path, Path]:
    cert_path = settings.TLS_CERT_PATH
    key_path = settings.TLS_KEY_PATH
    if cert_path.exists() and key_path.exists():
        return cert_path, key_path

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "miner-dashboard.local")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.utcnow() - datetime.timedelta(days=1))
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=3650))
        .add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName("localhost"),
                x509.DNSName("*.local"),
                x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
            ]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )

    key_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    try:
        key_path.chmod(0o600)
    except OSError:
        pass
    return cert_path, key_path
