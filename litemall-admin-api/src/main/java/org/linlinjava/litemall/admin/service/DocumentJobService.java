package org.linlinjava.litemall.admin.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.ClassPathResource;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.init.ResourceDatabasePopulator;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import javax.annotation.PostConstruct;
import java.io.*;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;

@Service
public class DocumentJobService {
    public static final long MAX_BYTES = 20L * 1024 * 1024;
    private static final String TABLE = "litemall_document_job";
    private static final Set<String> LIGHT_EXTENSIONS = new HashSet<>(Arrays.asList(
            "html", "htm", "md", "markdown", "txt", "csv", "xlsx"));
    private static final String LIGHT_QUEUE_SQL =
            "LOWER(SUBSTRING_INDEX(file_name,'.',-1)) IN ('html','htm','md','markdown','txt','csv','xlsx')";
    private final JdbcTemplate db;
    private final ObjectMapper json;
    private final Path root;
    private final String version;

    public DocumentJobService(JdbcTemplate db, ObjectMapper json,
            @Value("${document-library.root:storage/document-library}") String root,
            @Value("${document-library.pipeline-version:document-parse-v2}") String version) {
        this.db = db;
        this.json = json;
        this.root = Paths.get(root).toAbsolutePath().normalize();
        this.version = version;
    }

    @PostConstruct
    public void initialize() throws IOException {
        Files.createDirectories(root);
        new ResourceDatabasePopulator(new ClassPathResource("document-library.sql")).execute(db.getDataSource());
    }

    public static String extension(String name) {
        if (name == null || name.length() > 255 || name.contains("/") || name.contains("\\")
                || name.matches(".*[\\p{Cntrl}].*")) throw new IllegalArgumentException("FILE_NAME_INVALID");
        String ext = name.substring(name.lastIndexOf('.') + 1).toLowerCase(Locale.ROOT);
        if (!Arrays.asList("pdf", "docx", "pptx", "xlsx", "html", "htm", "md", "markdown", "txt", "csv",
                "png", "jpg", "jpeg", "tif", "tiff", "webp").contains(ext))
            throw new IllegalArgumentException("FILE_FORMAT_UNSUPPORTED");
        return ext;
    }

    public static String executionClass(String name) {
        return LIGHT_EXTENSIONS.contains(extension(name)) ? "light" : "heavy";
    }

