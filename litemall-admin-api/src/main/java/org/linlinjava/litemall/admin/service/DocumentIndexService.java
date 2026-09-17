package org.linlinjava.litemall.admin.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.*;

@Service
public class DocumentIndexService {
    private static final String RELEASE = "litemall_document_index_release";
    private static final String ITEM = "litemall_document_index_item";
    private final JdbcTemplate db;
    private final ObjectMapper json;
    private final Path documentRoot;
    private final Path indexRoot;
    private final Path python;
    private final Path script;
    private final String baseIndexPath;
    private final String pipelineVersion;

    public DocumentIndexService(JdbcTemplate db, ObjectMapper json,
            @Value("${document-library.root:storage/document-library}") String documentRoot,
            @Value("${document-library.index-root:storage/document-library/policy-index}") String indexRoot,
            @Value("${document-library.python:ai-service/.venv/Scripts/python.exe}") String python,
            @Value("${document-library.index-script:ai-service/scripts/document_index_worker.py}") String script,
            @Value("${document-library.base-policy-index:ai-service/data/policy_rag_real/index/policy_chunks.jsonl}") String baseIndexPath,
            @Value("${document-library.pipeline-version:document-parse-v2}") String pipelineVersion) {
        this.db = db;
        this.json = json;
        this.documentRoot = Paths.get(documentRoot).toAbsolutePath().normalize();
        this.indexRoot = Paths.get(indexRoot).toAbsolutePath().normalize();
        this.python = Paths.get(python).toAbsolutePath().normalize();
        this.script = Paths.get(script).toAbsolutePath().normalize();
        this.baseIndexPath = Paths.get(baseIndexPath).toAbsolutePath().normalize().toString();
        this.pipelineVersion = pipelineVersion;
    }

    @org.springframework.transaction.annotation.Transactional(rollbackFor = Exception.class)
    public synchronized Map<String, Object> createCandidate(String operator) throws Exception {
        List<Map<String, Object>> running = db.queryForList("SELECT * FROM " + RELEASE + " WHERE status IN ('queued','building') ORDER BY created_at DESC LIMIT 1");
        if (!running.isEmpty()) return publicRow(running.get(0));
        List<Map<String, Object>> documents = latestDocumentsBySource(db.queryForList(
                "SELECT id,result_path,file_name,source_name,source_url,file_hash,created_at,updated_at FROM litemall_document_job WHERE status='parsed' AND usage_type='policy_candidate' AND pipeline_version=? ORDER BY updated_at DESC,created_at DESC,id DESC",
                pipelineVersion));
        List<Map<String, Object>> active = db.queryForList("SELECT * FROM " + RELEASE + " WHERE status='active' ORDER BY created_at DESC LIMIT 1");
        if (documents.isEmpty() && active.isEmpty()) throw new IllegalArgumentException("NO_PARSED_POLICY_CANDIDATE");
        Set<String> desiredDocumentIds = documentIds(documents);
        if (!active.isEmpty() && hasCurrentEvaluation(active.get(0))
                && desiredDocumentIds.equals(documentIdsForRelease(String.valueOf(active.get(0).get("id")))))
            return noOpRow(active.get(0));
        for (Map<String, Object> ready : db.queryForList("SELECT * FROM " + RELEASE + " WHERE status='ready' ORDER BY created_at DESC")) {
            if (hasCurrentEvaluation(ready)
                    && desiredDocumentIds.equals(documentIdsForRelease(String.valueOf(ready.get("id"))))) return noOpRow(ready);
        }
        String id = UUID.randomUUID().toString();
        String version = "policy-" + LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyyMMdd'T'HHmmss")) + "-" + id.substring(0, 8);
        Path releaseDir = documentRoot.resolve("index-releases").resolve(id);
        Files.createDirectories(releaseDir);
        Path request = releaseDir.resolve("request.json");
        List<Map<String, Object>> inputs = new ArrayList<>();
        for (Map<String, Object> document : documents) {
            Map<String, Object> input = new LinkedHashMap<>();
            input.put("documentId", document.get("id"));
            input.put("resultPath", document.get("result_path"));
            input.put("sourceName", document.get("source_name"));
            input.put("sourceUrl", document.get("source_url"));
            input.put("fileHash", document.get("file_hash"));
            inputs.add(input);
        }
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("schemaVersion", "document-policy-index-request-v1");
        payload.put("releaseId", id);
        payload.put("version", version);
        payload.put("documentRoot", documentRoot.toString());
        payload.put("indexRoot", indexRoot.toString());
        payload.put("baseIndexPath", baseIndexPath);
        payload.put("denseRequired", true);
        payload.put("allowEmptyUploads", true);
        payload.put("documents", inputs);
        writeAtomic(request, json.writeValueAsBytes(payload));
        String relative = documentRoot.relativize(request).toString().replace('\\', '/');
        try {
            db.update("INSERT INTO " + RELEASE + " (id,version,status,document_count,request_path,requested_by,created_at,updated_at) VALUES (?,?, 'queued', ?,?,?,NOW(),NOW())",
                    id, version, documents.size(), relative, operator);
            for (Map<String, Object> document : documents)
                db.update("INSERT INTO " + ITEM + " (release_id,document_id) VALUES (?,?)", id, document.get("id"));
        } catch (Exception failure) {
            Files.deleteIfExists(request);
            Files.deleteIfExists(releaseDir);
            throw failure;
        }
        return detail(id);
    }

