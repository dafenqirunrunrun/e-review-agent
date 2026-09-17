# Local Deployment Runbook

Local service order:

1. MySQL
2. AI service
3. wx-api
4. admin-api
5. litemall-vue
6. litemall-admin

Optional Docker Compose profile:

```powershell
cd D:\EReviewAgent\litemall\docker
docker compose --profile ai-service up ai-service
```

Do not place secrets, absolute adapter paths, checkpoint files, or `data-private` contents in Git or Docker images. The adapter directory, when used locally, should be mounted read-only.
