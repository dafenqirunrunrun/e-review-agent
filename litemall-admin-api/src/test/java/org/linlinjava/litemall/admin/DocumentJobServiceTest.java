package org.linlinjava.litemall.admin;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.*;
import org.junit.rules.TemporaryFolder;
import org.linlinjava.litemall.admin.service.DocumentJobService;
import org.linlinjava.litemall.admin.service.DocumentIndexService;
import org.linlinjava.litemall.admin.web.DocumentWorkerController;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.web.server.ResponseStatusException;
import org.yaml.snakeyaml.Yaml;

import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import static org.junit.Assert.*;
import static org.mockito.Mockito.*;

public class DocumentJobServiceTest {
    @Rule public TemporaryFolder files = new TemporaryFolder();

    @Test public void uploadNameRejectsTraversalAndExecutable() {
        for (String name : Arrays.asList("../a.md", "C:\\a.md", "a.exe", "a\n.md")) {
            try { DocumentJobService.extension(name); fail(name); } catch (IllegalArgumentException expected) { }
        }
        assertEquals("pdf", DocumentJobService.extension("policy.PDF"));
        assertEquals("light", DocumentJobService.executionClass("policy.xlsx"));
        assertEquals("light", DocumentJobService.executionClass("policy.HTML"));
        assertEquals("heavy", DocumentJobService.executionClass("scan.pdf"));
        assertEquals("heavy", DocumentJobService.executionClass("slides.pptx"));
    }

    @Test public void internalQueueRequiresConfiguredStrongToken() {
        DocumentJobService jobs = mock(DocumentJobService.class);
        DocumentWorkerController controller = new DocumentWorkerController(jobs, "");
        try { controller.claim(null); fail(); } catch (ResponseStatusException expected) { }
        verifyZeroInteractions(jobs);
        controller = new DocumentWorkerController(jobs, String.join("", Collections.nCopies(32, "a")));
        try { controller.claim("wrong"); fail(); } catch (ResponseStatusException expected) { }
        verifyZeroInteractions(jobs);
    }