    public Map<String, Object> summary() {
        List<Map<String, Object>> rows = db.queryForList("SELECT * FROM " + RELEASE + " ORDER BY created_at DESC LIMIT 10");
        List<Map<String, Object>> releases = new ArrayList<>();
        for (Map<String, Object> row : rows) releases.add(publicRow(row));
        List<Map<String, Object>> activeRows = db.queryForList("SELECT * FROM " + RELEASE + " WHERE status='active' ORDER BY created_at DESC LIMIT 1");
        List<Map<String, Object>> candidateRows = db.queryForList("SELECT * FROM " + RELEASE + " WHERE status IN ('queued','building','ready','failed') ORDER BY created_at DESC LIMIT 1");
        Map<String, Object> result = new LinkedHashMap<>();
        Map<String, Object> activeRelease = activeRows.isEmpty() ? null : publicRow(activeRows.get(0));
        result.put("active", activeRelease);
        result.put("candidate", candidateRows.isEmpty() ? null : publicRow(candidateRows.get(0)));
        result.put("releases", releases);
        result.put("activeRelease", activeRelease);
        result.put("candidateRelease", selectCandidateRelease(releases));
        result.put("comparableRelease", selectComparableRelease(releases));
        result.put("historyReleases", releases);
        List<Map<String, Object>> currentDocuments = latestDocumentsBySource(db.queryForList(
                "SELECT id,file_name,source_name,source_url,created_at,updated_at FROM litemall_document_job WHERE status='parsed' AND usage_type='policy_candidate' AND pipeline_version=? ORDER BY updated_at DESC,created_at DESC,id DESC",
                pipelineVersion));
        result.put("parsedPolicyCandidates", currentDocuments.size());
        Set<String> desiredIds = documentIds(currentDocuments);
        Optional<Map<String, Object>> active = activeRows.stream().findFirst();
        result.put("hasUnpublishedChanges", !active.isPresent()
                ? !desiredIds.isEmpty()
                : !desiredIds.equals(documentIdsForRelease(String.valueOf(active.get().get("id")))));
        return result;
    }

    static Map<String, Object> selectCandidateRelease(List<Map<String, Object>> releases) {
        for (Map<String, Object> release : releases) {
            String status = String.valueOf(release.get("status"));
            if ("queued".equals(status) || "building".equals(status)) return release;
            if (("ready".equals(status) || "failed".equals(status))
                    && Boolean.TRUE.equals(release.get("evaluationAvailable"))) return release;
        }
        return null;
    }

