package org.linlinjava.litemall.core;

import org.junit.Assume;

import java.util.ArrayList;
import java.util.List;

final class ExternalStorageTestSupport {
    private static final String ENABLE_ENV = "E_REVIEW_EXTERNAL_STORAGE_TESTS";
    private static final String ENABLE_PROPERTY = "e.review.external.storage.tests";

    private ExternalStorageTestSupport() {
    }

    static void assumeProviderReady(String provider, String... requiredEnvVars) {
        boolean enabled = Boolean.parseBoolean(System.getenv(ENABLE_ENV))
                || Boolean.getBoolean(ENABLE_PROPERTY);
        Assume.assumeTrue(
                "External storage integration tests are skipped by default. Set "
                        + ENABLE_ENV + "=true or -D" + ENABLE_PROPERTY + "=true to enable.",
                enabled);

        List<String> missing = new ArrayList<>();
        for (String envVar : requiredEnvVars) {
            if (isBlank(System.getenv(envVar))) {
                missing.add(envVar);
            }
        }
        Assume.assumeTrue(
                provider + " storage integration test skipped; missing environment variables: " + missing,
                missing.isEmpty());
    }

    private static boolean isBlank(String value) {
        return value == null || value.trim().isEmpty();
    }
}
