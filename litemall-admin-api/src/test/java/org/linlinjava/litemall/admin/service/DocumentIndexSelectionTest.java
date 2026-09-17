package org.linlinjava.litemall.admin.service;

import org.junit.Test;

import java.util.*;

import static org.junit.Assert.assertEquals;

public class DocumentIndexSelectionTest {
    @Test public void latestParsedDocumentWinsForEachLogicalSource() {
        List<Map<String, Object>> rows = Arrays.asList(
                row("new", "Policy New", "policy.md", "HTTPS://EXAMPLE.ORG/policy"),
                row("name-new", "  Local   Policy ", "local.md", ""),
                row("separate-file", "local policy", "appendix.md", ""),
                row("old", "Policy Old", "policy.md", "https://example.org/policy"),
                row("name-old", "local policy", "local.md", ""));

        List<Map<String, Object>> selected = DocumentIndexService.latestDocumentsBySource(rows);

        assertEquals(3, selected.size());
        Set<String> ids = new HashSet<>();
        for (Map<String, Object> item : selected) ids.add(String.valueOf(item.get("id")));
        assertEquals(new HashSet<>(Arrays.asList("new", "name-new", "separate-file")), ids);
    }

    private static Map<String, Object> row(String id, String name, String file, String url) {
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("id", id);
        row.put("source_name", name);
        row.put("file_name", file);
        row.put("source_url", url);
        return row;
    }
}