    static Map<String, Object> selectComparableRelease(List<Map<String, Object>> releases) {
        for (Map<String, Object> release : releases) {
            String status = String.valueOf(release.get("status"));
            if (!("ready".equals(status) || "superseded".equals(status))) continue;
            if (!Boolean.TRUE.equals(release.get("evaluationAvailable"))) continue;
            Object rawEvaluation = release.get("releaseEvaluation");
            if (!(rawEvaluation instanceof Map)) continue;
            Map<?, ?> evaluation = (Map<?, ?>) rawEvaluation;
            if (Boolean.TRUE.equals(evaluation.get("gatePassed"))
                    && !"blocked".equals(evaluation.get("decision"))) return release;
        }
        return null;
    }

    public Map<String, Object> detail(String id) {
        List<Map<String, Object>> rows = db.queryForList("SELECT * FROM " + RELEASE + " WHERE id=?", id);
        if (rows.isEmpty()) throw new IllegalArgumentException("INDEX_RELEASE_NOT_FOUND");
        return publicRow(rows.get(0));
    }

    @org.springframework.transaction.annotation.Transactional(rollbackFor = Exception.class)
    public synchronized Map<String, Object> publish(String id, String operator) throws Exception {
        Map<String, Object> row = raw(id);
        if ("active".equals(row.get("status"))) return publicRow(row);
        if (!"ready".equals(row.get("status"))) throw new IllegalArgumentException("INDEX_RELEASE_NOT_READY");
        if (!Boolean.TRUE.equals(publicRow(row).get("canPublish")))
            throw new IllegalArgumentException("INDEX_RELEASE_EVALUATION_NOT_PASSED");
        String previous = activeVersion();
        runLifecycle("--publish", String.valueOf(row.get("version")));
        try {
            db.update("UPDATE " + RELEASE + " SET status='superseded',updated_at=NOW() WHERE status='active' AND id<>?", id);
            int updated = db.update("UPDATE " + RELEASE + " SET status='active',published_by=?,published_at=NOW(),updated_at=NOW() WHERE id=? AND status='ready'", operator, id);
            if (updated != 1) throw new IllegalStateException("INDEX_PUBLISH_CONFLICT");
        } catch (Exception failure) {
            if (!previous.isEmpty()) runLifecycle("--rollback", previous);
            else runLifecycle("--deactivate", String.valueOf(row.get("version")));
            throw failure;
        }
        return detail(id);
    }

    @org.springframework.transaction.annotation.Transactional(rollbackFor = Exception.class)
    public synchronized Map<String, Object> rollback(String id, String operator) throws Exception {
        Map<String, Object> row = raw(id);
        if (!"superseded".equals(row.get("status"))) throw new IllegalArgumentException("INDEX_ROLLBACK_TARGET_INVALID");
        String previous = activeVersion();
        runLifecycle("--rollback", String.valueOf(row.get("version")));
        try {
            db.update("UPDATE " + RELEASE + " SET status='superseded',updated_at=NOW() WHERE status='active'");
            db.update("UPDATE " + RELEASE + " SET status='active',published_by=?,published_at=NOW(),updated_at=NOW() WHERE id=?", operator, id);
        } catch (Exception failure) {
            if (!previous.isEmpty()) runLifecycle("--rollback", previous);
            throw failure;
        }
        return detail(id);
    }

