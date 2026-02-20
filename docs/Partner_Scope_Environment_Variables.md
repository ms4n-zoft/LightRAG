# Partner Scope — Environment Variables

Environment variables required for the partner-scoped query service.

## Required

| Variable         | Example                                                       | Description                                                                                                                                                                                                               |
| ---------------- | ------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `PEKO_MONGO_URI` | `mongodb://host.docker.internal:27017/?directConnection=true` | MongoDB connection URI for the Peko partner database. When running inside Docker, use `host.docker.internal` instead of `localhost` to reach the host machine's MongoDB.                                                  |
| `PEKO_DB_NAME`   | `PekoPartnerDB`                                               | Database name containing the partner's `products` collection. Each document must have an `_id` field whose string representation matches the product IDs used in the RAG store (`product_id:<hex_id>:source:...` format). |

## Optional

| Variable                  | Default | Description                                                                                            |
| ------------------------- | ------- | ------------------------------------------------------------------------------------------------------ |
| `PARTNER_SCOPE_CACHE_TTL` | `3600`  | How long (in seconds) to cache the partner's product ID set in memory before re-fetching from MongoDB. |

## Where to set them

- **Docker (test)**: Add to `.env.test`, which is volume-mounted as `/app/.env` in `docker-compose.test.yml`.
- **Docker (production)**: Add to the `.env` file used by your production `docker-compose.yml`, or set them directly in the compose `environment:` block.
- **Local dev**: Export in your shell or add to a local `.env` file.

## Notes

- If `PEKO_MONGO_URI` is not set, it defaults to `mongodb://localhost:27017/?directConnection=true`. This works for local dev but will fail inside a Docker container (localhost resolves to the container itself).
- The service uses `motor` (async MongoDB driver) if available, falling back to synchronous `pymongo`. The Docker image includes `motor` via `requirements.txt`.
- Adding a new partner requires adding a new `PartnerConfig` entry in `lightrag/services/partner_scope_service.py` along with corresponding env vars for that partner's MongoDB URI and database name.
