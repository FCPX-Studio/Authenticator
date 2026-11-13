# Authenticator

License authentication API for **FCPX Studio** products.

Authenticator issues license keys when a product is bought, and activates them on customer machines. Each activation returns an **Ed25519-signed token** that the product (FxPlug plugin / installer) verifies offline with the matching public key.

Built with FastAPI, SQLAlchemy and PostgreSQL.

---

## How it works

```
 fcpxstudio website                Authenticator                  Customer Mac (plugin)
 ──────────────────                ─────────────                  ─────────────────────
 purchase completed ──POST /license/create──▶ generate key
                     ◀──────── "ABCD-EFGH-JKMN-PQRS"
                                                     ◀──POST /license/activate── key + machine fingerprint
                                   check product, expiry,
                                   activation limit
                                   sign token (Ed25519) ──────▶ verify signature with public key,
                                                                check fingerprint / expiry
```

- **License keys** are 16 random characters from the Crockford Base32 alphabet, formatted `XXXX-XXXX-XXXX-XXXX`. Keys are normalized (trimmed, upper-cased) on activation.
- **Editions**: a license with no `expires_at` is perpetual (`pro`). A license with an `expires_at` date is a `trial`.
- **Activation limit**: each license allows a number of machines (`activation_limit`, default `2`). Each machine uses one seat, identified by its fingerprint. Reactivating a machine that is already registered refreshes its row and does not use another seat.

---

## Getting started

### Requirements

- Python 3.11+
- PostgreSQL

### Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install fastapi uvicorn "sqlalchemy>=2" psycopg2-binary pydantic-settings cryptography
```

### Configure

Copy the example environment file and fill it in:

```bash
cp .env.example .env
```

| Variable                       | Required | Default | Description                                                         |
| ------------------------------ | -------- | ------- | ------------------------------------------------------------------- |
| `license_private_key`          | yes      | —       | Base64 of the raw 32-byte Ed25519 private key used to sign tokens   |
| `POSTGRES_URL`                 | yes      | —       | SQLAlchemy URL, e.g. `postgresql://user:pass@localhost:5432/authenticator` |
| `POSTGRES_POOL_SIZE`           | no       | `5`     | Connection pool size                                                |
| `LICENSE_TOKEN_FORMAT_VERSION` | no       | `1`     | `formatVersion` written into signed tokens                          |

#### Generating a signing key pair

```python
import base64
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization as s

key = Ed25519PrivateKey.generate()
priv = key.private_bytes(s.Encoding.Raw, s.PrivateFormat.Raw, s.NoEncryption())
pub = key.public_key().public_bytes(s.Encoding.Raw, s.PublicFormat.Raw)

print("license_private_key =", base64.b64encode(priv).decode())  # → .env (keep secret)
print("public key          =", base64.b64encode(pub).decode())   # → embed in the product
```

> **Never commit the private key.** `.env` is git-ignored. If the private key changes, every shipped product must be updated with the new public key.

### Run

```bash
uvicorn app.main:app --reload
```

Database tables are created automatically on startup. Existing tables are never altered, so schema changes need a manual migration.

Interactive API docs are served at `http://localhost:8000/docs`.

---

## API

### `POST /license/create`

Creates a license for a product and returns its key.

> ⚠️ This endpoint is **not protected yet**. It is meant to be called only by the fcpxstudio website after a purchase. Do not expose it publicly until access control is in place.

**Request**

```json
{
  "product_id": "com.fcpxstudio.example",
  "activation_limit": 2,
  "customer_email": "customer@example.com",
  "order_id": "order_123",
  "expires_at": null
}
```

`customer_email`, `order_id` and `expires_at` may be `null`. Set `expires_at` (ISO 8601) to create a trial license.

**Response** `200`

```json
"ABCD-EFGH-JKMN-PQRS"
```

### `POST /license/activate`

Validates a license key for a product and registers the calling machine.

**Request**

```json
{
  "license_key": "abcd-efgh-jkmn-pqrs",
  "product_id": "com.fcpxstudio.example",
  "machine_fingerprint": "SHA256:<64 hex chars>",
  "machine_name": "Studio Mac",
  "app_version": "1.2.0",
  "fcpx_version": "11.0",
  "macOS_version": "15.1"
}
```

**Response** `200`

```json
{
  "activation_id": "act_9b5c…",
  "activation_limit": 2,
  "activations_used": 1,
  "license": {
    "payload": "<base64 JSON>",
    "signature_algorithm": "Ed25519",
    "signature": "<signature>"
  }
}
```

**Errors**

| Status | Reason                                                     |
| ------ | ---------------------------------------------------------- |
| `404`  | Unknown key, or the key belongs to a different product     |
| `403`  | License has expired                                        |
| `409`  | Activation limit reached for this license                  |

---

## Signed token

`license.payload` is the base64 encoding of compact JSON (no spaces). The Ed25519 signature covers the **decoded payload bytes** exactly as sent:

```json
{
  "formatVersion": 1,
  "licenseId": "lic_3f2a…",
  "productId": "com.fcpxstudio.example",
  "machineFingerprint": "SHA256:…",
  "issuedAt": "2026-11-13T10:00:00Z",
  "expiresAt": null
}
```

Dates are ISO 8601 UTC (`yyyy-MM-ddTHH:mm:ssZ`) so Swift's `ISO8601DateFormatter` can parse them. The signature is the raw 64-byte Ed25519 format expected by CryptoKit's `Curve25519.Signing.PublicKey.isValidSignature(_:for:)`.

The product should check that:

1. the signature is valid for the payload with the embedded public key,
2. `productId` matches the product,
3. `machineFingerprint` matches the current machine,
4. `expiresAt` is `null` or in the future.

The license key itself is never written into the token.

---

## Project structure

```
app/
├── main.py                      FastAPI app and lifespan (creates the Licensing service)
├── routers/license.py           /license endpoints
├── services/licensing.py        Business rules: key creation, validation, activation
├── keytool/keytool.py           Key generation and Ed25519 token signing
├── schemas/                     Pydantic models, request bodies, domain exceptions
└── db/
    ├── database.py              Engine, session factory, transactional sessions
    ├── models/                  SQLAlchemy tables: licenses, license_activations
    └── repositories/            LicenseRepository (data access)
config.py                        Settings loaded from environment / .env
```

### Data model

- **`licenses`**: `id` (`lic_…`), `license_key` (unique), `product_id`, `activation_limit`, `expires_at`, `customer_email`, `order_id`, `created_at`
- **`license_activations`**: `id` (`act_…`), `license_id` → `licenses`, `machine_fingerprint` (unique per license), `machine_name`, `app_version`, `fcpx_version`, `macos_version`, `created_at`, `last_activated_at`
