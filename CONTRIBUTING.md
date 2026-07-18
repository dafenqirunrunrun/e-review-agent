# Contributing

Thanks for your interest in E-Review Agent.

This repository is published as a learning, graduation-project and engineering-portfolio snapshot. Contributions are welcome for documentation, reproducible tests, build scripts and small bug fixes.

## Guidelines

- Do not submit secrets, tokens, passwords, private keys or real user data.
- Do not add model weights, checkpoints, FAISS indexes or private datasets.
- Keep payment, logistics and refund behavior clearly marked as demo mode unless a full security and compliance review is completed.
- Prefer small pull requests with clear test evidence.

## Local Checks

```bash
mvn -DskipTests package
cd ai-service && python -m pytest
cd ../litemall-admin && npm run build:prod
cd ../litemall-vue && npm run build:prod
```
