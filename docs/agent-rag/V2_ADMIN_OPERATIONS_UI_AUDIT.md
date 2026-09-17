# V2 Admin Operations UI Audit

## Admin Project

```text
path: litemall-admin
stack: Vue 2.6.10, Element UI 2.15.6, Vue Router, Vuex, Axios
build: npm run build:prod
unit: npm run test:unit -- --runInBand tests/unit/agent-rag.spec.js
```

The implementation reuses the existing litemall admin shell, request wrapper,
permission directive, route metadata, Element UI tables/forms/dialogs, and
`Pagination` component.

## Reused Conventions

- API calls are centralized in `src/api/agentRag.js`.
- Display conversion is centralized in `src/utils/agent-rag.js`.
- Routes use existing lazy-loaded route definitions in `src/router/index.js`.
- Buttons use `v-permission` for override and replay actions.
- The UI avoids `v-html`, full evidence copying, local model paths, and local
  storage of evidence bundles.

## New Routes

```text
/agent-rag/overview
/agent-rag/runs
/agent-rag/runs/:id
/agent-rag/runtime
```

## UI Style

The pages use the existing Element UI operational dashboard style: restrained
cards, compact filters, bordered tables, explicit tags, loading states, error
alerts, and empty states. No new charting or large frontend dependency was
introduced.
