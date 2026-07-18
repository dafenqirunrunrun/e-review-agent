<template>
  <div class="ai-workbench-page ai-aggregate-page ai-platform-governance-page">
    <ai-page-header
      title="平台治理设置"
      subtitle="本页面用于管理智能体工具、审批策略、安全护栏和智能体注册。相关能力属于本地实验增强，用于展示系统可扩展性和治理边界。"
      module="高级设置"
      boundary="演示支付、演示发货、最终验收和交付检查仍由脚本与文档完成，不作为独立后台业务页面。"
    />

    <el-tabs v-model="activeTab" type="border-card" @tab-click="syncQuery">
      <el-tab-pane label="工具管理" name="tools">
        <p class="ai-section-note">集中管理本地工具注册、工具协议清单、结构校验和调用日志；导出内容是本地协议描述，不代表已接入外部 MCP。</p>
        <div class="ai-embedded-panel"><ai-enterprise-platform v-if="activeTab === 'tools'" mode-override="tool-registry" /></div>
      </el-tab-pane>
      <el-tab-pane label="审批策略" name="approval">
        <p class="ai-section-note">高风险工具动作需要人工确认。审批能力保留在工具管理页面内部，避免分散成多个菜单入口。</p>
        <div class="ai-embedded-panel"><ai-enterprise-platform v-if="activeTab === 'approval'" mode-override="tool-registry" /></div>
      </el-tab-pane>
      <el-tab-pane label="安全护栏" name="guardrails">
        <p class="ai-section-note">安全护栏展示本地输入、输出和工具调用边界，敏感信息不直接暴露到页面。</p>
        <div class="ai-embedded-panel"><ai-enterprise-platform v-if="activeTab === 'guardrails'" mode-override="guardrails" /></div>
      </el-tab-pane>
      <el-tab-pane label="智能体注册" name="agents">
        <p class="ai-section-note">展示本地智能体角色、能力、工具边界和人工确认要求。</p>
        <div class="ai-embedded-panel"><ai-enterprise-platform v-if="activeTab === 'agents'" mode-override="agent-registry" /></div>
      </el-tab-pane>
      <el-tab-pane label="配置中心" name="config">
        <p class="ai-section-note">配置中心以只读方式说明当前演示边界：不接真实支付、真实物流、真实退款或外部模型强依赖。</p>
        <div class="ai-embedded-panel"><ai-config v-if="activeTab === 'config'" /></div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script>
import AiPageHeader from '@/components/AiPageHeader'
import AiEnterprisePlatform from '@/views/ai-enterprise-platform/index'
import AiConfig from '@/views/ai-config/index'

export default {
  name: 'AiPlatformGovernance',
  components: { AiPageHeader, AiEnterprisePlatform, AiConfig },
  data() {
    return {
      activeTab: this.$route.query.tab || 'tools'
    }
  },
  watch: {
    '$route.query.tab'(value) {
      if (value && value !== this.activeTab) this.activeTab = value
    }
  },
  methods: {
    syncQuery() {
      this.$router.replace({ path: this.$route.path, query: { tab: this.activeTab }})
    }
  }
}
</script>
