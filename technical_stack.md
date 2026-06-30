# Technical Architecture Directory & Technical Stack: DivorceConnect India

This document details the complete, production-ready, high-performance hybrid technology stack powering the **DivorceConnect India** platform. The architecture integrates an asynchronous **FastAPI** backend with a dynamic **Vanilla JS Single-Page Hydrated** frontend, supported by a decoupled **Django management layer** and real-time **WebSocket** notifications.

---

## 1. ⚙️ Web Server & Core API Framework
*   **Primary Application Framework:** **FastAPI (v0.138.1)** (fully compatible with Python 3.14). Manages all asynchronous JSON REST APIs, WebSocket connections, dependencies, and request/response validation.
*   **Asynchronous ASGI Server:** **Uvicorn (v0.49.0)**. Runs the FastAPI application with high-throughput event loops using `httptools` and custom WebSocket protocols.
*   **Production Process Manager:** **Gunicorn (v26.0.0)**. Used as the process controller in production environments, binding Uvicorn workers (`uvicorn.workers.UvicornWorker`) to handle worker process lifecycles.
*   **Coexistence Layer (Management):** **Django (v6.0.6)**. Leveraged for legacy management operations, shell scripting, database migration generation, and database admin tasks (`manage.py`).
*   **Static Asset Optimization:** **Whitenoise (v6.12.0)**. Serves cached, gzip/brotli-compressed static assets directly from the FastAPI ASGI application, bypassing the need for a separate static file server.

---

## 2. 🗄️ Database, ORM, & Modeling Layer
*   **Database Engine:** **SQLite** (`db.sqlite3` database file for development and operation).
*   **Object-Relational Mapping (ORM):** 
    *   **Asynchronous Engine:** **SQLAlchemy (v2.0.51)**. Handles non-blocking database queries via an asynchronous SQLite engine driven by `aiosqlite (v0.22.1)`.
    *   **Synchronous Engine:** **Django ORM** (shares the database schema for Django administrative commands).
*   **Schema Migration Engine:** **Alembic (v1.18.5)**. Manages database model changes and database schemas. Configured via `alembic.ini` and python scripts inside the `/alembic` folder.
*   **Data Validation & Serialization:** **Pydantic (v2.13.4)** & **Pydantic Core (v2.46.4)**. Validates incoming API payloads and formats outgoing SQLAlchemy queries into serialized JSON models.

---

## 3. 🔐 Authentication & Two-Step Verification Flow (OTP Security)
*   **Session Management:** **JWT (JSON Web Tokens)**. Tokens are generated upon login and passed via `Authorization: Bearer <token>` headers. The backend extracts and validates credentials using FastAPI's dependency injection (`Depends(get_current_user)`).
*   **2-Step OTP Authentication Flow:**
    *   **Register Endpoint (`POST /api/auth/register`):** Creates the database User with `is_active=False` (inactive state). Generates a 6-digit registration OTP, saves it in the `accounts_otpcode` table via the `OTPCode` SQLAlchemy model, and sends it to the user's inbox in the background, returning `{"redirect": "/verify-register-otp/"}`.
    *   **Login Endpoint (`POST /api/auth/token`):** Validates credentials, generates a 6-digit login OTP, dispatches it via background task queues, and returns `{"redirect": "/verify-otp/"}`.
    *   **OTP Verification Endpoints (`/api/auth/verify-otp` and `/api/auth/verify-register-otp`):** Authenticate matching un-expired (10-minute validity) OTP codes, mark them as used, activate the user (`is_active=True`), generate and return the JWT `access_token` and `token_type`, and dispatch the welcome emails.

---

