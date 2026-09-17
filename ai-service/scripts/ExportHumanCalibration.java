import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.security.MessageDigest;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.Statement;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;

/** Exports sanitized review-task facts without reviewer identity. */
public class ExportHumanCalibration {
    public static void main(String[] args) throws Exception {
        if (args.length != 1) {
            throw new IllegalArgumentException("usage: ExportHumanCalibration <output-jsonl>");
        }
        String url = required("E_REVIEW_CALIBRATION_DB_URL");
        String user = required("E_REVIEW_CALIBRATION_DB_USER");
        String password = required("E_REVIEW_CALIBRATION_DB_PASSWORD");
        String sql = "select t.id,t.review_text,t.risk_type,t.risk_level,t.source_type,t.status," +
                "l.action_type,l.created_time from litemall_ai_review_risk_task t " +
                "left join litemall_ai_operation_log l on l.id=(select max(l2.id) from litemall_ai_operation_log l2 where l2.risk_task_id=t.id) " +
                "where t.deleted=0 and t.review_text is not null and trim(t.review_text)<>'' order by t.id";
        Class.forName("com.mysql.cj.jdbc.Driver");
        List<String> rows = new ArrayList<String>();
        try (Connection connection = DriverManager.getConnection(url, user, password);
             Statement statement = connection.createStatement();
             ResultSet result = statement.executeQuery(sql)) {
            while (result.next()) {
                String action = value(result.getString("action_type"));
                boolean accepted = "accept_ai_suggestion".equals(action) || "human_review_accept_ai_suggestion".equals(action);
                boolean humanReviewed = accepted || action.startsWith("human_review_");
                String tier = action.startsWith("human_review_") ? "A" : accepted ? "B" : "UNLABELED";
                String created = result.getTimestamp("created_time") == null ? "unknown" :
                        result.getTimestamp("created_time").toLocalDateTime().format(DateTimeFormatter.ofPattern("yyyy-MM"));
                String text = sanitize(result.getString("review_text"));
                String id = sha256(result.getInt("id") + ":" + text).substring(0, 20);
                rows.add("{" +
                        field("caseId", "db-" + id) + "," +
                        field("sanitizedText", text) + "," +
                        field("currentRiskType", value(result.getString("risk_type"))) + "," +
                        field("currentRiskLevel", value(result.getString("risk_level"))) + "," +
                        field("sourceType", "risk_task:" + value(result.getString("source_type"))) + "," +
                        field("sourcePeriod", created) + "," +
                        field("taskStatus", value(result.getString("status"))) + "," +
                        field("reviewOutcome", outcome(action)) + "," +
                        field("provenanceTier", tier) + "," +
                        "\"humanReviewed\":" + humanReviewed + "," +
                        "\"eligibleAsGold\":" + accepted +
                        "}");
            }
        }
        Path output = Paths.get(args[0]);
        Files.createDirectories(output.toAbsolutePath().getParent());
        Files.write(output, rows, StandardCharsets.UTF_8);
        System.out.println("exported=" + rows.size() + " output=" + output);
    }

    private static String sanitize(String value) {
        String text = value == null ? "" : value;
        text = text.replaceAll("(?i)[A-Z0-9._%+-]+@[A-Z0-9.-]+\\.[A-Z]{2,}", "[EMAIL]");
        text = text.replaceAll("(?<!\\d)1[3-9]\\d{9}(?!\\d)", "[PHONE]");
        text = text.replaceAll("(?<!\\d)\\d{17}[0-9Xx](?!\\d)", "[ID]");
        text = text.replaceAll("(?i)https?://\\S+", "[URL]");
        return text.trim();
    }

    private static String outcome(String action) {
        if ("accept_ai_suggestion".equals(action) || "human_review_accept_ai_suggestion".equals(action)) return "accepted_ai_label";
        if ("human_review_override".equals(action)) return "human_override_needs_gold_label";
        if ("human_review_no_action".equals(action)) return "human_no_action_needs_gold_label";
        return "not_human_reviewed";
    }

    private static String required(String name) {
        String value = System.getenv(name);
        if (value == null || value.trim().isEmpty()) throw new IllegalStateException(name + " is required");
        return value.trim();
    }

    private static String value(String value) { return value == null ? "" : value; }
    private static String field(String key, String value) { return "\"" + key + "\":\"" + escape(value) + "\""; }
    private static String escape(String value) {
        return value.replace("\\", "\\\\").replace("\"", "\\\"").replace("\r", "\\r").replace("\n", "\\n");
    }
    private static String sha256(String value) throws Exception {
        byte[] digest = MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8));
        StringBuilder out = new StringBuilder();
        for (byte item : digest) out.append(String.format("%02x", item));
        return out.toString();
    }
}
