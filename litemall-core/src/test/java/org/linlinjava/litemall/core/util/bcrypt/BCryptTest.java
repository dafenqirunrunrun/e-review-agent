package org.linlinjava.litemall.core.util.bcrypt;

import org.junit.Assert;
import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.ExpectedException;

public class BCryptTest {

    @Rule
    public final ExpectedException thrown = ExpectedException.none();

    @Test
    public void testHashpwSaltIsNull() throws IllegalArgumentException {
        thrown.expect(IllegalArgumentException.class);
        BCrypt.hashpw("foo", null);
    }

    @Test
    public void testHashpwSaltTooShort() throws IllegalArgumentException {
        thrown.expect(IllegalArgumentException.class);
        BCrypt.hashpw("foo", "foo");
    }

    @Test
    public void testHashpwInvalidSaltVersion() throws IllegalArgumentException {
        thrown.expect(IllegalArgumentException.class);
        BCrypt.hashpw("foo", "+2a$10$.....................");
    }

    @Test
    public void testHashpwInvalidSaltVersion2() throws IllegalArgumentException {
        thrown.expect(IllegalArgumentException.class);
        BCrypt.hashpw("foo", "$1a$10$.....................");
    }

    @Test
    public void testHashpwInvalidSaltRevision() throws IllegalArgumentException {
        thrown.expect(IllegalArgumentException.class);
        BCrypt.hashpw("foo", "$2+$10$.....................");
    }

    @Test
    public void testHashpwInvalidSaltRevision2() throws IllegalArgumentException {
        thrown.expect(IllegalArgumentException.class);
        BCrypt.hashpw("foo", "$2a+10$.....................");
    }

    @Test
    public void testHashpwSaltTooShort2() throws IllegalArgumentException {
        thrown.expect(IllegalArgumentException.class);
        BCrypt.hashpw("foo", "$2a$10+.....................");
    }

    @Test
    public void testHashpwMissingSaltRounds() throws IllegalArgumentException {
        thrown.expect(IllegalArgumentException.class);
        BCrypt.hashpw("foo", "$2$a10$.....................");
    }

    @Test
    public void testHashpwTooLittleRounds() throws IllegalArgumentException {
        thrown.expect(IllegalArgumentException.class);
        BCrypt.hashpw("foo", "$2a$03$......................");
    }

    @Test
    public void testHashpwTooManyRounds() throws IllegalArgumentException {
        thrown.expect(IllegalArgumentException.class);
        BCrypt.hashpw("foo", "$2a$32$......................");
    }

    @Test
    public void testHashpw() {
        Assert.assertEquals(
                "$2a$10$......................0li5vIK0lccG/IXHAOP2wBncDW/oa2u",
                BCrypt.hashpw("foo", "$2a$10$......................"));

        Assert.assertEquals(
                "$2$09$......................GlnmyWmDnFB.MnSSUnFsiPvHsC2KPBm",
                BCrypt.hashpw("foo", "$2$09$......................"));
    }

    @Test
    public void testGensalt() {
        String defaultSalt = BCrypt.gensalt();
        String roundsSalt = BCrypt.gensalt(9);

        Assert.assertTrue(defaultSalt.matches("\\$2a\\$10\\$[./A-Za-z0-9]{22}"));
        Assert.assertTrue(roundsSalt.matches("\\$2a\\$09\\$[./A-Za-z0-9]{22}"));
        Assert.assertNotEquals(defaultSalt, BCrypt.gensalt());
    }

    @Test
    public void testGensaltTooLittleRounds() throws IllegalArgumentException {
        thrown.expect(IllegalArgumentException.class);
        BCrypt.gensalt(3);
    }

    @Test
    public void testGensaltTooManyRounds() throws IllegalArgumentException {
        thrown.expect(IllegalArgumentException.class);
        BCrypt.gensalt(32);
    }

    @Test
    public void testCheckpw() {
        Assert.assertFalse(BCrypt.checkpw("foo", "$2a$10$......................"));

        final String hashed = BCrypt.hashpw("foo", BCrypt.gensalt());
        Assert.assertTrue(BCrypt.checkpw("foo", hashed));
        Assert.assertFalse(BCrypt.checkpw("bar", hashed));
    }
}
