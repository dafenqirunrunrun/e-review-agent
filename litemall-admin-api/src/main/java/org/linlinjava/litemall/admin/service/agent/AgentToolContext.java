package org.linlinjava.litemall.admin.service.agent;

import java.util.HashMap;
import java.util.Map;

public class AgentToolContext {
    private final Map<String, Object> values = new HashMap<String, Object>();

    public AgentToolContext put(String key, Object value) {
        values.put(key, value);
        return this;
    }

    public Object get(String key) {
        return values.get(key);
    }

    public Map<String, Object> values() {
        return values;
    }
}
