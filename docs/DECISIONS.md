# Implementation decisions

- Use the existing project root for the section 19 layout; avoid a redundant nested clearline directory.
- Use SQLite only for isolated unit tests; Docker, demos and integration checks use PostgreSQL 16 and pgvector.
- Keep the configured embedding default local; explicitly select hash for offline demo/CI to avoid downloading a model.
- Demo credentials are public, local-only configuration; both services bind to loopback.