## 4. 📬 Sockets, Multi-Purpose SMTP, & Cloud Assets
*   **Real-time Push Notifications:** Asynchronous WebSockets managed by a global `ConnectionManager` inside [notifications.py](file:///D:/Software%20Setup/C/Django_Projects/PROJECT99/divorce-connect-india/divorce_connect/fastapi_app/notifications.py). Maps WebSocket connections dynamically to active client sessions.
*   **Dynamic Database Notification Integrations:**
    *   Unified helper `create_and_broadcast_notification` writes records to the `accounts_notification` table and triggers instant WebSocket broadcasts on active channels.
    *   Triggered dynamically upon: **Profile Updates**, **Case Hire Request Creations**, and **Successful Verified Registrations**.
*   **Dual SMTP Mailing Architecture:** Decoupled SMTP pipelines for separate functions:
    *   **Auth SMTP Pipeline:** Host `smtp.gmail.com:587` ➔ Dispatching verification links, registration codes, and password reset codes.
    *   **Operations SMTP Pipeline:** Host `smtp.gmail.com:587` ➔ Sending transaction invoices, case updates, and lawyer onboarding validations.
    *   **Implementation:** Standard python `smtplib`, `email.mime.text.MIMEText`, and `email.mime.multipart.MIMEMultipart`.
*   **Media & Document Hosting:** **Cloudinary (v1.44.2)**. Stores case attachments and profile pictures securely in the cloud, mapped through `django-cloudinary-storage (v0.3.0)`.
*   **Image Processing:** **Pillow (v12.2.0)**. Processes, crops, and validates uploaded images before cloud transfer.

---

## 5. 🔄 Background Tasks, Schedulers, & Queue Workers
*   **Event Broker:** **NATS (via nats-py v2.15.0)**. Serves as the central messaging bus.
*   **Background Worker:** **Taskiq (v0.12.4)** & **Taskiq-NATS (v0.6.0)**. Evaluates and executes asynchronous task queues in dedicated backend worker processes.
*   **Case Reminders Schedulers:**
    *   **pycron (v3.2.0)** monitors background schedules.
    *   **Reminders Route (`GET /api/reminders/check-due`):** Triggered to sweep outstanding reminders, verify their timestamps, set status to `sent`, and dispatch alerts to clients via WebSockets and email.

---

## 6. 🎨 Jinja2 Layout Loader & Dynamic Path Router
*   **Template Loader Bridge:** `DjangoToJinjaFileSystemLoader` (located in [main.py](file:///D:/Software%20Setup/C/Django_Projects/PROJECT99/divorce-connect-india/divorce_connect/fastapi_app/main.py)).
    *   A custom Jinja2 template loader subclass that parses file contents on-the-fly.
    *   Translates Django template syntax like colons (`|filter:arg` to `|filter("arg")`), `{% empty %}` loops, `{% widthratio %}` calculations, and `forloop` attributes (`forloop.counter0` to `loop.index0`) to Jinja2 compliant syntax before parsing.
*   **Dynamic Template Mapping:** Auto-maps frontend request routes `/verify-otp/` and `/verify-register-otp/` to the physical templates `verify_otp.html` and `verify_register_otp.html`.

---

## 7. 💰 Payments, Billings, & Escrow
*   **Payment Gateway:** **Razorpay**.
*   **Backend Implementation:** [payments.py](file:///D:/Software%20Setup/C/Django_Projects/PROJECT99/divorce-connect-india/divorce_connect/fastapi_app/api/payments.py).
*   **Transaction Flow:**
    1.  **Pending Payment Creation (`POST /api/payments/`):** Generates a payment record on `Payment` table (in `INR` currency) mapped to a specific `CaseRequest`. Triggers instant WebSocket alert to client and lawyer.
    2.  **Payment Verification (`POST /api/payments/{payment_id}/verify`):** Verifies the transaction state (`SUCCEEDED` / `FAILED`) against the `razorpay_payment_id`.
    3.  **Client Notifications:**
        *   Flashes status details instantly on screen via active WebSockets.
        *   Dispatches an HTML payment receipt/confirmation email to the client's inbox.
*   **Document Generation Support:** Under-the-hood preparation for HTML-to-PDF compilers (such as `weasyprint`, `reportlab`, or `xhtml2pdf`) to automate downloading receipt invoices directly.

---

## 8. 🌐 Client-Side Logic & State Hydration (Frontend)
*   **Hydration Architecture:** **Single-Page Hydration (Vanilla JS)**.
    *   Skeletons are loaded initially, and all dynamic content is populated asynchronously on the client-side via JavaScript `fetch()` API calls against backend routers.
*   **State & Authentication Client:** [auth.js](file:///D:/Software%20Setup/C/Django_Projects/PROJECT99/divorce-connect-india/divorce_connect/static/js/auth.js).
    *   Stores active JWT access tokens securely inside browser `localStorage`.
    *   Automatically validates credentials on page load (`GET /api/auth/me`). If invalid (401), it flushes local credentials and redirects users to `/login/`.
    *   Drives role-based rendering (showing/hiding menus for clients, lawyers, and administrators).
*   **Real-time Sockets Notification Client:** [notifications_api.js](file:///D:/Software%20Setup/C/Django_Projects/PROJECT99/divorce-connect-india/divorce_connect/static/notifications_api.js).
    *   Runs globally on load. Pulls unread database alerts from `/api/notifications/` and populates the notification panel on Client, Lawyer, or Admin navbars.
    *   Integrates an **automatic refresh token workflow** (`POST /api/token/refresh/`) to query fresh access tokens on-the-fly.
    *   Maintains a WebSocket handshake matching user ids, prepends incoming messages dynamically, and renders slide-in Tailwind Toast notifications when messages arrive.
*   **Styling & UI Components:** **Tailwind CSS (CDN)** + Custom Theme overrides.
    *   **Design Framework:** Translucent, glassmorphic UI using backdrop filters (`backdrop-filter: blur(...)`) and translucent panels (`bg-white/5`).
*   **Analytics Visualization:** **Chart.js (CDN)** via [admin_charts.js](file:///D:/Software%20Setup/C/Django_Projects/PROJECT99/divorce-connect-india/divorce_connect/static/js/admin_charts.js). Renders interactive earnings lines, onboarding bars, and case status breakdown charts.

---

## 9. 🧪 Testing & QA Suite
*   **Testing Harness:** **Pytest (v9.1.1)** with `anyio (v4.14.1)` async extensions.
*   **Test Suite:** 
    *   [test_phase7.py](file:///D:/Software%20Setup/C/Django_Projects/PROJECT99/divorce-connect-india/divorce_connect/fastapi_app/tests/test_phase7.py): Tests case requests, payments list/verify endpoints, client deactivations, and reminders check-due scheduling.
    *   [test_otp.py](file:///D:/Software%20Setup/C/Django_Projects/PROJECT99/divorce-connect-india/divorce_connect/fastapi_app/tests/test_otp.py): Tests the entire 2-step registration & login OTP verification pipeline and checks the template loading rendering engine.