    @org.springframework.transaction.annotation.Transactional(rollbackFor = Exception.class)
    public synchronized Map<String, Object> restoreBase(String operator) throws Exception {
        List<Map<String, Object>> activeRows = db.queryForList(
                "SELECT * FROM " + RELEASE + " WHERE status='active' ORDER BY created_at DESC LIMIT 1");
        if (activeRows.isEmpty()) {
            Map<String, Object> result = summary();
            result.put("restoredBase", true);
            result.put("noOp", true);
            result.put("previousVersion", "");
            return result;
        }
        Map<String, Object> active = activeRows.get(0);
        String id = String.valueOf(active.get("id"));
        String version = String.valueOf(active.get("version"));
        runLifecycle("--deactivate", version);
        try {
            int updated = db.update("UPDATE " + RELEASE + " SET status='superseded',updated_at=NOW() WHERE id=? AND status='active'", id);
            if (updated != 1) throw new IllegalStateException("INDEX_RESTORE_BASE_CONFLICT");
        } catch (Exception failure) {
            runLifecycle("--rollback", version);
            throw failure;
        }
        Map<String, Object> result = summary();
        result.put("restoredBase", true);
        result.put("noOp", false);
        result.put("previousVersion", version);
        result.put("restoredBy", operator);
        return result;
    }

    private String activeVersion() {
        List<String> versions = db.query("SELECT version FROM " + RELEASE + " WHERE status='active' LIMIT 1",
                (result, row) -> result.getString(1));
        return versions.isEmpty() ? "" : versions.get(0);
    }

    public Map<String, Object> claim() {
        db.update("UPDATE " + RELEASE + " SET status=IF(attempts>=3,'failed','queued'),lease_token=NULL,lease_until=NULL,error_code='INDEX_WORKER_INTERRUPTED',updated_at=NOW() WHERE status='building' AND lease_until<NOW()");
        for (Map<String, Object> item : db.queryForList("SELECT id FROM " + RELEASE + " WHERE status='queued' AND attempts<3 ORDER BY created_at,id LIMIT 5")) {
            String id = String.valueOf(item.get("id"));
            String token = UUID.randomUUID().toString();
            if (db.update("UPDATE " + RELEASE + " SET status='building',attempts=attempts+1,lease_token=?,lease_until=DATE_ADD(NOW(),INTERVAL 120 SECOND),updated_at=NOW() WHERE id=? AND status='queued' AND attempts<3", token, id) != 1)
                continue;
            Map<String, Object> row = raw(id);
            Map<String, Object> task = publicRow(row);
            task.put("leaseToken", token);
            task.put("root", documentRoot.toString());
            task.put("requestPath", row.get("request_path"));
            return task;
        }
        return null;
    }

    public boolean heartbeat(String id, String token) {
        return db.update("UPDATE " + RELEASE + " SET lease_until=DATE_ADD(NOW(),INTERVAL 120 SECOND),updated_at=NOW() WHERE id=? AND lease_token=? AND status='building' AND lease_until>=NOW()", id, token) == 1;
    }

    public boolean finish(String id, String token, String errorCode) throws Exception {
        String relative = "index-releases/" + id + "/" + token + "/build-result.json";
        if (errorCode == null || errorCode.isEmpty()) {
            Map<?, ?> result = readBuildResult(relative, id);
            Map<?, ?> dense = result.get("dense") instanceof Map ? (Map<?, ?>) result.get("dense") : Collections.emptyMap();
            Map<?, ?> evaluation = releaseEvaluation(result);
            if (!"PASS".equals(result.get("gate")) || !"ready".equals(dense.get("status"))
                    || !Boolean.TRUE.equals(evaluation.get("gatePassed")))
                throw new IllegalArgumentException("INDEX_BUILD_RESULT_INVALID");
            Number chunks = (Number) result.get("chunkCount");
            return db.update("UPDATE " + RELEASE + " SET status='ready',chunk_count=?,dense_status='ready',quality_gate='PASS',result_path=?,error_code=NULL,lease_until=NULL,updated_at=NOW() WHERE id=? AND lease_token=? AND status='building' AND lease_until>=NOW()",
                    chunks.intValue(), relative, id, token) == 1;
        }
        if (!errorCode.matches("[A-Z0-9_]{1,100}")) throw new IllegalArgumentException("INDEX_ERROR_CODE_INVALID");
        Path resultPath = documentRoot.resolve(relative).normalize();
        if (Files.isRegularFile(resultPath)) {
            Map<?, ?> result = readBuildResult(relative, id);
            Map<?, ?> dense = result.get("dense") instanceof Map ? (Map<?, ?>) result.get("dense") : Collections.emptyMap();
            Number chunks = result.get("chunkCount") instanceof Number ? (Number) result.get("chunkCount") : 0;
            String denseStatus = "ready".equals(dense.get("status")) ? "ready" : "failed";
            return db.update("UPDATE " + RELEASE + " SET status='failed',chunk_count=?,dense_status=?,quality_gate='FAIL',result_path=?,error_code=?,lease_until=NULL,updated_at=NOW() WHERE id=? AND lease_token=? AND status='building' AND lease_until>=NOW()",
                    chunks.intValue(), denseStatus, relative, errorCode, id, token) == 1;
        }
        return db.update("UPDATE " + RELEASE + " SET status='failed',dense_status='failed',quality_gate='FAIL',error_code=?,lease_until=NULL,updated_at=NOW() WHERE id=? AND lease_token=? AND status='building' AND lease_until>=NOW()",
                errorCode, id, token) == 1;
    }

