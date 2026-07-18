package org.linlinjava.litemall.db.service;

import com.github.pagehelper.PageHelper;
import org.linlinjava.litemall.db.dao.LitemallAiReviewRiskTaskMapper;
import org.linlinjava.litemall.db.domain.LitemallAiReviewRiskTask;
import org.springframework.stereotype.Service;

import javax.annotation.Resource;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

@Service
public class LitemallAiReviewRiskTaskService {
    @Resource
    private LitemallAiReviewRiskTaskMapper riskTaskMapper;

    public int add(LitemallAiReviewRiskTask task) {
        LocalDateTime now = LocalDateTime.now();
        task.setStatus(task.getStatus() == null ? "pending" : task.getStatus());
        task.setCreatedTime(now);
        task.setUpdatedTime(now);
        task.setDeleted(false);
        return riskTaskMapper.insertSelective(task);
    }

    public LitemallAiReviewRiskTask findById(Integer id) {
        return riskTaskMapper.selectByPrimaryKey(id);
    }

    public LitemallAiReviewRiskTask findByAnalysisAndType(Integer analysisId, String riskType) {
        return riskTaskMapper.findByAnalysisAndType(analysisId, riskType);
    }

    public List<LitemallAiReviewRiskTask> querySelective(String riskLevel, String riskType, String status, Integer page, Integer limit) {
        PageHelper.startPage(page, limit);
        return riskTaskMapper.querySelective(riskLevel, riskType, status);
    }

    public int updateStatus(Integer id, String status, String handler, String handleNote) {
        return riskTaskMapper.updateStatus(id, status, handler, handleNote);
    }

    public List<Map<String, Object>> statByStatus() {
        return riskTaskMapper.statByStatus();
    }

    public List<Map<String, Object>> statByLevel() {
        return riskTaskMapper.statByLevel();
    }
}
