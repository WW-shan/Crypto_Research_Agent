# Phase 16 GHCR Container Publishing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish the Docker runtime image to GHCR and make VPS deployment pull `ghcr.io/ww-shan/crypto-alpha-agent:main` by default.

**Architecture:** Add a GitHub Actions workflow that builds `Dockerfile` with Buildx and pushes to GHCR. Update Compose to default to the GHCR image while retaining an explicit local image override for development and local soak runs.

**Tech Stack:** GitHub Actions, GHCR, Docker Buildx, Docker Compose, bash, pytest, ruff.

---

## Files

- Create: `.github/workflows/publish-container.yml`
- Modify: `docker-compose.yml`
- Modify: `docs/vps-deployment.md`
- Modify: `docs/runbook.md`
- Modify: `docs/roadmap.md`
- Modify: `docs/goals/project-completion-state.md`
- Modify: `tests/test_vps_ops.py`

## Task 1: Contract Tests

- [ ] Add `test_github_actions_publishes_container_to_ghcr()` to `tests/test_vps_ops.py`:

```python
def test_github_actions_publishes_container_to_ghcr() -> None:
    workflow = read_text(".github/workflows/publish-container.yml")

    for expected in [
        "ghcr.io/ww-shan/crypto-alpha-agent",
        "permissions:",
        "contents: read",
        "packages: write",
        "docker/login-action",
        "registry: ghcr.io",
        "password: ${{ secrets.GITHUB_TOKEN }}",
        "docker/metadata-action",
        "type=raw,value=main",
        "type=sha,prefix=sha-",
        "type=ref,event=tag",
        "docker/build-push-action",
        "push: true",
    ]:
        assert expected in workflow

    for forbidden in [
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "GHCR_PAT",
        "GHCR_TOKEN",
        "CR_PAT",
        "docker.sock",
    ]:
        assert forbidden not in workflow
```

- [ ] Extend `test_docker_runtime_keeps_secrets_out_of_image_and_mounts_state()` with:

```python
    for expected in [
        "${CRYPTO_ALPHA_AGENT_IMAGE:-ghcr.io/ww-shan/crypto-alpha-agent:main}",
        "build:",
        "context: .",
    ]:
        assert expected in compose
```

- [ ] Extend `test_vps_deployment_doc_documents_outputs_and_boundaries()` with:

```python
        "ghcr.io/ww-shan/crypto-alpha-agent:main",
        "docker compose pull crypto-alpha-agent",
        "docker compose run --rm crypto-alpha-agent llm-health-check",
        "docker login ghcr.io",
        "CRYPTO_ALPHA_AGENT_IMAGE=crypto-alpha-agent:local",
```

- [ ] Run `uv run --extra dev pytest tests/test_vps_ops.py -q`.
- [ ] Verify RED because `.github/workflows/publish-container.yml` does not exist and compose/docs do not yet include GHCR.

## Task 2: GitHub Actions Workflow

- [ ] Create `.github/workflows/publish-container.yml`:

```yaml
name: Publish Container

on:
  push:
    branches:
      - main
    tags:
      - "v*"
  workflow_dispatch:

permissions:
  contents: read
  packages: write

env:
  IMAGE_NAME: ghcr.io/ww-shan/crypto-alpha-agent

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - name: Check out repository
        uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Generate image metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.IMAGE_NAME }}
          tags: |
            type=raw,value=main,enable=${{ github.ref == 'refs/heads/main' }}
            type=sha,prefix=sha-
            type=ref,event=tag

      - name: Build and publish image
        uses: docker/build-push-action@v6
        with:
          context: .
          push: true
          platforms: linux/amd64
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

- [ ] Run `uv run --extra dev pytest tests/test_vps_ops.py::test_github_actions_publishes_container_to_ghcr -q`.
- [ ] Verify the workflow contract passes.

## Task 3: Compose GHCR Default

- [ ] Change `docker-compose.yml` to:

```yaml
services:
  crypto-alpha-agent:
    build:
      context: .
    image: ${CRYPTO_ALPHA_AGENT_IMAGE:-ghcr.io/ww-shan/crypto-alpha-agent:main}
    env_file:
      - .env
    working_dir: /app
    extra_hosts:
      - "host.docker.internal:host-gateway"
    volumes:
      - ./var:/app/var
      - ./.env:/app/.env:ro
    command: ["--help"]
    restart: "no"
```

- [ ] Run `uv run --extra dev pytest tests/test_vps_ops.py::test_docker_runtime_keeps_secrets_out_of_image_and_mounts_state -q`.
- [ ] Verify compose contract passes.

## Task 4: VPS And Operator Docs

- [ ] Update `docs/vps-deployment.md` Build And Smoke Test section to pull GHCR first:

```bash
cd /opt/crypto-alpha-agent
docker compose pull crypto-alpha-agent
docker compose run --rm crypto-alpha-agent llm-health-check
```

- [ ] Add a private-package note:

```bash
docker login ghcr.io -u <github-user>
```

- [ ] Add a local development override:

```bash
CRYPTO_ALPHA_AGENT_IMAGE=crypto-alpha-agent:local docker compose build
CRYPTO_ALPHA_AGENT_IMAGE=crypto-alpha-agent:local \
  docker compose run --rm crypto-alpha-agent llm-health-check
```

- [ ] Update `docs/runbook.md`, `docs/roadmap.md`, and `docs/goals/project-completion-state.md` to record that VPS operation now defaults to GHCR-pulled images and still fails closed on LLM health failures.
- [ ] Run `uv run --extra dev pytest tests/test_vps_ops.py tests/test_documentation_contract.py -q`.
- [ ] Verify focused docs and VPS contracts pass.

## Task 5: Final Verification And Merge Prep

- [ ] Run `uv run --extra dev pytest tests/test_vps_ops.py tests/test_documentation_contract.py -q`.
- [ ] Run `uv run --extra dev pytest -q`.
- [ ] Run `uv run --extra dev ruff check .`.
- [ ] Run `git diff --check`.
- [ ] Stage intended files and run:

```bash
git diff --cached --check
git diff --cached --name-only
git diff --cached --no-ext-diff --unified=0
uv run python -m crypto_alpha_agent.security.secret_scan --staged --fail-on-empty-with-untracked
```

- [ ] Commit with `feat: publish container image to ghcr`.
- [ ] Merge the worktree branch to `main`, push `main`, and inspect the GitHub Actions run that publishes the image.
- [ ] If the local one-day soak remains active in the main worktree, restart or preserve it with `CRYPTO_ALPHA_AGENT_IMAGE=crypto-alpha-agent:local` before the next scheduled loop.
