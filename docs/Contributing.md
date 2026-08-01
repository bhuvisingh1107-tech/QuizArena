# Contributing

Thank you for contributing to QuizArena.

## Getting started

1. Read [DeveloperSetup.md](./DeveloperSetup.md) to run the stack locally.
2. Familiarize yourself with [PROJECT_SPEC.md](./PROJECT_SPEC.md) and [API_SPEC.md](./API_SPEC.md) for requirements and contracts.

## Branch workflow

- Branch from `main` (or `master`) using descriptive names: `feat/quiz-timer`, `fix/join-validation`.
- Keep changes focused; prefer small, reviewable pull requests.

## Code standards

### Backend (Python)

- Python 3.12, type hints where practical
- FastAPI routers stay thin; business logic in `app/services/`
- New database changes require Alembic migrations
- Run `pytest` before opening a PR

### Frontend (TypeScript)

- Strict TypeScript; run `npx tsc -b --noEmit`
- React function components; co-locate tests with features
- Use existing UI patterns (Tailwind, shared components)
- Run `npm test` and `npm run lint` (oxlint)

## Migrations

Every schema change must include an Alembic revision:

```bash
cd backend
alembic revision --autogenerate -m "short_description"
alembic upgrade head
python scripts/verify_migrations.py
```

## Pull requests

Include in the PR description:

- **Summary** — what changed and why
- **Test plan** — commands run and manual checks
- **Screenshots** — for UI changes

CI runs backend tests, frontend tests/build, typecheck, lint, migration check, and Docker image builds.

## Reporting issues

Include reproduction steps, expected vs actual behavior, and relevant logs (backend JSON logs, browser console).

## Documentation

Update docs when changing:

- Environment variables → [EnvironmentVariables.md](./EnvironmentVariables.md)
- Deployment steps → [Deployment.md](./Deployment.md)
- API behavior → [API_SPEC.md](./API_SPEC.md)

## License

By contributing, you agree that your contributions will be licensed under the same terms as the project.
