package org.linlinjava.litemall.publicruntime;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.Map;

@RestController
@RequestMapping("/public/runtime")
public class PublicRuntimeHealthController {
    @Autowired
    private JdbcTemplate jdbcTemplate;

    @Value("${ai.service.base-url:http://127.0.0.1:8008}")
    private String aiServiceBaseUrl;

    @GetMapping("/live")
    public Map<String, Object> live() {
        Map<String, Object> data = new HashMap<String, Object>();
        data.put("status", "live");
        data.put("service", "litemall-all");
        data.put("time", LocalDateTime.now().toString());
        return data;
    }

    @GetMapping("/ready")
    public Map<String, Object> ready() {
        Map<String, Object> data = live();
        try {
            Integer tableCount = jdbcTemplate.queryForObject(
                    "select count(*) from information_schema.tables where table_schema = database() and table_name in ('litemall_comment','litemall_review_ai_analysis','litemall_ai_review_risk_task')",
                    Integer.class);
            Integer seedUserCount = jdbcTemplate.queryForObject(
                    "select count(*) from litemall_user where username like 'ci_public_%' and deleted = 0",
                    Integer.class);
            data.put("status", tableCount != null && tableCount >= 3 ? "ready" : "not_ready");
            data.put("mysql", "ok");
            data.put("requiredTables", tableCount);
            data.put("publicSeedUsers", seedUserCount);
            data.put("aiServiceBaseUrl", aiServiceBaseUrl);
        } catch (Exception e) {
            data.put("status", "not_ready");
            data.put("mysql", "failed");
            data.put("error", e.getClass().getSimpleName() + ": " + e.getMessage());
        }
        return data;
    }
}
