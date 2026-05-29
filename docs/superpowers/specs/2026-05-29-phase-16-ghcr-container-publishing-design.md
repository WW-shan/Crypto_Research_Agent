# Phase 16 GHCR Container Publishing Design

## Goal

Publish the Docker runtime image to GitHub Container Registry and make VPS
deployments pull that image by default instead of requiring each server to
build from source.

## Scope

This phase is an operations packaging change. It does not change the
LLM-native product commands, data collection logic, validators, paper
simulation, risk guards, memory, reports, or live-trading boundaries.

The GHCR runtime must:

- publish `ghcr.io/ww-shan/crypto-alpha-agent` from the repository's
  `Dockerfile`;
- tag default-branch images as `main` and immutable images as `sha-<commit>`;
- publish git tag images when a version tag is pushed;
- use GitHub Actions `GITHUB_TOKEN` package permissions instead of committing
  registry credentials;
- make `docker-compose.yml` default to the GHCR image;
- keep local Docker builds possible through an explicit
  `CRYPTO_ALPHA_AGENT_IMAGE=crypto-alpha-agent:local` override;
- keep `.env`, `var/`, worktrees, and credentials outside image build context
  and git.

## Architecture

Add one GitHub Actions workflow under `.github/workflows/`. On pushes to
`main`, version tags, or manual dispatch, it checks out the repository, logs
in to `ghcr.io` with `${{ secrets.GITHUB_TOKEN }}`, generates OCI tags and
labels with Docker metadata, and publishes the image with Buildx.

Compose remains the local runtime interface. The service image becomes:

```yaml
image: ${CRYPTO_ALPHA_AGENT_IMAGE:-ghcr.io/ww-shan/crypto-alpha-agent:main}
```

The `build:` section stays in the file so a developer can deliberately build a
local image, but the VPS runbook uses `docker compose pull` and
`llm-health-check` before timers are enabled. Local long-running soak jobs that
should use the current working tree must set
`CRYPTO_ALPHA_AGENT_IMAGE=crypto-alpha-agent:local`.

## Data Flow

```text
push to main/tag -> GitHub Actions -> build Dockerfile
  -> ghcr.io/ww-shan/crypto-alpha-agent:main
  -> ghcr.io/ww-shan/crypto-alpha-agent:sha-<commit>
  -> optional git tag image

VPS maintenance window -> docker compose pull crypto-alpha-agent
  -> docker compose run --rm crypto-alpha-agent llm-health-check
  -> systemd timers run existing ops wrappers
```

## Error Handling

- If GitHub Actions cannot build or push the image, the workflow fails and no
  VPS update should be promoted.
- If a private GHCR package requires authentication, the operator logs in on
  the VPS with a host-local token; no token is stored in the repo.
- If `docker compose pull` or `llm-health-check` fails on the VPS, timers stay
  stopped.
- Existing product command failures, failed markers, manifests, and logs are
  unchanged.

## Testing

Tests remain local and do not require Docker, GitHub Actions, or GHCR network
access. Contract tests verify:

- the workflow publishes to `ghcr.io/ww-shan/crypto-alpha-agent`;
- the workflow grants only `contents: read` and `packages: write`;
- it uses Docker login, metadata, and build-push actions;
- it tags `main`, `sha-<commit>`, and git tags;
- compose defaults to GHCR while keeping the local image override;
- VPS docs show `docker compose pull`, `llm-health-check`, optional
  `docker login ghcr.io`, and the local image override.

## Security Boundaries

- No OpenAI key, Dune key, exchange key, registry PAT, wallet key, or proxy
  value is committed.
- The workflow uses GitHub's short-lived package token.
- Docker build context still excludes `.env`, `var/`, `.venv/`, worktrees,
  caches, logs, reports, and git metadata.
- Published images do not contain runtime secrets; secrets are mounted or
  loaded at runtime on the host.
