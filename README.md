# Pool Builder Backend

FastAPI backend for OTP login, JWT auth, onboarding, and user management.

## Tech Stack
- FastAPI
- SQLAlchemy (Postgres)
- JWT access + refresh tokens

## Requirements
- Python 3.11+ (3.13 supported)
- Postgres running locally

## Setup
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Environment
Create a `.env` file in this folder. Example:
```bash
DATABASE_URL=postgresql://postgres:password@localhost:5432/poolBuilder
JWT_SECRET=your_base64_secret
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=30
OTP_LENGTH=6
OTP_TTL_SECONDS=300
OTP_DEBUG=false

# Email (Gmail API)
OTP_EMAIL_SENDER=developer@glowante.com
GMAIL_TOKEN_FILE=/path/to/credentials/token.json
GMAIL_CREDENTIALS_FILE=/path/to/credentials/credentials.json
```

Notes:
- Set `OTP_DEBUG=true` to return the OTP in the response body (dev only).
- Gmail credentials/token files are expected on disk (not committed).

## Run
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## API Summary
- `POST /api/auth/otp/request`
- `POST /api/auth/otp/verify`
- `POST /api/auth/refresh`
- `POST /api/auth/logout`
- `GET /api/users`
- `GET /api/users/me`
- `PUT /api/users/me`

## Auth
- Use `Authorization: Bearer <access_token>` for protected routes.
- Use `POST /api/auth/refresh` with `refresh_token` to get a new access token.
- Logout expects the refresh token in the `Authorization` header.
