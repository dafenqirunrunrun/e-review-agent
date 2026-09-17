package org.linlinjava.litemall.admin.service;

import org.junit.Test;

import java.util.*;

import static org.junit.Assert.*;

public class DocumentIndexReleaseRoleTest {
    @Test
    public void legacyReadyReleaseDoesNotHideVerifiedComparableHistory() {
        Map<String, Object> legacy = release("legacy", "ready", false, false);
        Map<String, Object> verified = release("verified", "superseded", true, true);
        List<Map<String, Object>> releases = Arrays.asList(legacy, verified);

        assertNull(DocumentIndexService.selectCandidateRelease(releases));
        assertEquals("verified", DocumentIndexService.selectComparableRelease(releases).get("version"));
    }

    @Test
    public void evaluatedCandidateKeepsItsCandidateRole() {
        Map<String, Object> candidate = release("candidate", "ready", true, true);
        Map<String, Object> previous = release("previous", "superseded", true, true);
        List<Map<String, Object>> releases = Arrays.asList(candidate, previous);

        assertEquals("candidate", DocumentIndexService.selectCandidateRelease(releases).get("version"));
        assertEquals("candidate", DocumentIndexService.selectComparableRelease(releases).get("version"));
    }

    private static Map<String, Object> release(String version, String status, boolean evaluated, boolean passed) {
        Map<String, Object> evaluation = new LinkedHashMap<String, Object>();
        evaluation.put("gatePassed", passed);
        evaluation.put("decision", passed ? "recommended" : "blocked");
        Map<String, Object> release = new LinkedHashMap<String, Object>();
        release.put("version", version);
        release.put("status", status);
        release.put("evaluationAvailable", evaluated);
        release.put("releaseEvaluation", evaluated ? evaluation : null);
        return release;
    }
}
