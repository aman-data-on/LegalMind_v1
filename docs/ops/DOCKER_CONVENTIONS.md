# Docker conventions (project-neutral)

**Status:** 📁 operational reference, adopted 2026-10-16 for `docker-compose.yml`. It decides
nothing in the specification: locked 55.6 still records hosting platform and container
orchestration as NOT YET SPECIFIED, and **production does not run Docker** — the app, PostgreSQL,
Redis and nginx run on the host under systemd (see [ops/production/README.md](../../ops/production/README.md)).
These rules govern the development/staging stack in `docker-compose.yml` and any future
production use. `backend/tests/test_compose_conventions.py` enforces them in CI.

How we run supporting services (databases, admin tools, caches) in Docker on a single
production server. Written to be copied into another project as-is — an engineer or an AI
coding agent can follow it as a checklist.

## The shape

- **Docker runs the supporting services, not necessarily the app.** Databases, admin GUIs and
  caches go in `docker-compose.yml`. The app can run as a systemd service when its deploys need
  more than "restart a container" (build aside, smoke-test, swap, auto-rollback, wait for
  background jobs). LegalMind's `legalmind-deploy` is exactly that case.
- **One `docker-compose.yml` in the repo, one secrets file outside git.**

## Checklist for every service

1. **Bind ports to localhost only** — `"127.0.0.1:${DB_PORT}:5432"`, never `"5432:5432"`. A bare
   mapping listens on every interface, and Docker's own firewall rules are inserted ahead of the
   host firewall (ufw/iptables), so "the firewall blocks it" is usually false. Only the reverse
   proxy (80/443) is public. Reach admin tools through an SSH tunnel:
   `ssh -L 8080:localhost:8080 you@server`.
2. **Give each container only the variables it needs, by name** (`environment:` keys). Never
   `env_file: .env` / `.env.local` on a service: it copies every app secret into that container.
   Check what a container really holds (names only):
   `docker inspect <name> --format '{{range .Config.Env}}{{println .}}{{end}}' | cut -d= -f1`
3. **Keep secrets in one git-ignored file, pass it explicitly.** Real values in `.env.local`
   (git-ignored); the committed `.env.example` lists every key with placeholders. Compose only
   auto-reads `.env`, so always run `docker compose --env-file .env.local up -d`.
4. **Put data in named volumes.** Recreating a container is then always safe.
   `docker compose down -v` (`-v`!) deletes the data — never run it on a server.
5. **Health check and restart policy** on every service: `restart: unless-stopped` and a
   `healthcheck`. Use `$$VAR` in health checks (read inside the container at run time), not
   `${VAR}` (compose bakes the value into the container config, visible to `docker inspect`).
   Dependants use `depends_on: { db: { condition: service_healthy } }`.
6. **Boot order for anything outside Docker.** If the app runs under systemd and its database in
   Docker, order it after Docker with a drop-in (`After=docker.service`, `Wants=docker.service`)
   and make the app retry its first database connection.
7. **Back up through the container** (`docker exec <db> pg_dump …`), nightly from cron, alert on
   failure, copy off the server, and test a restore at least once. LegalMind's database is on the
   host, so its backup is `ops/production/backup.sh` (database AND uploaded documents, encrypted
   off-server, read back and decrypt-tested every night).
8. **Update Docker by hand.** Exclude Docker from automatic OS updates: an upgrade restarts every
   container, including databases in the middle of work. The same holds for a host database —
   see `ops/production/52legalmind-unattended-holds` for PostgreSQL, Redis and nginx.

## Changing a running service

`docker compose --env-file .env.local up -d` after an edit **recreates** that container — expect
10–30 seconds of downtime for a database. Before doing it: the file is valid
(`docker compose --env-file .env.local config --quiet`); nothing is mid-job (imports, syncs,
migrations). Afterwards: health is `healthy`, the data is there (count rows in a known table),
the app answers, and a backup run still succeeds.

## Don't

- Publish database or cache ports on all interfaces.
- `env_file:` the whole app secrets file into a container.
- Commit `.env` / `.env.local`, or put real values in `.env.example`.
- `docker compose down -v`, or `docker system prune --volumes`, on a server.
- Let unattended upgrades touch Docker — or a production database.
