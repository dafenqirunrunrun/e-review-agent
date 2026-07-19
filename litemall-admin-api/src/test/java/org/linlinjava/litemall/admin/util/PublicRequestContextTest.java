package org.linlinjava.litemall.admin.util;

import org.junit.Assert;
import org.junit.Test;

public class PublicRequestContextTest {
    @Test
    public void sanitizeKeepsValidRequestId() {
        Assert.assertEquals("req-123.A_B:9", PublicRequestContext.sanitize("req-123.A_B:9"));
    }

    @Test
    public void sanitizeReplacesBlankRequestId() {
        String value = PublicRequestContext.sanitize("   ");
        Assert.assertNotEquals("   ", value);
        Assert.assertTrue(value.length() > 0);
    }

    @Test
    public void sanitizeReplacesCrlfRequestId() {
        String value = PublicRequestContext.sanitize("bad\r\nid");
        Assert.assertNotEquals("bad\r\nid", value);
        Assert.assertFalse(value.contains("\r"));
        Assert.assertFalse(value.contains("\n"));
    }

    @Test
    public void sanitizeReplacesTooLongRequestId() {
        StringBuilder builder = new StringBuilder();
        for (int i = 0; i < 129; i++) {
            builder.append("a");
        }
        String value = PublicRequestContext.sanitize(builder.toString());
        Assert.assertNotEquals(builder.toString(), value);
    }

    @Test
    public void sanitizeReplacesIllegalCharacters() {
        String value = PublicRequestContext.sanitize("bad request id");
        Assert.assertNotEquals("bad request id", value);
    }
}
