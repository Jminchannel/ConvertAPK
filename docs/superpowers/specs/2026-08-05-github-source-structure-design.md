# GitHub Source Structure Design

## Goal

Reorganize the source that is currently tracked on GitHub so that contributors can identify each deployable application, build worker, Android template, and business feature without reading generated files or multi-thousand-line entry files. The migration preserves all public HTTP paths, frontend behavior, task data formats, and build modes.

## Scope

This work starts from GitHub `origin/main` only. It does not add the local-only `admin/` or `desktop-electrobun/` directories. The checked-in Electron source remains the only desktop shell in scope.

The migration includes:

- Moving tracked source into application, worker, and template roots.
- Removing tracked generated artifacts, IDE metadata, and the unreferenced legacy worker directory.
- Making the README and Docker Compose configuration accurately describe the tracked source.
- Splitting frontend composition, state, API clients, and feature views by business responsibility.
- Splitting the FastAPI application into an application factory, routers, services, repositories, and domain modules.

The migration does not rewrite Git history, change endpoint URLs, add a state-management library, introduce Vue Router, or change build policy and compliance behavior.

## Target Repository Layout

```text
.
├── apps/
│   ├── web/
│   │   ├── frontend/
│   │   └── backend/
│   └── desktop-electron/
├── workers/
│   └── apk-worker/
├── templates/
│   └── android/
├── docs/
├── scripts/
├── docker-compose.yml
├── docker-compose.windows.yml
├── README.md
└── AGENTS.md
```

`docker-compose.yml`, its Windows override, top-level documentation, and reusable scripts remain at the repository root because they are the primary operational entry points. `build/`, `dist/`, desktop packaging output, and `.idea/` are not source and are removed from Git tracking.

## Source and Operational Moves

| Current path | Target or action | Reason |
| --- | --- | --- |
| `web/` | `apps/web/` | Groups the user-facing application source under one deployable-app root. |
| `desktop/` source files | `apps/desktop-electron/` | Names the supported desktop technology and separates it from generated packages. |
| `apk-worker/` | `workers/apk-worker/` | Makes the Docker build executor distinct from web applications. |
| `templates/HTML2APK/`, `templates/Tubbim/` | `templates/android/HTML2APK/`, `templates/android/Tubbim/` | Makes the template platform explicit. |
| `build-worker-docker/` | Remove | It has no tracked Compose or script consumer; `apk-worker/` is the active worker. |
| `build/`, `dist/`, `desktop/build/`, `desktop/dist/`, `.idea/` | Remove from Git | Generated or machine-local material must not obscure source. |

All Compose build contexts, Dockerfile paths, PowerShell scripts, ignore rules, and README commands must be updated atomically with these moves. Release binaries belong in GitHub Releases; future builds remain ignored by `.gitignore`.

The source does not contain `admin/`. Compose therefore must not attempt to build `admin-backend` or `admin-frontend`. The existing optional admin-client integration remains code-compatible, but deployment documentation must state that a separate configured admin service is required when those optional endpoints are enabled.

## Frontend Design

`src/App.vue` becomes a small composition root: it creates application state once, provides that state context, and renders `app/AppShell.vue`. It no longer contains the complete build form, task screen, or modal templates.

```text
apps/web/frontend/src/
├── app/
│   ├── AppShell.vue
│   └── appStateContext.js
├── features/
│   ├── auth/
│   ├── billing/
│   ├── build/
│   ├── settings/
│   └── tasks/
├── components/
│   ├── layout/
│   └── ui/
├── composables/
│   ├── useAppState.js
│   ├── useAuthState.js
│   ├── useBuildState.js
│   ├── useHtmlEditorState.js
│   ├── useTaskState.js
│   └── useUiState.js
├── api/
│   ├── auth.js
│   ├── build.js
│   ├── files.js
│   ├── tasks.js
│   └── index.js
└── utils/
```

Feature boundaries are:

- `build`: mode selection, ZIP/HTML/URL upload, app configuration, permissions, signing, CDN localization, image cropper, and HTML editor.
- `tasks`: task list, status polling, task actions, output downloads, logs, and diagnosis.
- `auth`: login, registration, SMS, GitHub OAuth, and profile display.
- `billing`: quota retrieval, code redemption, plan display, and Alipay order polling.
- `settings`: announcements, feedback, donation, compliance notice, locale, theme, and desktop-shell controls.

`useAppState` remains the only initializer and composes feature-specific composables in dependency order. It exposes grouped state (`ui`, `build`, `tasks`, `auth`, `billing`) through `appStateContext.js`; feature components consume the single provided instance. This avoids prop drilling and prevents duplicate polling timers or duplicate task state. No Pinia dependency is added.

`api/index.js` remains the public API import surface and re-exports dedicated request modules. Existing request URLs, payload keys, error payload handling, and download helpers stay unchanged.

## Backend Design

```text
apps/web/backend/
├── app/
│   ├── main.py
│   ├── api/
│   │   ├── dependencies.py
│   │   └── routes/
│   │       ├── auth.py
│   │       ├── uploads.py
│   │       ├── tasks.py
│   │       ├── task_files.py
│   │       ├── task_logs.py
│   │       ├── runtime.py
│   │       └── admin_hub.py
│   ├── core/
│   │   ├── config.py
│   │   └── lifecycle.py
│   ├── domain/
│   │   └── models.py
│   ├── repositories/
│   │   ├── task_repository.py
│   │   └── user_repository.py
│   └── services/
│       ├── auth_service.py
│       ├── task_service.py
│       ├── upload_service.py
│       ├── risk_guard_service.py
│       ├── output_service.py
│       └── admin_client_service.py
├── tests/
└── requirements.txt
```

`app/main.py` creates the FastAPI application, registers middleware and lifecycle hooks, mounts static assets, and includes routers. Routers only parse HTTP inputs and map service results to existing response models. Services own business operations; repositories own JSON/Redis/file persistence access. Application services are created once during startup and retrieved from `request.app.state`, so routers do not import `main.py` and no circular imports are introduced.

The following route groups keep their existing paths and response formats: authentication, upload and scan, task lifecycle, task files, logs and diagnosis, runtime/environment, and optional admin-hub/payment endpoints. The published ASGI command is updated from the old flat module path to `app.main:app`.

## Verification Strategy

- Add a backend route-contract test that imports `app.main:app` and verifies every currently published route path and HTTP method remains registered.
- Keep and run existing backend tests, including runtime safety, compliance hardening, and signature-verification contract tests.
- Add focused frontend tests for state-context single initialization and API barrel exports; run the production Vite build to validate every extracted component import.
- Run `docker compose -f docker-compose.yml config` and the Windows override configuration check after every path move.
- Verify README commands and the documented tree against the final tracked paths.

## Migration Sequence

1. Establish directory and deployment-path contract tests.
2. Remove generated tracked content and unused worker source, then move root source directories and update operational references.
3. Extract frontend API modules, state composables, feature components, and the thin `App.vue` composition root without changing UI behavior.
4. Extract backend domain, repository, service, and router modules while retaining the HTTP contract.
5. Run complete regression verification and update the repository documentation.
