NARO-LIMS

System Structure and Technology Overview
A briefing note for non-technical stakeholders

1. Introduction

The National Agricultural Research Organisation Laboratory Information Management System (NARO-LIMS) is a modern, web-based digital platform designed to manage laboratory samples, records, and workflows across NARO laboratories.

NARO-LIMS is structured to ensure data integrity, traceability, security, and long-term institutional memory. Rather than being a single piece of software, it is a coordinated system made up of several well-defined components, each with a specific responsibility.

This briefing explains how the system is organised, what each major component does, and the technologies used, in a way that does not require technical expertise.

2. Overall System Organisation

NARO-LIMS follows a modular structure. Each module performs a specific role, and together they form a reliable and auditable laboratory information system.

At a high level, the system consists of:

A core laboratory logic layer

A user interface layer

Background processing services

Data storage and infrastructure services

Security and deployment components

This separation ensures that the system is robust, scalable, and suitable for long-term institutional use.

3. Core Application Layer (Laboratory Logic)
The heart of the system

The central component of NARO-LIMS is the core application layer, which contains all the rules and logic related to laboratory work.

This layer is responsible for:

Defining what a laboratory sample is

Managing how samples move through their lifecycle

Enforcing rules that prevent illegal or accidental data changes

Controlling user actions based on roles and permissions

In practical terms, this is where the system “understands” laboratory operations and enforces good scientific practice.

Technology used: Django

This layer is built using Django, a widely used and trusted web framework written in Python. Django is used globally by governments, universities, and research institutions because it emphasizes:

Data integrity

Security

Clear separation of responsibilities

Long-term maintainability

4. System Configuration and Control

The system includes a dedicated configuration component that defines:

How the system starts and runs

How it connects to the database

Security settings

Deployment behavior

This component ensures that all parts of the system work together correctly and consistently across environments.

In non-technical terms, this is the operating manual the system reads every time it runs.

5. User Interface Layer
What users see

The user interface layer controls how information is presented to users through a web browser.

It is responsible for:

Displaying forms, tables, and dashboards

Presenting sample information clearly

Separating visual appearance from scientific logic

This layer ensures that laboratory staff interact with the system in a clear and structured way, while the underlying rules remain strictly enforced.

Technologies used

Standard web technologies (HTML and CSS)

Django’s built-in templating system

6. Visual and Interaction Assets

Supporting the user interface is a collection of static resources that define:

Visual styling (colors, layout, fonts)

Icons and images

Interactive behaviors such as validation messages

These components determine the look and feel of NARO-LIMS and help ensure usability without compromising data integrity.

7. Database and Data Integrity
Institutional memory

All laboratory data in NARO-LIMS is stored in a dedicated database system.

The database is responsible for:

Storing samples, statuses, users, and history

Preserving records over time

Preventing data corruption or inconsistency

Technology used: PostgreSQL

NARO-LIMS uses PostgreSQL, an enterprise-grade database system trusted worldwide by research institutions, governments, and large organisations. PostgreSQL is known for:

Reliability

Strong data integrity guarantees

Long-term stability

This database represents the permanent institutional memory of the laboratory system.

8. Background Processing and Automation

Some tasks should not slow down users or require constant manual attention. NARO-LIMS handles these using background processing services.

These services are used for:

Long-running operations

Scheduled or repeated tasks

Automated system processes

Technologies used

Celery: a background task management system

Redis: a fast coordination service that helps different parts of the system communicate efficiently

In simple terms, these technologies allow the system to work quietly in the background while users continue their normal work.

9. System Integrity and Quality Control

To ensure long-term reliability, NARO-LIMS includes automated testing components.

These tests:

Verify that sample lifecycle rules are enforced

Prevent accidental breaking of critical safeguards

Ensure that updates do not compromise system integrity

This approach provides confidence that the system behaves correctly even as it evolves.

10. Deployment, Security, and Availability

NARO-LIMS is deployed using industry-standard infrastructure components that ensure availability and security.

These include:

Gunicorn: runs the application efficiently

Nginx: manages web traffic and user requests

Cloudflare: provides secure internet access, encryption, and protection

Systemd: ensures the system starts automatically and remains operational

Together, these components ensure that NARO-LIMS is:

Secure

Reliable

Accessible

Protected from common cyber threats

11. Why This Structure Matters

This carefully defined structure ensures that:

Laboratory data cannot be silently altered

Scientific traceability is preserved

The system can grow without redesign

Institutional knowledge is embedded in the system

New laboratories can be onboarded efficiently

This approach mirrors best practices used in long-lived national and international research systems.

12. Key Takeaway

NARO-LIMS is a coherent, institution-grade digital system, not a simple application.

Its structure and technology choices prioritize:

Integrity over convenience

Traceability over speed

Longevity over short-term fixes

This makes it a strong foundation for present and future laboratory information management within NARO.
