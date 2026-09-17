package org.linlinjava.litemall.core;

import org.apache.commons.logging.Log;
import org.apache.commons.logging.LogFactory;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.linlinjava.litemall.core.storage.TencentStorage;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.core.io.Resource;
import org.springframework.test.context.junit4.SpringRunner;
import org.springframework.test.context.web.WebAppConfiguration;

import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.net.URL;
import java.util.Objects;

@WebAppConfiguration
@RunWith(SpringRunner.class)
@SpringBootTest
public class TencentStorageTest {

    private Log logger = LogFactory.getLog(TencentStorageTest.class);
    @Autowired
    private TencentStorage tencentStorage;

    @Test
    public void test() throws IOException {
        ExternalStorageTestSupport.assumeProviderReady(
                "Tencent",
                "LITEMALL_STORAGE_TENCENT_SECRET_ID",
                "LITEMALL_STORAGE_TENCENT_SECRET_KEY",
                "LITEMALL_STORAGE_TENCENT_REGION",
                "LITEMALL_STORAGE_TENCENT_BUCKET_NAME");
        URL testResource = Objects.requireNonNull(getClass().getClassLoader().getResource("litemall.png"));
        String test = testResource.getFile();
        File testFile = new File(test);
        tencentStorage.store(new FileInputStream(test), testFile.length(), "image/png", "litemall.png");
        Resource resource = tencentStorage.loadAsResource("litemall.png");
        String url = tencentStorage.generateUrl("litemall.png");
        logger.info("test file " + test);
        logger.info("store file " + resource.getURI());
        logger.info("generate url " + url);
    }

}