    private Map<String, Object> raw(String id) {
        List<Map<String, Object>> rows = db.queryForList("SELECT * FROM " + RELEASE + " WHERE id=?", id);
        if (rows.isEmpty()) throw new IllegalArgumentException("INDEX_RELEASE_NOT_FOUND");
        return rows.get(0);
    }

    private Map<String, Object> publicRow(Map<String, Object> row) {
        Map<String, Object> result = new LinkedHashMap<>();
        String[][] fields = {{"id","id"},{"version","version"},{"status","status"},{"documentCount","document_count"},
                {"chunkCount","chunk_count"},{"denseStatus","dense_status"},{"qualityGate","quality_gate"},
                {"errorCode","error_code"},{"requestedBy","requested_by"},{"publishedBy","published_by"},
                {"publishedAt","published_at"},{"createdAt","created_at"},{"updatedAt","updated_at"}};
        for (String[] pair : fields) result.put(pair[0], row.get(pair[1]));
        Map<?, ?> buildResult = buildResult(row);
        Map<?, ?> evaluation = releaseEvaluation(buildResult);
        boolean evaluationAvailable = "policy-release-evaluation-v1".equals(evaluation.get("schemaVersion"));
        boolean evaluationPassed = evaluationAvailable && Boolean.TRUE.equals(evaluation.get("gatePassed"))
                && !"blocked".equals(evaluation.get("decision"));
        result.put("evaluationAvailable", evaluationAvailable);
        result.put("evaluationMissing", !evaluationAvailable && ("ready".equals(row.get("status")) || "failed".equals(row.get("status"))));
        result.put("releaseEvaluation", evaluationAvailable ? evaluation : null);
        result.put("canPublish", "ready".equals(row.get("status")) && evaluationPassed);
        result.put("canRollback", "superseded".equals(row.get("status")));
        return result;
    }

    private boolean hasCurrentEvaluation(Map<String, Object> row) {
        return "policy-release-evaluation-v1".equals(releaseEvaluation(buildResult(row)).get("schemaVersion"));
    }

    private Map<?, ?> buildResult(Map<String, Object> row) {
        Object relative = row.get("result_path");
        if (relative == null || String.valueOf(relative).trim().isEmpty()) return Collections.emptyMap();
        try {
            return json.readValue(safeFile(String.valueOf(relative)).toFile(), Map.class);
        } catch (Exception ignored) {
            return Collections.emptyMap();
        }
    }

    private Map<?, ?> readBuildResult(String relative, String releaseId) throws Exception {
        Map<?, ?> result = json.readValue(safeFile(relative).toFile(), Map.class);
        if (!releaseId.equals(result.get("releaseId"))) throw new IllegalArgumentException("INDEX_BUILD_RESULT_INVALID");
        return result;
    }

