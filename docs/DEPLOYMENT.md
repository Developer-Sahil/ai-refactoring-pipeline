# Deployment Guide — AI Refactoring Pipeline

## Overview
The AI Refactoring Pipeline is a modern SaaS application. Deployment uses Cloudflare for DNS/edge protection, Vercel for frontend hosting, and Firebase Auth for user identity.

## Frontend (Vercel)
The React/Vite frontend deploys to **Vercel**.
- **Platform**: [Vercel](https://vercel.com)
- **Framework Preset**: Vite
- **Build Command**: `npm run build`
- **Output Directory**: `dist`
- **Environment Variables**:
  - `VITE_API_URL` — URL of the production backend API
  - `VITE_FIREBASE_API_KEY` — Firebase project API key
  - `VITE_FIREBASE_AUTH_DOMAIN` — Firebase auth domain
  - `VITE_FIREBASE_PROJECT_ID` — Firebase project ID

## Authentication (Firebase Auth)
- **Provider**: [Firebase Authentication](https://firebase.google.com/products/auth) (Google Identity Platform)
- **Supported sign-in methods**: Email/Password, Google OAuth
- **Token validation**: Backend validates Firebase ID tokens on every protected request via the Firebase Admin SDK
- **Required env vars on backend**:
  - `FIREBASE_PROJECT_ID`
  - `FIREBASE_PRIVATE_KEY`
  - `FIREBASE_CLIENT_EMAIL`

## Backend (Cloudflare + VPS / Docker)
The FastAPI backend can be deployed in several ways:
- **Cloudflare**: DNS, SSL termination, and DDoS protection.
- **Hosting**: Standard VPS or Docker via `docker-compose.ymal`.
- **Cloudflare Tunnel**: Recommended for securely exposing the backend without opening public ports.
- **Required env vars**:
  - `GEMINI_API_KEY` — Gemini API access
  - Firebase Admin credentials (see above)

## Infrastructure Monitoring
- **Error Tracking**: Sentry (recommended)
- **Analytics**: Cloudflare edge analytics
- **Logs**: Backend stdout/stderr captured by uvicorn; pipe to your logging stack
