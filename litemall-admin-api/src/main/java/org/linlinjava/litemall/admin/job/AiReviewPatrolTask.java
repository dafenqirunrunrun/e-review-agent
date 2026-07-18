package org.linlinjava.litemall.admin.job;

import org.linlinjava.litemall.admin.service.AiReviewPatrolService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Component
public class AiReviewPatrolTask {
    @Autowired
    private AiReviewPatrolService patrolService;

    @Scheduled(fixedDelayString = "${ai.patrol.fixed-delay:30000}")
    public void patrol() {
        if (patrolService.isEnabled()) {
            patrolService.runOnce();
        }
    }
}