    private static Map<?, ?> releaseEvaluation(Map<?, ?> result) {
        Object value = result.get("releaseEvaluation");
        return value instanceof Map ? (Map<?, ?>) value : Collections.emptyMap();
    }

    private Map<String, Object> noOpRow(Map<String, Object> row) {
        Map<String, Object> result = publicRow(row);
        result.put("noOp", true);
        return result;
    }

    static List<Map<String, Object>> latestDocumentsBySource(List<Map<String, Object>> rows) {
        List<Map<String, Object>> selected = new ArrayList<>();
        Set<String> sources = new HashSet<>();
        for (Map<String, Object> row : rows) {
            String source = logicalSourceKey(row.get("source_url"), row.get("source_name"), row.get("file_name"));
            if (sources.add(source)) selected.add(row);
        }
        Collections.reverse(selected);
        return selected;
    }

    static String logicalSourceKey(Object sourceUrl, Object sourceName, Object fileName) {
        String url = sourceUrl == null ? "" : String.valueOf(sourceUrl).trim();
        if (!url.isEmpty()) return "url:" + url.toLowerCase(Locale.ROOT);
        String name = sourceName == null ? "" : String.valueOf(sourceName).trim().replaceAll("\\s+", " ");
        String file = fileName == null ? "" : String.valueOf(fileName).trim();
        return "name:" + name.toLowerCase(Locale.ROOT) + "|file:" + file.toLowerCase(Locale.ROOT);
    }

    private static Set<String> documentIds(List<Map<String, Object>> documents) {
        Set<String> ids = new LinkedHashSet<>();
        for (Map<String, Object> document : documents) ids.add(String.valueOf(document.get("id")));
        return ids;
    }

    private Set<String> documentIdsForRelease(String releaseId) {
        return new LinkedHashSet<>(db.query("SELECT document_id FROM " + ITEM + " WHERE release_id=? ORDER BY document_id",
                new Object[]{releaseId}, (result, row) -> result.getString(1)));
    }

    private Path safeFile(String relative) throws Exception {
        Path path = documentRoot.resolve(relative).normalize();
        if (!path.startsWith(documentRoot) || !path.toRealPath().startsWith(documentRoot.toRealPath()))
            throw new IllegalArgumentException("INDEX_ARTIFACT_PATH_INVALID");
        return path;
    }

    private void runLifecycle(String operation, String version) throws Exception {
        if (!Files.isRegularFile(python) || !Files.isRegularFile(script)) throw new IllegalStateException("INDEX_RUNTIME_NOT_AVAILABLE");
        Process process = new ProcessBuilder(python.toString(), script.toString(), operation, indexRoot.toString(), version)
                .redirectErrorStream(true).start();
        ByteArrayOutputStream output = new ByteArrayOutputStream();
        try (InputStream stream = process.getInputStream()) {
            byte[] buffer = new byte[4096];
            int count;
            while ((count = stream.read(buffer)) != -1 && output.size() < 1024 * 1024) output.write(buffer, 0, count);
        }
        if (!process.waitFor(30, java.util.concurrent.TimeUnit.SECONDS)) {
            process.destroyForcibly();
            throw new IllegalStateException("INDEX_LIFECYCLE_TIMEOUT");
        }
        if (process.exitValue() != 0) throw new IllegalStateException("INDEX_LIFECYCLE_FAILED");
    }

    private static void writeAtomic(Path target, byte[] bytes) throws Exception {
        Path temporary = Files.createTempFile(target.getParent(), "request-", ".tmp");
        Files.write(temporary, bytes, StandardOpenOption.TRUNCATE_EXISTING);
        try {
            Files.move(temporary, target, StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
        } catch (AtomicMoveNotSupportedException ignored) {
            Files.move(temporary, target, StandardCopyOption.REPLACE_EXISTING);
        }
    }
}
