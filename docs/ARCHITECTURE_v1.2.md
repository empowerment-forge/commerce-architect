# 🧱 Commerce Architect  
## Architecture v1.2 (Frozen)

**Status:** Locked  
**Phase:** Phase 1 (Validation / Owner-Operated)  
**Philosophy:** Minimalist, Secure, Reversible, Low-Ops  

---

# 🎯 Core Strategic Principles

1. Minimize operational burden  
2. Minimize security surface  
3. Preserve data ownership  
4. Avoid vendor lock-in  
5. Optimize for validation, not scale  

This architecture is intentionally boring and production-safe.

---

# 🖥 Frontend

## Framework
**React**

## Rationale
- Industry standard
- Large ecosystem
- SPA architecture
- Natural pairing with DRF
- Future React Native compatibility if needed

## Responsibilities
- Product browsing
- Cart handling
- Checkout redirection
- Account management UI
- Reservation / scheduling UI

---

# 🧠 Backend

## Framework
**Django**

## API Layer
**Django REST Framework (DRF)**

## Rationale
- Built-in authentication system
- Admin interface included
- Mature ORM
- Strong permissions model
- Excellent for workflow-heavy business logic
- Reduces need for custom internal tooling

## Responsibilities
- User authentication
- Inventory management
- Scheduling logic
- Reservation management
- Order state machine
- Stripe webhook handling
- Business rule enforcement

---

# 🗄 Database

## Engine
**PostgreSQL**

## Rationale
- ACID compliance
- Strong relational modeling
- JSONB flexibility
- Easy export and migration
- Industry standard

---

# 💳 Payments

## Provider
**Stripe**

## Mode
Hosted Checkout + Stripe Billing

## Rationale
- Minimizes PCI scope (SAQ-A)
- Secure hosted payment UI
- Built-in subscription support
- Mature webhook system
- Strong documentation

No credit card data touches the backend.

---

# ☁ Hosting

## 🥇 Rank 1 — Railway (Chosen)

### Why
- Managed infrastructure
- No OS patching required
- Docker-based deployment
- Managed PostgreSQL
- Automatic SSL/TLS
- Simple developer workflow
- Within early-stage budget

### Tradeoffs
- Usage-based pricing
- Shared resource model
- Less OS-level control than VPS

### Strategic Justification
Phase 1 prioritizes speed, validation, and reduced operational burden.  
Docker preserves portability. PostgreSQL dumps preserve reversibility.

---

## 🥈 Rank 2 — Hetzner VPS

### Why
- Extremely low cost
- Full infrastructure control
- Strong ownership alignment

### Tradeoffs
- OS patching responsibility
- Manual hardening required
- Higher operational complexity

---

## 🥉 Rank 3 — DigitalOcean

### Why
- Stable and predictable
- Docker-friendly
- Well-documented

### Tradeoffs
- No meaningful free tier
- Manual security management
- Higher ops responsibility than Railway

---

# 🐳 Deployment Model

- Dockerized Django backend
- Dockerized React frontend (or static build served separately)
- Managed PostgreSQL
- Stripe webhooks exposed via HTTPS
- Environment variables for secrets
- Railway-managed TLS

---

# 🔒 Security Model

- Hosted Stripe Checkout (no card storage)
- Django CSRF protection
- Django authentication & permissions
- Strict CORS configuration
- HTTPS enforced
- Managed hosting TLS
- No custom cryptography
- No custom auth implementation

---

# 🚫 Explicit Phase 1 Exclusions

- Plugin marketplace
- Multi-tenant admin
- Theme builder
- Microservices architecture
- Kubernetes
- Serverless architecture
- Custom payment processor
- ERP integrations
- Extension ecosystem

---

# 🔁 Reversibility Guarantees

- Docker containers are portable
- PostgreSQL is exportable
- Stripe data exportable
- DNS controlled independently
- No proprietary DB features
- No platform-specific SDK lock-in

Railway can be replaced without rewriting business logic.

---

# 🧭 Evolution Path (Future Phases)

Potential Phase 2+ enhancements:

- Background worker queue (Celery + Redis)
- Dedicated caching layer
- Multi-tenant architecture
- Modular extension layer
- Search indexing
- CDN optimization
- VPS or hybrid infrastructure
- Dedicated monitoring stack

All additions remain compatible with Phase 1 domain design.

---

# 🏁 Final Locked Stack Summary

| Layer        | Decision                       |
|--------------|--------------------------------|
| Frontend     | React                          |
| Backend      | Django + DRF                   |
| Database     | PostgreSQL                     |
| Payments     | Stripe Hosted Checkout         |
| Hosting      | Railway                        |
| Container    | Docker                         |
| Infra Model  | Managed PaaS (Phase 1)         |

---

# 📌 Architecture Freeze Declaration

Architecture v1.2 is formally frozen.

All Phase 1 development decisions must align with this document unless a formal revision (v1.3+) is declared.

No framework changes.
No hosting changes.
No premature scaling changes.

Build. Validate. Iterate.
