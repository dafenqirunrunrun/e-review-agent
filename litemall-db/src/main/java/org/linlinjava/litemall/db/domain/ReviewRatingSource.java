package org.linlinjava.litemall.db.domain;

public enum ReviewRatingSource {
    USER_PROVIDED,
    UNKNOWN;

    public static boolean isUserProvided(String value) {
        return USER_PROVIDED.name().equals(value);
    }
}
