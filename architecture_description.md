NARO-LIMS

High-Level System Architecture

1. Architectural Overview (Plain-Language Description)

NARO-LIMS is designed as a layered, modular system, where each layer has a clearly defined responsibility.
This design ensures data integrity, security, scalability, and long-term institutional reliability.

At the highest level, the system is organised into five main layers:

User Access Layer

Application Logic Layer

Background Processing Layer

Data Storage Layer

Infrastructure and Security Layer

Each layer can evolve independently without compromising the others.

2. Layer 1: User Access Layer

What it is
This is how users interact with NARO-LIMS.

Who uses it

Laboratory technicians

Scientists

Laboratory managers

Institutional administrators

How it works

Users access the system through a standard web browser

No special software installation is required

Key characteristics

Role-based access

Clear forms and dashboards

Consistent user experience

Technologies involved

Web browser

HTML and CSS

Django templating system

3. Layer 2: Application Logic Layer (Core System)

What it is
This is the brain of NARO-LIMS.

What it does

Defines what a sample is

Enforces the sample lifecycle

Controls permissions and actions

Prevents illegal or silent data changes

Why it matters
All scientific and institutional rules are enforced here.
If an action violates the system charter, it is blocked at this layer.

Technology involved

Django (Python-based framework)

Django is widely used in research, government, and enterprise systems because it enforces structure, security, and consistency.

4. Layer 3: Background Processing Layer

What it is
This layer handles tasks that should not interrupt users.

Examples

Scheduled tasks

Batch processing

Notifications

Long-running operations

Why it matters
It allows NARO-LIMS to scale and remain responsive even as usage grows.

Technologies involved

Celery: manages background tasks

Redis: coordinates and queues these tasks efficiently

In simple terms, this layer allows the system to “work in the background”.

5. Layer 4: Data Storage Layer

What it is
This is where all laboratory data is permanently stored.

What it stores

Samples and their lifecycle states

User accounts and roles

Audit-relevant records

Historical data

Why it matters
This layer represents the institutional memory of NARO-LIMS.

Technology involved

PostgreSQL database

PostgreSQL is a robust, enterprise-grade database trusted globally for mission-critical data.

6. Layer 5: Infrastructure and Security Layer

What it is
This layer ensures that NARO-LIMS is accessible, secure, and always running.

Responsibilities

Serving the web application

Handling internet traffic

Encrypting communication

Protecting against common cyber threats

Ensuring automatic startup and recovery

Technologies involved

Gunicorn: application server

Nginx: web server and traffic manager

Cloudflare: security, encryption, and internet access

Systemd: service management

This layer is largely invisible to users but critical for reliability.

7. High-Level Architecture Diagram (Conceptual)

You can present the system visually as follows:

┌────────────────────────────────────────────┐
│              Users (Web Browser)            │
│  Technicians • Scientists • Managers        │
└───────────────────────────┬────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────┐
│           User Interface Layer               │
│   Web pages, forms, dashboards               │
│   (HTML, CSS, Django Templates)              │
└───────────────────────────┬────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────┐
│         Application Logic Layer              │
│   Sample lifecycle • Rules • Permissions     │
│   Core laboratory logic (Django)             │
└───────────────────────────┬────────────────┘
                            │
           ┌────────────────┴────────────────┐
           ▼                                 ▼
┌──────────────────────────┐   ┌──────────────────────────┐
│ Background Processing     │   │    Data Storage Layer     │
│  Tasks & automation       │   │  PostgreSQL Database      │
│  (Celery + Redis)         │   │  Samples & History        │
└──────────────────────────┘   └──────────────────────────┘
           │
           ▼
┌────────────────────────────────────────────┐
│     Infrastructure & Security Layer          │
│  Nginx • Gunicorn • Cloudflare • Systemd    │
└────────────────────────────────────────────┘

8. Why This Architecture Was Chosen

This architecture ensures that:

Scientific rules cannot be bypassed

Data integrity is enforced centrally

The system can grow without redesign

Security is built in, not added later

Institutional knowledge is preserved

It reflects best practices used in national research infrastructures, regulated laboratory systems, and long-lived public sector platforms.

9. Key Message for Stakeholders

NARO-LIMS is:

Modular, not monolithic

Secure by design

Scalable and maintainable

Built for long-term institutional use

This architecture provides a solid, future-proof foundation for laboratory information management within NARO.
