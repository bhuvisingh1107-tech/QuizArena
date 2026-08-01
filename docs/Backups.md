# Backups

Operational guide for backing up, restoring, and rolling back QuizArena.

## What to back up

| Asset | Location | Priority |
|-------|----------|----------|
| PostgreSQL database | Docker volume `postgres_data` | **Critical** |
| Uploaded media | Docker volume `storage_data` or `STORAGE_PATH` | **High** |
| Environment secrets | `backend/.env`, root `.env` | **High** (store securely, not in git) |
| Application code | Git repository | Medium (reproducible from VCS) |

## PostgreSQL backup

### Manual dump (running stack)

```bash
docker compose -f docker-compose.prod.yml exec -T db \
  pg_dump -U quizarena -d quizarena -Fc > quizarena-$(date +%Y%m%d-%H%M%S).dump
```

Plain SQL alternative:

```bash
docker compose -f docker-compose.prod.yml exec -T db \
  pg_dump -U quizarena -d quizarena > quizarena-$(date +%Y%m%d).sql
```

### Scheduled backup (cron example)

```bash
0 2 * * * cd /opt/quizarena && docker compose -f docker-compose.prod.yml exec -T db \
  pg_dump -U quizarena -d quizarena -Fc > /backups/quizarena-$(date +\%Y\%m\%d).dump
```

Retain dumps off-host (S3, NFS, etc.) and encrypt at rest.

## Media backup

```bash
docker compose -f docker-compose.prod.yml run --rm -v $(pwd)/backups:/backup backend \
  tar czf /backup/storage-$(date +%Y%m%d).tar.gz -C /app storage
```

Or archive the `storage_data` volume directly from the host.

## Restore database

1. Stop backend to prevent writes:

```bash
docker compose -f docker-compose.prod.yml stop backend
```

2. Restore from custom-format dump:

```bash
docker compose -f docker-compose.prod.yml exec -T db \
  pg_restore -U quizarena -d quizarena --clean --if-exists < quizarena-YYYYMMDD.dump
```

For plain SQL:

```bash
docker compose -f docker-compose.prod.yml exec -T db \
  psql -U quizarena -d quizarena < quizarena-YYYYMMDD.sql
```

3. Verify migrations (optional if dump is from same revision):

```bash
docker compose -f docker-compose.prod.yml exec backend python scripts/verify_migrations.py
```

4. Restart backend:

```bash
docker compose -f docker-compose.prod.yml start backend
```

## Restore media

```bash
docker compose -f docker-compose.prod.yml run --rm -v $(pwd)/backups:/backup backend \
  tar xzf /backup/storage-YYYYMMDD.tar.gz -C /app
```

Ensure file ownership matches the container user (`quizarena`).

## Rollback deployment

### Application rollback (code)

Redeploy a known-good Git tag or image:

```bash
git checkout v1.2.3
docker compose -f docker-compose.prod.yml up -d --build
```

### Database rollback (schema)

**Preferred:** restore from backup taken before the failed migration.

**Alembic downgrade** (only if a reversible migration exists):

```bash
docker compose -f docker-compose.prod.yml exec backend alembic downgrade -1
```

Never downgrade production without a fresh backup and a tested plan.

## Pre-migration checklist

1. Take a PostgreSQL dump
2. Note current Alembic revision: `alembic current`
3. Apply migration in staging first
4. Run `python scripts/verify_migrations.py`
5. Smoke-test `/api/v1/ready` and a live room flow

## Disaster recovery RPO/RTO targets

Define targets for your environment. Example:

| Metric | Target |
|--------|--------|
| RPO (max data loss) | 24 hours (daily backups) |
| RTO (max downtime) | 1 hour |

Improve RPO with more frequent dumps or PostgreSQL continuous archiving (WAL).

## Verification

After any restore:

```bash
curl -sf http://localhost/api/v1/ready
curl -sf http://localhost/api/v1/health
```

Log in as admin, open a quiz, and verify media loads from restored storage.