    @Test public void realMysqlPersistenceDedupConcurrentClaimLeaseFencingRetryAndCompletion() throws Exception {
        Assume.assumeTrue("Set E_REVIEW_DOCUMENT_MYSQL_TEST=true for real MySQL verification",
                "true".equals(System.getenv("E_REVIEW_DOCUMENT_MYSQL_TEST")));
        Map config = new Yaml().load(getClass().getResourceAsStream("/application-db.yml"));
        Map database = (Map) ((Map) ((Map) config.get("spring")).get("datasource")).get("druid");
        DriverManagerDataSource dataSource = new DriverManagerDataSource();
        dataSource.setDriverClassName("com.mysql.cj.jdbc.Driver");
        dataSource.setUrl(System.getenv().getOrDefault("E_REVIEW_DOCUMENT_DB_URL", String.valueOf(database.get("url"))));
        dataSource.setUsername(System.getenv().getOrDefault("EREVIEW_MYSQL_USER", String.valueOf(database.get("username"))));
        dataSource.setPassword(System.getenv().getOrDefault("EREVIEW_MYSQL_PASSWORD", String.valueOf(database.get("password"))));
        JdbcTemplate db = new JdbcTemplate(dataSource);
        ObjectMapper json = new ObjectMapper();
        String version = "test-" + UUID.randomUUID();
        Path root = files.newFolder().toPath();
        DocumentJobService service = new DocumentJobService(db, json, root.toString(), version);
        service.initialize();
        try {
            MockMultipartFile file = new MockMultipartFile("file", "policy.md", "text/markdown", "# Policy\n\nNo fake reviews".getBytes(StandardCharsets.UTF_8));
            Map<String, Object> first = service.upload(file, "Source", "https://example.org", "reference", "test");
            String id = (String) first.get("id");
            assertEquals(id, service.upload(file, "Source", "https://example.org", "reference", "test").get("id"));
            assertEquals(false, first.get("published"));
            assertEquals(1, db.queryForObject("SELECT COUNT(*) FROM litemall_document_job WHERE pipeline_version=?", Integer.class, version).intValue());
            // A new service instance proves the queue is not process-local memory.
            DocumentJobService reopened = new DocumentJobService(db, json, root.toString(), version);
            ExecutorService pool = Executors.newFixedThreadPool(2);
            Map<String, Object> claim;
            try {
                Future<Map<String, Object>> a = pool.submit(service::claim);
                Future<Map<String, Object>> b = pool.submit(reopened::claim);
                Map<String, Object> one = a.get(10, TimeUnit.SECONDS), two = b.get(10, TimeUnit.SECONDS);
                assertTrue((one == null) != (two == null));
                claim = one == null ? two : one;
            } finally { pool.shutdownNow(); }
            String oldToken = (String) claim.get("leaseToken");
            assertTrue(service.heartbeat(id, oldToken));
            db.update("UPDATE litemall_document_job SET lease_until=DATE_SUB(NOW(),INTERVAL 1 SECOND) WHERE id=?", id);
            assertFalse(service.heartbeat(id, oldToken));
            Map<String, Object> next = reopened.claim();
            String token = (String) next.get("leaseToken");
            assertNotEquals(oldToken, token);
            assertEquals(2, next.get("attempts"));
            assertFalse(service.finish(id, oldToken, "STALE_FAILURE"));
            assertTrue(reopened.finish(id, token, "DOCUMENT_PARSE_FAILED"));
            assertEquals("failed", service.detail(id).get("status"));
            assertEquals("queued", service.retry(id).get("status"));
            assertEquals("queued", service.retry(id).get("status"));
            token = (String) service.claim().get("leaseToken");
            Path output = root.resolve(id).resolve(token).resolve("normalized.json");
            Files.createDirectories(output.getParent());
            Map<String, Object> document = new LinkedHashMap<>();
            document.put("documentId", id); document.put("sourceName", "Source");
            document.put("sourceType", "uploaded_document"); document.put("markdown", "# Policy");
            document.put("nodes", Collections.singletonList(Collections.singletonMap("text", "Policy")));
            document.put("assets", Collections.emptyList()); document.put("parser", "lightweight");
            json.writeValue(output.toFile(), document);
            assertTrue(service.finish(id, token, ""));
            assertFalse(service.finish(id, token, "DOCUMENT_PARSE_FAILED"));
            assertEquals("parsed", reopened.preview(id).get("status"));
            assertEquals("# Policy", reopened.preview(id).get("preview"));
            assertEquals("parsed", service.retry(id).get("status"));
            assertNull(service.claim());
            assertFalse(service.detail(id).containsKey("input_path"));
        } finally {
            db.update("DELETE FROM litemall_document_job WHERE pipeline_version=?", version);
        }
    }

