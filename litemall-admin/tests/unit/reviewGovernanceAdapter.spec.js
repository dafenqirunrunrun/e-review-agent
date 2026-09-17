/* eslint-env jest */
import { normalizeReviewGovernance } from '@/utils/reviewGovernanceAdapter'

describe('reviewGovernanceAdapter', () => {
  it('maps review_governance contract into review console scenario', () => {
    const scenario = normalizeReviewGovernance(
      {
        review_governance: {
          schemaVersion: 'review-governance-v1',
          reviewId: 'demo-agentic-cashback',
          productId: '1006001',
          decision: {
            code: 'suggest_action',
            label: '建议处理',
            riskLevel: 'medium',
            confidence: 0.84,
            needHumanReview: false,
            status: '已自动完成'
          },
          summary: {
            title: '疑似好评返现与评分诱导',
            reason: '风险信号和公开依据匹配，建议运营处理。',
            explanation: '审核人员可按编号查看引用来源。'
          },
          riskTypes: ['rating_manipulation'],
          evidenceStatus: 'supported',
          riskCoverage: [
            {
              riskType: 'rating_manipulation',
              label: '评分操纵',
              status: 'supported',
              statusText: '已支持',
              supportedBy: ['E1'],
              missingEvidenceTags: []
            }
          ],
          reflectionReason: '证据与风险类型匹配。',
          requiresHumanReview: false,
          riskSignals: [
            {
              riskType: 'rating_manipulation',
              label: '评分操纵',
              severity: '中',
              matchedText: 'cashback',
              reason: '存在利益诱导。'
            }
          ],
          evidenceCitations: [
            {
              id: 'E1',
              sourceName: 'FTC 16 CFR Part 465',
              sourceType: 'regulation',
              sourceLevel: 'A',
              sourceUrl: 'https://www.ecfr.gov/current/title-16/chapter-I/subchapter-D/part-465',
              sectionPath: ['Part 465', '465.4'],
              clauseId: '465.4',
              snippet: 'Paid review incentives are rating manipulation evidence.',
              riskTypes: ['rating_manipulation'],
              evidenceTags: ['rating_manipulation'],
              contentHash: 'sha256:test',
              retrieval: { mode: 'hybrid', score: 0.0317 }
            }
          ],
          process: [
            { order: 1, name: '识别是否需要严格审核', status: '完成', summary: '进入严格审核' },
            { order: 2, name: '查找可引用依据', status: '完成', summary: 'retrieved 1 policy citation' }
          ],
          recommendedActions: [
            { code: 'accept_suggestion', label: '采纳建议', style: 'primary', requiresHuman: false }
          ],
          humanReview: {
            required: false,
            reason: '当前结论和依据满足自动处理条件。',
            missingInformation: []
          }
        }
      },
      {
        key: 'cashback',
        product: '便携榨汁杯',
        orderNo: '订单 202609060018',
        rating: '5 星',
        reviewText: '客服说晒五星截图可以返 10 元。',
        actions: []
      }
    )

    expect(scenario.source).toBe('api')
    expect(scenario.status).toBe('warn')
    expect(scenario.statusText).toBe('建议处理')
    expect(scenario.decision).toBe('疑似好评返现与评分诱导')
    expect(scenario.signals[0]).toEqual({ label: '命中风险', value: '评分操纵' })
    expect(scenario.evidence[0].title).toBe('FTC 16 CFR Part 465')
    expect(scenario.evidence[0].path).toContain('A 类')
    expect(scenario.evidence[0].riskTypes).toBe('评分操纵')
    expect(scenario.evidence[0].retrieval).toBe('Hybrid / 0.0317')
    expect(scenario.evidence[0].technicalDetails[0]).toContain('Hybrid')
    expect(scenario.evidenceStatusText).toBe('证据充分')
    expect(scenario.riskCoverage[0].statusText).toBe('已支持')
    expect(scenario.showPolicyEvidence).toBe(true)
    expect(scenario.reflectionReason).toBe('证据与风险类型匹配。')
    expect(scenario.requiresHumanReview).toBe(false)
    expect(scenario.actions[0].label).toBe('采纳建议')
    expect(scenario.process[0].done).toBe(true)
  })

  it('keeps fallback scenario renderable when governance contract is incomplete', () => {
    const scenario = normalizeReviewGovernance(
      { sentiment_label: 'negative' },
      {
        key: 'legacy-review',
        product: '商品 1181000',
        orderNo: '评论 #1073',
        rating: '1 星',
        reviewText: '历史分析记录',
        actions: null
      }
    )

    expect(scenario.evidenceStatus).toBe('insufficient')
    expect(scenario.evidence).toEqual([])
    expect(scenario.signals).toEqual([])
    expect(scenario.actions).toEqual([])
    expect(scenario.process).toEqual([])
    expect(scenario.reason).toContain('完整治理结果')
  })

  it('shows partial risk coverage with readable missing evidence reason', () => {
    const scenario = normalizeReviewGovernance({
      decision: {
        code: 'manual_review',
        label: '需人工复核',
        riskLevel: 'medium',
        confidence: 0.75,
        needHumanReview: true
      },
      summary: { title: '多风险评论', reason: '需要人工确认。' },
      riskTypes: ['rating_manipulation', 'review_suppression'],
      evidenceStatus: 'mismatch',
      reflectionReason: '检测到 2 类风险，其中 1 类缺少对应政策依据：压制差评。',
      failureReasons: [
        { code: 'PARTIAL_RISK_COVERAGE', message: '检测到 2 类风险，其中 1 类缺少对应政策依据。' }
      ],
      riskCoverage: [
        { riskType: 'rating_manipulation', status: 'supported', supportedBy: ['E1'] },
        { riskType: 'review_suppression', status: 'insufficient', missingEvidenceTags: ['压制差评'] }
      ],
      evidenceCitations: [],
      humanReview: { required: true, reason: '证据不匹配，需要人工确认。' }
    })

    expect(scenario.evidenceStatusText).toBe('证据不匹配')
    expect(scenario.failureReasons[0].message).toContain('缺少对应政策依据')
    expect(scenario.riskCoverage[0].label).toBe('评分操纵')
    expect(scenario.riskCoverage[1].label).toBe('压制差评')
    expect(scenario.showPolicyEvidence).toBe(true)
  })

  it('keeps normal review simple without empty policy evidence card', () => {
    const scenario = normalizeReviewGovernance({
      decision: {
        code: 'auto_pass',
        label: '自动通过',
        riskLevel: 'low',
        confidence: 0.9,
        needHumanReview: false
      },
      summary: { title: '未发现需要拦截的风险信号', reason: '评论风险较低。' },
      riskTypes: ['normal_review'],
      evidenceStatus: 'supported',
      reflectionReason: '未命中治理风险，轻路径自动审核通过。',
      evidenceCitations: [],
      humanReview: { required: false }
    })

    expect(scenario.riskCoverage[0].label).toBe('普通评价')
    expect(scenario.showPolicyEvidence).toBe(false)
    expect(scenario.requiresHumanReview).toBe(false)
  })

  it('marks v1 records as historical without exposing raw snapshot data', () => {
    const scenario = normalizeReviewGovernance({
      schemaVersion: 'review-governance-v1',
      decision: { code: 'manual_review', label: '需人工复核', riskLevel: 'medium', confidence: 0.7 },
      summary: { title: '历史记录', reason: '历史结论。' },
      riskTypes: ['after_sales_risk'],
      evidenceStatus: 'insufficient',
      humanReview: { required: true }
    })

    expect(scenario.governanceSchemaVersion).toBe('review-governance-v1')
    expect(scenario.history.message).toContain('历史治理口径')
  })
})
