package org.linlinjava.litemall.admin.web;

import org.linlinjava.litemall.admin.service.DocumentJobService;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Map;
import java.util.Collections;

@RestController
@RequestMapping("/internal/document-jobs")
public class DocumentWorkerController {
    private final DocumentJobService jobs;
    private final org.linlinjava.litemall.admin.service.DocumentIndexService indexes;
    private final String secret;
    @org.springframework.beans.factory.annotation.Autowired
    public DocumentWorkerController(DocumentJobService jobs,
            org.linlinjava.litemall.admin.service.DocumentIndexService indexes,
            @Value("${DOCUMENT_WORKER_TOKEN:}") String secret) {
        this.jobs = jobs;
        this.indexes = indexes;
        this.secret = secret;
    }

    public DocumentWorkerController(DocumentJobService jobs, String secret) {
        this.jobs = jobs;
        this.indexes = null;
        this.secret = secret;
    }

    private void authenticate(String supplied) {
        if (secret.length() < 32 || supplied == null || !MessageDigest.isEqual(
                secret.getBytes(StandardCharsets.UTF_8), supplied.getBytes(StandardCharsets.UTF_8)))
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED);
    }

    @PostMapping("/claim")
    public Object claim(@RequestHeader(value="X-Document-Worker-Token", required=false) String token,
            @RequestBody(required=false) Map<String, String> body) {
        authenticate(token);
        return Collections.singletonMap("task", jobs.claimForExecutionClass(body == null ? "any" : body.get("executionClass")));
    }

    public Object claim(String token) { return claim(token, Collections.emptyMap()); }

    @PostMapping("/{id}/heartbeat")
    public Object heartbeat(@RequestHeader(value="X-Document-Worker-Token", required=false) String token,
            @PathVariable String id, @RequestBody Map<String, String> body) {
        authenticate(token);
        return Collections.singletonMap("accepted", jobs.heartbeat(id, body.get("leaseToken")));
    }

    @PostMapping("/{id}/finish")
    public Object finish(@RequestHeader(value="X-Document-Worker-Token", required=false) String token,
            @PathVariable String id, @RequestBody Map<String, String> body) throws Exception {
        authenticate(token);
        return Collections.singletonMap("accepted", jobs.finish(id, body.get("leaseToken"), body.get("errorCode")));
    }

    @PostMapping("/index/claim")
    public Object claimIndex(@RequestHeader(value="X-Document-Worker-Token", required=false) String token) {
        authenticate(token);
        return Collections.singletonMap("task", indexes.claim());
    }

    @PostMapping("/index/{id}/heartbeat")
    public Object heartbeatIndex(@RequestHeader(value="X-Document-Worker-Token", required=false) String token,
            @PathVariable String id, @RequestBody Map<String, String> body) {
        authenticate(token);
        return Collections.singletonMap("accepted", indexes.heartbeat(id, body.get("leaseToken")));
    }

    @PostMapping("/index/{id}/finish")
    public Object finishIndex(@RequestHeader(value="X-Document-Worker-Token", required=false) String token,
            @PathVariable String id, @RequestBody Map<String, String> body) throws Exception {
        authenticate(token);
        return Collections.singletonMap("accepted", indexes.finish(id, body.get("leaseToken"), body.get("errorCode")));
    }
}
