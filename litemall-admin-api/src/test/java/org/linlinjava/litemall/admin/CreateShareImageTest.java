package org.linlinjava.litemall.admin;

import org.junit.Assert;
import org.junit.Assume;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.linlinjava.litemall.core.qcode.QCodeService;
import org.linlinjava.litemall.db.domain.LitemallGoods;
import org.linlinjava.litemall.db.service.LitemallGoodsService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.junit4.SpringJUnit4ClassRunner;
import org.springframework.test.context.web.WebAppConfiguration;

import java.util.List;

@WebAppConfiguration
@RunWith(SpringJUnit4ClassRunner.class)
@SpringBootTest
public class CreateShareImageTest {
    @Autowired
    QCodeService qCodeService;
    @Autowired
    LitemallGoodsService litemallGoodsService;

    @Test
    public void test() {
        List<LitemallGoods> goods = litemallGoodsService.querySelective(null, null, null, 1, 1, "id", "asc");
        Assume.assumeFalse("Share image test skipped because the local database has no goods fixture.", goods.isEmpty());

        LitemallGoods good = goods.get(0);
        String result = qCodeService.createGoodShareImage(good.getId().toString(), good.getPicUrl(), good.getName());
        Assert.assertNotNull(result);
    }
}