    public Map<String, Object> upload(MultipartFile file, String sourceName, String sourceUrl,
                                      String usageType, String operator) throws Exception {
        String name = file.getOriginalFilename();
        String ext = extension(name);
        if (file.isEmpty() || file.getSize() > MAX_BYTES) throw new IllegalArgumentException("FILE_SIZE_INVALID");
        sourceName = sourceName == null || sourceName.trim().isEmpty() ? name : sourceName.trim();
        sourceUrl = sourceUrl == null ? "" : sourceUrl.trim();
        if (sourceName.length() > 255 || sourceUrl.length() > 2048) throw new IllegalArgumentException("SOURCE_INVALID");
        if (!sourceUrl.isEmpty()) {
            URI uri = URI.create(sourceUrl);
            if (!("https".equals(uri.getScheme()) || "http".equals(uri.getScheme()))
                    || uri.getHost() == null || uri.getUserInfo() != null) throw new IllegalArgumentException("SOURCE_URL_INVALID");
        }
        if (!Arrays.asList("reference", "policy_candidate", "historical_case").contains(usageType))
            throw new IllegalArgumentException("USAGE_TYPE_INVALID");
        String id = UUID.randomUUID().toString();
        Path directory = root.resolve(id);
        Files.createDirectories(directory);
        Path input = directory.resolve("original." + ext);
        boolean committed = false;
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            long size = 0;
            try (InputStream in = file.getInputStream(); OutputStream out = Files.newOutputStream(input, StandardOpenOption.CREATE_NEW)) {
                byte[] buffer = new byte[8192];
                int count;
                while ((count = in.read(buffer)) != -1) {
                    size += count;
                    if (size > MAX_BYTES) throw new IllegalArgumentException("FILE_SIZE_INVALID");
                    digest.update(buffer, 0, count);
                    out.write(buffer, 0, count);
                }
            }
            String hash = hex(digest.digest());
            String key = hex(MessageDigest.getInstance("SHA-256").digest(json.writeValueAsBytes(
                    Arrays.asList(hash, ext, sourceName, sourceUrl, usageType, version))));
            try {
                db.update("INSERT INTO " + TABLE + " (id,dedup_key,file_name,file_hash,size_bytes,source_name,source_url,usage_type,pipeline_version,input_path,operator_name,available_at,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,NOW(),NOW(),NOW())",
                        id, key, name, hash, size, sourceName, sourceUrl, usageType, version,
                        id + "/original." + ext, operator);
                committed = true;
            } catch (DuplicateKeyException duplicate) {
                Files.deleteIfExists(input);
                Files.deleteIfExists(directory);
                String existing = db.queryForObject("SELECT id FROM " + TABLE + " WHERE dedup_key=?", String.class, key);
                db.update("UPDATE " + TABLE + " SET status='queued',attempts=0,lease_token=NULL,lease_until=NULL,available_at=NOW(),result_path=NULL,error_code=NULL,operator_name=?,updated_at=NOW() WHERE id=? AND status='removed'",
                        operator, existing);
                return detail(existing);
            }
            return detail(id);
        } catch (Exception failure) {
            // Only remove this upload's private directory if the durable insert did not commit.
            if (!committed) {
                Files.deleteIfExists(input);
                Files.deleteIfExists(directory);
            }
            throw failure;
        }
    }

    private Map<String, Object> row(String id) {
        List<Map<String, Object>> rows = db.queryForList("SELECT * FROM " + TABLE + " WHERE id=?", id);
        if (rows.isEmpty()) throw new IllegalArgumentException("TASK_NOT_FOUND");
        return rows.get(0);
    }

    public Map<String, Object> detail(String id) { return publicRow(row(id)); }

    private Map<String, Object> publicRow(Map<String, Object> row) {
        Map<String, Object> result = new LinkedHashMap<>();
        String[][] fields = {{"id","id"},{"fileName","file_name"},{"sizeBytes","size_bytes"},
                {"sourceName","source_name"},{"sourceUrl","source_url"},{"usageType","usage_type"},
                {"status","status"},{"attempts","attempts"},{"errorCode","error_code"},
                {"createdAt","created_at"},{"updatedAt","updated_at"},{"pipelineVersion","pipeline_version"}};
        for (String[] pair : fields) result.put(pair[0], row.get(pair[1]));
        result.put("executionClass", executionClass(String.valueOf(row.get("file_name"))));
        List<Map<String, Object>> published = db.queryForList(
                "SELECT r.version FROM litemall_document_index_item i JOIN litemall_document_index_release r ON r.id=i.release_id WHERE i.document_id=? AND r.status='active' LIMIT 1",
                row.get("id"));
        result.put("published", !published.isEmpty());
        result.put("indexVersion", published.isEmpty() ? "" : published.get(0).get("version"));
        result.put("canRetry", "failed".equals(row.get("status")) && ((Number) row.get("attempts")).intValue() < 3);
        result.put("canRemove", "policy_candidate".equals(row.get("usage_type"))
                && !Arrays.asList("running", "removed").contains(String.valueOf(row.get("status"))));
        return result;
    }

    public Map<String, Object> list(int page, int limit) {
        page = Math.max(1, Math.min(page, 100000));
        limit = Math.max(1, Math.min(limit, 100));
        List<Map<String, Object>> items = new ArrayList<>();
        for (Map<String, Object> row : db.queryForList("SELECT * FROM " + TABLE + " ORDER BY created_at DESC,id LIMIT ? OFFSET ?", limit, (page - 1) * limit))
            items.add(publicRow(row));
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("list", items);
        result.put("total", db.queryForObject("SELECT COUNT(*) FROM " + TABLE, Long.class));
        return result;
    }

    public Map<String, Object> retry(String id) {
        db.update("UPDATE " + TABLE + " SET status='queued',error_code=NULL,available_at=NOW(),updated_at=NOW() WHERE id=? AND status='failed' AND attempts<3", id);
        return detail(id);
    }

    @org.springframework.transaction.annotation.Transactional
    public synchronized Map<String, Object> remove(String id, String operator) {
        Map<String, Object> target = row(id);
        if (!"policy_candidate".equals(target.get("usage_type"))) throw new IllegalArgumentException("DOCUMENT_NOT_POLICY_CANDIDATE");
        if ("running".equals(target.get("status"))) throw new IllegalArgumentException("DOCUMENT_RUNNING");
        if ("removed".equals(target.get("status"))) return publicRow(target);
        String sourceUrl = String.valueOf(target.get("source_url"));
        int removed;
        if (!sourceUrl.trim().isEmpty()) {
            if (db.queryForObject("SELECT COUNT(*) FROM " + TABLE + " WHERE pipeline_version=? AND usage_type='policy_candidate' AND source_url=? AND status='running'", Integer.class,
                    version, sourceUrl) > 0) throw new IllegalArgumentException("DOCUMENT_RUNNING");
            removed = db.update("UPDATE " + TABLE + " SET status='removed',lease_token=NULL,lease_until=NULL,operator_name=?,updated_at=NOW() WHERE pipeline_version=? AND usage_type='policy_candidate' AND source_url=? AND status<>'running' AND status<>'removed'",
                    operator, version, sourceUrl);
        } else {
            if (db.queryForObject("SELECT COUNT(*) FROM " + TABLE + " WHERE pipeline_version=? AND usage_type='policy_candidate' AND source_url='' AND source_name=? AND file_name=? AND status='running'", Integer.class,
                    version, target.get("source_name"), target.get("file_name")) > 0) throw new IllegalArgumentException("DOCUMENT_RUNNING");
            removed = db.update("UPDATE " + TABLE + " SET status='removed',lease_token=NULL,lease_until=NULL,operator_name=?,updated_at=NOW() WHERE pipeline_version=? AND usage_type='policy_candidate' AND source_url='' AND source_name=? AND file_name=? AND status<>'running' AND status<>'removed'",
                    operator, version, target.get("source_name"), target.get("file_name"));
        }
        Map<String, Object> result = detail(id);
        result.put("removedVersionCount", removed);
        return result;
    }

    public Map<String, Object> claim() { return claimForExecutionClass("any"); }

    public Map<String, Object> claimForExecutionClass(String requestedClass) {
        String executionClass = requestedClass == null ? "any" : requestedClass.trim().toLowerCase(Locale.ROOT);
        if (!Arrays.asList("any", "light", "heavy").contains(executionClass))
            throw new IllegalArgumentException("EXECUTION_CLASS_INVALID");
        db.update("UPDATE " + TABLE + " SET status=IF(attempts>=3,'failed','queued'),lease_token=NULL,lease_until=NULL,error_code='WORKER_INTERRUPTED',available_at=NOW(),updated_at=NOW() WHERE pipeline_version=? AND status='running' AND lease_until<NOW()", version);
        String queueFilter = "";
        if ("light".equals(executionClass)) queueFilter = " AND " + LIGHT_QUEUE_SQL;
        if ("heavy".equals(executionClass)) queueFilter = " AND NOT (" + LIGHT_QUEUE_SQL + ")";
        for (Map<String, Object> item : db.queryForList("SELECT id FROM " + TABLE + " WHERE pipeline_version=? AND status='queued' AND attempts<3 AND available_at<=NOW()" + queueFilter + " ORDER BY created_at,id LIMIT 10", version)) {
            String id = (String) item.get("id");
            String token = UUID.randomUUID().toString();
            int updated = db.update("UPDATE " + TABLE + " SET status='running',attempts=attempts+1,lease_token=?,lease_until=DATE_ADD(NOW(),INTERVAL 120 SECOND),updated_at=NOW() WHERE id=? AND status='queued' AND attempts<3", token, id);
            if (updated == 0) continue;
            Map<String, Object> raw = row(id);
            Map<String, Object> result = publicRow(raw);
            result.put("leaseToken", token);
            result.put("root", root.toString());
            result.put("inputPath", raw.get("input_path"));
            result.put("fileHash", raw.get("file_hash"));
            result.put("executionClass", executionClass(String.valueOf(raw.get("file_name"))));
            return result;
        }
        return null;
    }

    public boolean heartbeat(String id, String token) {
        return db.update("UPDATE " + TABLE + " SET lease_until=DATE_ADD(NOW(),INTERVAL 120 SECOND),updated_at=NOW() WHERE id=? AND lease_token=? AND status='running' AND lease_until>=NOW()", id, token) == 1;
    }

    public boolean finish(String id, String token, String errorCode) throws IOException {
        // A stale worker can write its own attempt artifact, never publish another lease's result.
        String relative = id + "/" + token + "/normalized.json";
        if (errorCode == null || errorCode.isEmpty()) {
            Map<String, Object> raw = row(id);
            Map<?, ?> document = json.readValue(safePath(relative).toFile(), Map.class);
            if (!id.equals(document.get("documentId")) || !raw.get("source_name").equals(document.get("sourceName"))
                    || !"uploaded_document".equals(document.get("sourceType"))
                    || !(document.get("nodes") instanceof List) || ((List<?>) document.get("nodes")).isEmpty())
                throw new IllegalArgumentException("PARSED_DOCUMENT_INVALID");
            return db.update("UPDATE " + TABLE + " SET status='parsed',result_path=?,error_code=NULL,lease_until=NULL,updated_at=NOW() WHERE id=? AND lease_token=? AND status='running' AND lease_until>=NOW()", relative, id, token) == 1;
        }
        if (!errorCode.matches("[A-Z0-9_]{1,100}")) throw new IllegalArgumentException("ERROR_CODE_INVALID");
        return db.update("UPDATE " + TABLE + " SET status='failed',error_code=?,lease_until=NULL,updated_at=NOW() WHERE id=? AND lease_token=? AND status='running' AND lease_until>=NOW()", errorCode, id, token) == 1;
    }

    private Path safePath(String relative) throws IOException {
        Path resolved = root.resolve(relative).normalize();
        if (!resolved.startsWith(root) || !resolved.toRealPath().startsWith(root.toRealPath()))
            throw new IllegalArgumentException("ARTIFACT_PATH_INVALID");
        if (Files.size(resolved) > 50L * 1024 * 1024) throw new IllegalArgumentException("ARTIFACT_TOO_LARGE");
        return resolved;
    }

    public Map<String, Object> preview(String id) throws IOException {
        Map<String, Object> raw = row(id);
        Map<String, Object> result = publicRow(raw);
        if (!"parsed".equals(raw.get("status"))) return result;
        Map<?, ?> document = json.readValue(safePath((String) raw.get("result_path")).toFile(), Map.class);
        String markdown = String.valueOf(document.get("markdown"));
        result.put("preview", markdown.substring(0, Math.min(markdown.length(), 12000)));
        result.put("previewTruncated", markdown.length() > 12000);
        result.put("nodeCount", ((List<?>) document.get("nodes")).size());
        result.put("assetCount", ((List<?>) document.get("assets")).size());
        result.put("parser", document.get("parser"));
        List<Map<String, Object>> outline = new ArrayList<>();
        for (Object node : (List<?>) document.get("nodes")) {
            Map<?, ?> n = (Map<?, ?>) node;
            Map<String, Object> shown = new LinkedHashMap<>();
            for (String key : Arrays.asList("type", "sectionPath", "pageNumber", "sourceRef")) shown.put(key, n.get(key));
            String text = String.valueOf(n.get("text"));
            shown.put("text", text.substring(0, Math.min(240, text.length())));
            outline.add(shown);
            if (outline.size() == 30) break;
        }
        result.put("outline", outline);
        return result;
    }

    private static String hex(byte[] bytes) {
        StringBuilder out = new StringBuilder();
        for (byte value : bytes) out.append(String.format("%02x", value));
        return out.toString();
    }
}
