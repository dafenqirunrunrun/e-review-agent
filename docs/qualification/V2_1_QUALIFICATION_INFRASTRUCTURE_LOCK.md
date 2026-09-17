# v2.1 Qualification Infrastructure Lock

## Locked Baseline

- Infrastructure commit: `2d160578c381cd701f90cbcf57b4a682959a2988`
- Source archive SHA-256: `C8AD2FEAB7652837C0E0069963C4DAF2183592DF94004FE67951A16BC7372557`
- Archive location: external qualification directory, not committed to Git

## Locked Evidence

- Python default: `488 passed, 12 skipped, 0 failed`
- Java `mvn test -DskipTests=false`: PASS
- Java `mvn -DskipTests package`: PASS
- Admin `npm run build:prod`: PASS
- Customer `npm run build:prod`: PASS
- Migration immutability: PASS
- Cross-platform checksum: PASS
- v2.0 RC compatibility: PASS
- v2.1 qualification infrastructure gate: PASS

## Frozen Worktrees

- v2.0 RC: `D:\EReviewAgent\litemall` at `ffd05f2611cf2c7996a681fa0343778da73f7e50`
- v2.1 infrastructure: `D:\EReviewAgent\litemall-quality-scale` at `2d160578c381cd701f90cbcf57b4a682959a2988`
- v2.1 infrastructure verify: `D:\EReviewAgent\litemall-quality-scale-verify`

These worktrees are treated as read-only baselines for blocker closure.
