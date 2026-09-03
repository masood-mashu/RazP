# Deploying RazP Sentinel on Vercel

RazP is configured for **zero-friction full-stack deployment on Vercel** (Vite React Operator Console + Python Serverless FastAPI backend) under a single project domain.

---

## 🚀 Quick Deploy (Option 1: Vercel CLI)

If you have the Vercel CLI installed:

```bash
# 1. Login to Vercel (if not already logged in)
vercel login

# 2. Deploy from the repository root
vercel

# 3. Deploy to production
vercel --prod
```

---

## 🌐 Git Integration (Option 2: GitHub / GitLab / Bitbucket)

1. Push your code to your Git repository:
   ```bash
   git add .
   git commit -m "Configure Vercel fullstack deployment"
   git push origin main
   ```
2. In your [Vercel Dashboard](https://vercel.com/dashboard):
   - Click **Add New...** -> **Project**.
   - Import your repository.
   - **Framework Preset**: Select **Vite** (or Other).
   - **Root Directory**: Leave as `./` (the repository root). **Do NOT change to `frontend`**.
   - **Build Command**: `cd frontend && npm install && npm run build` (auto-configured in `vercel.json`).
   - **Output Directory**: `frontend/dist` (auto-configured in `vercel.json`).
3. Click **Deploy**.

---

## 🔐 Environment Variables to Set in Vercel

Under **Project Settings -> Environment Variables**, add:

| Variable | Required | Description | Default / Example |
| :--- | :--- | :--- | :--- |
| `GEMINI_API_KEY` | Recommended | Google AI Studio Gemini API Key for autonomous reasoning. | `AIzaSy...` |
| `DATABASE_URL` | Optional | PostgreSQL connection string (Neon, Supabase, Vercel Postgres). | `postgresql://user:pass@ep-xxx.neon.tech/razp?sslmode=require` |
| `RAZP_DEMO_IN_MEMORY` | Optional | Forces in-memory demo fallback if no database is connected. | `true` (auto-enabled on Vercel if `DATABASE_URL` is empty) |
| `ALLOWED_ORIGINS` | Optional | Comma-separated CORS origins. `*.vercel.app` is allowed automatically. | `https://your-custom-domain.com` |

> [!TIP]
> **No database yet?** RazP will automatically boot into high-speed **Demo In-Memory Mode** on Vercel if `DATABASE_URL` is not provided. You can attach a free PostgreSQL database (e.g. from [Neon](https://neon.tech) or [Supabase](https://supabase.com)) at any time by simply adding the `DATABASE_URL` environment variable.

---

## 📁 Architecture on Vercel

```
┌────────────────────────────────────────────────────────┐
│                   Vercel Edge Network                  │
└────────────────────────────────────────────────────────┘
          │                                  │
          ▼ (/api/*)                         ▼ (/*)
┌───────────────────────────┐    ┌───────────────────────────┐
│ Python Serverless Function│    │   Static Edge CDN Cache   │
│       api/index.py        │    │       frontend/dist       │
│  (FastAPI Recovery Engine)│    │   (React Operator UI)     │
└───────────────────────────┘    └───────────────────────────┘
```

---

## 🛠 Local Development Note (Port 8000 in Use)

If you saw:
```
ERROR: [Errno 10048] error while attempting to bind on address ('127.0.0.1', 8000)
```
Port `8000` is already being used by an existing server process on your machine.

- **To run on an alternate port**:
  ```bash
  python -m uvicorn server.app:app --host 127.0.0.1 --port 8001 --reload
  ```
- **To stop the existing process on port 8000 (Windows PowerShell)**:
  ```powershell
  # Find PID using port 8000
  netstat -ano | findstr :8000
  # Stop the process
  taskkill /PID <PID> /F
  ```