    @Test public void realMysqlClaimsLightAndHeavyQueuesIndependently() throws Exception {
        Assume.assumeTrue("Set E_REVIEW_DOCUMENT_MYSQL_TEST=true for real MySQL verification",
                "true".equals(System.getenv("E_REVIEW_DOCUMENT_MYSQL_TEST")));
        Map config = new Yaml().load(getClass().getResourceAsStream("/application-db.yml"));
        Map database = (Map) ((Map) ((Map) config.get("spring")).get("datasource")).get("druid");
        DriverManagerDataSource dataSource = new DriverManagerDataSource();
        dataSource.setDriverClassName("com.mysql.cj.jdbc.Driver");
        dataSource.setUrl(System.getenv().getOrDefault("E_REVIEW_DOCUMENT_DB_URL", String.valueOf(database.get("url"))));
        dataSource.setUsername(System.getenv().getOrDefault("EREVIEW_MYSQL_USER", String.valueOf(database.get("username"))));
        dataSource.setPassword(System.getenv().getOrDefault("EREVIEW_MYSQL_PASSWORD", String.valueOf(database.get("password"))));
        JdbcTemplate db = new JdbcTemplate(dataSource);
        String version = "class-test-" + UUID.randomUUID();
        DocumentJobService service = new DocumentJobService(db, new ObjectMapper(), files.newFolder().toPath().toString(), version);
        service.initialize();
        try {
            service.upload(new MockMultipartFile("file", "policy.md", "text/markdown", "# Policy".getBytes(StandardCharsets.UTF_8)),
                    "Light", "", "reference", "test");
            service.upload(new MockMultipartFile("file", "scan.pdf", "application/pdf", "%PDF fixture".getBytes(StandardCharsets.UTF_8)),
                    "Heavy", "", "reference", "test");
            Map<String, Object> light = service.claimForExecutionClass("light");
            Map<String, Object> heavy = service.claimForExecutionClass("heavy");
            assertEquals("light", light.get("executionClass"));
            assertEquals("policy.md", light.get("fileName"));
            assertEquals("heavy", heavy.get("executionClass"));
            assertEquals("scan.pdf", heavy.get("fileName"));
            assertNull(service.claimForExecutionClass("light"));
            assertNull(service.claimForExecutionClass("heavy"));
        } finally {
            db.update("DELETE FROM litemall_document_job WHERE pipeline_version=?", version);
        }
    }

    @Test public void realMysqlPolicySourceRemovalIsLogicalAndExactReuploadRestoresIt() throws Exception {
        Assume.assumeTrue("Set E_REVIEW_DOCUMENT_MYSQL_TEST=true for real MySQL verification",
                "true".equals(System.getenv("E_REVIEW_DOCUMENT_MYSQL_TEST")));
        Map config = new Yaml().load(getClass().getResourceAsStream("/application-db.yml"));
        Map database = (Map) ((Map) ((Map) config.get("spring")).get("datasource")).get("druid");
        DriverManagerDataSource dataSource = new DriverManagerDataSource();
        dataSource.setDriverClassName("com.mysql.cj.jdbc.Driver");
        dataSource.setUrl(System.getenv().getOrDefault("E_REVIEW_DOCUMENT_DB_URL", String.valueOf(database.get("url"))));
        dataSource.setUsername(System.getenv().getOrDefault("EREVIEW_MYSQL_USER", String.valueOf(database.get("username"))));
        dataSource.setPassword(System.getenv().getOrDefault("EREVIEW_MYSQL_PASSWORD", String.valueOf(database.get("password"))));
        JdbcTemplate db = new JdbcTemplate(dataSource);
        String version = "lifecycle-test-" + UUID.randomUUID();
        DocumentJobService service = new DocumentJobService(db, new ObjectMapper(), files.newFolder().toPath().toString(), version);
        service.initialize();
        try {
            MockMultipartFile oldFile = new MockMultipartFile("file", "policy.md", "text/markdown", "old".getBytes(StandardCharsets.UTF_8));
            MockMultipartFile newFile = new MockMultipartFile("file", "policy.md", "text/markdown", "new".getBytes(StandardCharsets.UTF_8));
            String oldId = String.valueOf(service.upload(oldFile, "Policy", "https://example.org/lifecycle", "policy_candidate", "test").get("id"));
            String newId = String.valueOf(service.upload(newFile, "Policy", "https://example.org/lifecycle", "policy_candidate", "test").get("id"));
            db.update("UPDATE litemall_document_job SET status='parsed' WHERE id IN (?,?)", oldId, newId);

            Map<String, Object> removed = service.remove(newId, "reviewer");
            assertEquals("removed", removed.get("status"));
            assertEquals(2, ((Number) removed.get("removedVersionCount")).intValue());
            assertEquals(2, db.queryForObject("SELECT COUNT(*) FROM litemall_document_job WHERE pipeline_version=? AND status='removed'", Integer.class, version).intValue());

            Map<String, Object> restored = service.upload(newFile, "Policy", "https://example.org/lifecycle", "policy_candidate", "reviewer");
            assertEquals(newId, restored.get("id"));
            assertEquals("queued", restored.get("status"));
            assertEquals(1, db.queryForObject("SELECT COUNT(*) FROM litemall_document_job WHERE pipeline_version=? AND status='removed'", Integer.class, version).intValue());
        } finally {
            db.update("DELETE FROM litemall_document_job WHERE pipeline_version=?", version);
        }
    }

