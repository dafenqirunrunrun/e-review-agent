# E-Review Agent v2.0 Default Test Debt Audit

## Scope

This audit freezes the default local Maven test debt found during v2.0 release candidate hardening. It only covers tests that block reproducible local verification and does not change production code, business logic, interfaces, or database schema.

## Baseline Failure

Command:

```powershell
mvn test -DskipTests=false
```

Observed failures before remediation:

| Module | Test | Failure Type | Root Cause |
| --- | --- | --- | --- |
| `litemall-core` | `AliyunStorageTest` | error | External object storage integration test ran by default without verified cloud credentials and bucket state. |
| `litemall-core` | `QiniuStorageTest` | error | External object storage integration test ran by default without verified cloud credentials and bucket state. |
| `litemall-core` | `TencentStorageTest` | error | External object storage integration test ran by default without verified cloud credentials and bucket state. |
| `litemall-core` | `BCryptTest` | error | PowerMock/Objenesis test runner is incompatible with the current JDK reflective access model. |
| `litemall-admin-api` | `CreateShareImageTest` | error | Test assumed a fixed goods ID existed in the local database. Clean or evolved demo databases may not contain that row. |

## Remediation

External object storage tests now behave as integration tests:

- They are skipped by default in a clean local environment.
- They can be enabled explicitly with either `E_REVIEW_EXTERNAL_STORAGE_TESTS=true` or `-De.review.external.storage.tests=true`.
- Each provider also requires its provider-specific environment variables.
- They are not marked with unconditional ignore annotations, so a maintainer can still run the real integration path intentionally.

Required provider variables:

| Provider | Required Variables |
| --- | --- |
| Aliyun | `LITEMALL_STORAGE_ALIYUN_ENDPOINT`, `LITEMALL_STORAGE_ALIYUN_ACCESS_KEY_ID`, `LITEMALL_STORAGE_ALIYUN_ACCESS_KEY_SECRET`, `LITEMALL_STORAGE_ALIYUN_BUCKET_NAME` |
| Qiniu | `LITEMALL_STORAGE_QINIU_ENDPOINT`, `LITEMALL_STORAGE_QINIU_ACCESS_KEY`, `LITEMALL_STORAGE_QINIU_SECRET_KEY`, `LITEMALL_STORAGE_QINIU_BUCKET_NAME` |
| Tencent | `LITEMALL_STORAGE_TENCENT_SECRET_ID`, `LITEMALL_STORAGE_TENCENT_SECRET_KEY`, `LITEMALL_STORAGE_TENCENT_REGION`, `LITEMALL_STORAGE_TENCENT_BUCKET_NAME` |

`BCryptTest` no longer uses PowerMock. It keeps deterministic hash validation, invalid salt validation, generated salt format validation, and password verification coverage without altering the BCrypt implementation.

`CreateShareImageTest` now selects an available local goods fixture instead of a fixed goods ID. If the local database has no goods rows, the test is skipped with an explicit reason. The default share-image production switch remains unchanged.

## Verification

Default local gate:

```powershell
D:\anaconda\envs\torchtest\python.exe scripts\readiness\run_default_maven_test_gate.py
```

Expected tokens:

```text
E_REVIEW_DEFAULT_MAVEN_TEST_PASS
E_REVIEW_EXTERNAL_STORAGE_TESTS_SKIPPED_WITHOUT_CREDENTIALS
```

Boundary:

- External cloud provider correctness is not claimed unless those tests are explicitly enabled with real credentials.
- Share image generation against a live WeChat Mini Program provider is not claimed when the production switch is disabled.
- No production business logic was modified in this cleanup.
