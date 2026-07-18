package org.linlinjava.litemall.db.service;

import com.github.pagehelper.PageHelper;
import org.linlinjava.litemall.db.dao.LitemallAiDemoReviewMapper;
import org.linlinjava.litemall.db.domain.LitemallAiDemoReview;
import org.springframework.stereotype.Service;

import javax.annotation.Resource;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

@Service
public class LitemallAiDemoReviewService {
    public static final String STATUS_PENDING = "pending";
    public static final String STATUS_ANALYZING = "analyzing";
    public static final String STATUS_ANALYZED = "analyzed";
    public static final String STATUS_FAILED = "failed";

    @Resource
    private LitemallAiDemoReviewMapper demoReviewMapper;

    public int add(LitemallAiDemoReview review) {
        LocalDateTime now = LocalDateTime.now();
        review.setAnalysisStatus(STATUS_PENDING);
        review.setCreatedTime(now);
        review.setUpdatedTime(now);
        review.setDeleted(false);
        return demoReviewMapper.insertSelective(review);
    }

    public LitemallAiDemoReview findById(Integer id) {
        return demoReviewMapper.selectByPrimaryKey(id);
    }

    public List<LitemallAiDemoReview> querySelective(Integer productId, String analysisStatus, Integer page, Integer limit) {
        PageHelper.startPage(page, limit);
        return demoReviewMapper.querySelective(productId, analysisStatus);
    }

    public List<LitemallAiDemoReview> queryPending(Integer limit) {
        return demoReviewMapper.queryPending(limit);
    }

    public int updateStatus(Integer id, String status) {
        return demoReviewMapper.updateStatus(id, status);
    }

    public List<Map<String, Object>> statByStatus() {
        return demoReviewMapper.statByStatus();
    }
}