    @Test public void realMysqlCandidateIndexQueueIsDurableAndQualityGated() throws Exception {
        Assume.assumeTrue("Set E_REVIEW_DOCUMENT_MYSQL_TEST=true for real MySQL verification",
                "true".equals(System.getenv("E_REVIEW_DOCUMENT_MYSQL_TEST")));
        Map config = new Yaml().load(getClass().getResourceAsStream("/application-db.yml"));
        Map database = (Map) ((Map) ((Map) config.get("spring")).get("datasource")).get("druid");
        DriverManagerDataSource dataSource = new DriverManagerDataSource();
        dataSource.setDriverClassName("com.mysql.cj.jdbc.Driver");
        dataSource.setUrl(String.valueOf(database.get("url")));
        dataSource.setUsername(String.valueOf(database.get("username")));
        dataSource.setPassword(String.valueOf(database.get("password")));
        JdbcTemplate db = new JdbcTemplate(dataSource);
        ObjectMapper json = new ObjectMapper();
        Path root = files.newFolder().toPath();
        String pipeline = "index-test-" + UUID.randomUUID();
        DocumentJobService jobs = new DocumentJobService(db, json, root.toString(), pipeline);
        jobs.initialize();
        String documentId = "";
        String newerDocumentId = "";
        String releaseId = "";
        try {
            Map<String, Object> uploaded = jobs.upload(new MockMultipartFile("file", "candidate.md", "text/markdown",
                    "# Policy\n\nNo paid reviews".getBytes(StandardCharsets.UTF_8)), "Candidate", "https://example.org", "policy_candidate", "test");
            documentId = String.valueOf(uploaded.get("id"));
            Map<String, Object> claimedDocument = jobs.claimForExecutionClass("light");
            String documentToken = String.valueOf(claimedDocument.get("leaseToken"));
            Path normalized = root.resolve(documentId).resolve(documentToken).resolve("normalized.json");
            Files.createDirectories(normalized.getParent());
            Map<String, Object> parsed = new LinkedHashMap<>();
            parsed.put("documentId", documentId); parsed.put("sourceName", "Candidate");
            parsed.put("sourceType", "uploaded_document"); parsed.put("markdown", "# Policy\n\nNo paid reviews");
            parsed.put("nodes", Collections.singletonList(Collections.singletonMap("text", "No paid reviews")));
            parsed.put("assets", Collections.emptyList()); parsed.put("parser", "lightweight");
            json.writeValue(normalized.toFile(), parsed);
            assertTrue(jobs.finish(documentId, documentToken, ""));

            Map<String, Object> newer = jobs.upload(new MockMultipartFile("file", "candidate.md", "text/markdown",
                    "# Policy\n\nUpdated paid review rule".getBytes(StandardCharsets.UTF_8)), "Candidate", "https://example.org", "policy_candidate", "test");
            newerDocumentId = String.valueOf(newer.get("id"));
            db.update("UPDATE litemall_document_job SET status='parsed',result_path=?,updated_at=DATE_ADD(NOW(),INTERVAL 2 SECOND) WHERE id=?",
                    documentId + "/" + documentToken + "/normalized.json", newerDocumentId);

            DocumentIndexService indexes = new DocumentIndexService(db, json, root.toString(), root.resolve("policy-index").toString(),
                    root.resolve("python.exe").toString(), root.resolve("worker.py").toString(), root.resolve("base.jsonl").toString(), pipeline);
            Map<String, Object> release = indexes.createCandidate("test");
            releaseId = String.valueOf(release.get("id"));
            assertEquals("queued", release.get("status"));
            Map request = json.readValue(root.resolve("index-releases").resolve(releaseId).resolve("request.json").toFile(), Map.class);
            List requestDocuments = (List) request.get("documents");
            assertEquals(1, requestDocuments.size());
            assertEquals(newerDocumentId, ((Map) requestDocuments.get(0)).get("documentId"));
            Map<String, Object> claim = indexes.claim();
            assertEquals(releaseId, claim.get("id"));
            String token = String.valueOf(claim.get("leaseToken"));
            assertTrue(indexes.heartbeat(releaseId, token));
            Path result = root.resolve("index-releases").resolve(releaseId).resolve(token).resolve("build-result.json");
            Files.createDirectories(result.getParent());
            Map<String, Object> resultData = new LinkedHashMap<>();
            resultData.put("releaseId", releaseId); resultData.put("gate", "PASS"); resultData.put("chunkCount", 3);
            resultData.put("dense", Collections.singletonMap("status", "ready"));
            Map<String, Object> evaluation = new LinkedHashMap<>();
            evaluation.put("schemaVersion", "policy-release-evaluation-v1");
            evaluation.put("decision", "recommended");
            evaluation.put("decisionLabel", "建议发布");
            evaluation.put("gatePassed", true);
            resultData.put("releaseEvaluation", evaluation);
            json.writeValue(result.toFile(), resultData);
            assertTrue(indexes.finish(releaseId, token, ""));
            assertEquals("ready", indexes.detail(releaseId).get("status"));
            assertEquals(true, indexes.detail(releaseId).get("canPublish"));

            Files.delete(result);
            assertEquals(false, indexes.detail(releaseId).get("canPublish"));
            assertEquals(true, indexes.detail(releaseId).get("evaluationMissing"));
            json.writeValue(result.toFile(), resultData);

            String failedToken = UUID.randomUUID().toString();
            db.update("UPDATE litemall_document_index_release SET status='building',lease_token=?,lease_until=DATE_ADD(NOW(),INTERVAL 120 SECOND) WHERE id=?",
                    failedToken, releaseId);
            Path failedResult = root.resolve("index-releases").resolve(releaseId).resolve(failedToken).resolve("build-result.json");
            Files.createDirectories(failedResult.getParent());
            Map<String, Object> failedData = new LinkedHashMap<>(resultData);
            failedData.put("gate", "FAIL");
            Map<String, Object> failedEvaluation = new LinkedHashMap<>(evaluation);
            failedEvaluation.put("decision", "blocked");
            failedEvaluation.put("decisionLabel", "禁止发布");
            failedEvaluation.put("gatePassed", false);
            failedEvaluation.put("reasonCodes", Collections.singletonList("CRITICAL_RISK_EVIDENCE_MISSING"));
            failedData.put("releaseEvaluation", failedEvaluation);
            json.writeValue(failedResult.toFile(), failedData);
            assertTrue(indexes.finish(releaseId, failedToken, "INDEX_QUALITY_GATE_FAILED"));
            Map<String, Object> failedDetail = indexes.detail(releaseId);
            assertEquals("failed", failedDetail.get("status"));
            assertEquals(true, failedDetail.get("evaluationAvailable"));
            assertEquals(false, failedDetail.get("canPublish"));
            assertEquals("blocked", ((Map) failedDetail.get("releaseEvaluation")).get("decision"));
        } finally {
            if (!releaseId.isEmpty()) {
                db.update("DELETE FROM litemall_document_index_item WHERE release_id=?", releaseId);
                db.update("DELETE FROM litemall_document_index_release WHERE id=?", releaseId);
            }
            db.update("DELETE FROM litemall_document_job WHERE pipeline_version=?", pipeline);
        }
    }
}
