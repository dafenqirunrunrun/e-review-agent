import Vue from 'vue'
import Router from 'vue-router'

Vue.use(Router)

/* Layout */
import Layout from '@/views/layout/Layout'

/** note: Submenu only appear when children.length>=1
 *  detail see  router and nav implementation note
 **/

/**
* hidden: true                   if `hidden:true` will not show in the sidebar(default is false)
* alwaysShow: true               if set true, will always show the root menu, whatever its child routes length
*                                if not set alwaysShow, only more than one route under the children
*                                it will becomes nested mode, otherwise not show the root menu
* redirect: noredirect           if `redirect:noredirect` will no redirect in the breadcrumb
* name:'router-name'             the name is used by <keep-alive> (must set!!!)
* meta : {
    perms: ['GET /aaa','POST /bbb']     will control the page perms (you can set multiple perms)
    title: 'title'               the name show in submenu and breadcrumb (recommend set)
    icon: 'svg-name'             the icon show in the sidebar,
    noCache: true                if true ,the page will no be cached(default is false)
  }
**/
export const constantRoutes = [
  {
    path: '/redirect',
    component: Layout,
    hidden: true,
    children: [
      {
        path: '/redirect/:path(.*)',
        component: () => import('@/views/redirect/index')
      }
    ]
  },
  {
    path: '/login',
    component: () => import('@/views/login/index'),
    hidden: true
  },
  {
    path: '/auth-redirect',
    component: () => import('@/views/login/authredirect'),
    hidden: true
  },
  {
    path: '/404',
    component: () => import('@/views/errorPage/404'),
    hidden: true
  },
  {
    path: '/401',
    component: () => import('@/views/errorPage/401'),
    hidden: true
  },
  {
    path: '',
    component: Layout,
    redirect: 'dashboard',
    children: [
      {
        path: 'dashboard',
        component: () => import('@/views/dashboard/index'),
        name: 'Dashboard',
        meta: { title: 'app.menu.dashboard', icon: 'dashboard', affix: true }
      }
    ]
  }
]

export const asyncRoutes = [
  {
    path: '/user',
    component: Layout,
    redirect: 'noredirect',
    alwaysShow: true,
    name: 'userManage',
    meta: {
      title: 'app.menu.user',
      icon: 'chart'
    },
    children: [
      {
        path: 'user',
        component: () => import('@/views/user/user'),
        name: 'user',
        meta: {
          perms: ['GET /admin/user/list'],
          title: 'app.menu.user_user',
          noCache: true
        }
      },
      {
        path: 'address',
        component: () => import('@/views/user/address'),
        name: 'address',
        meta: {
          perms: ['GET /admin/address/list'],
          title: 'app.menu.user_address',
          noCache: true
        }
      },
      {
        path: 'collect',
        component: () => import('@/views/user/collect'),
        name: 'collect',
        meta: {
          perms: ['GET /admin/collect/list'],
          title: 'app.menu.user_collect',
          noCache: true
        }
      },
      {
        path: 'footprint',
        component: () => import('@/views/user/footprint'),
        name: 'footprint',
        meta: {
          perms: ['GET /admin/footprint/list'],
          title: 'app.menu.user_footprint',
          noCache: true
        }
      },
      {
        path: 'history',
        component: () => import('@/views/user/history'),
        name: 'history',
        meta: {
          perms: ['GET /admin/history/list'],
          title: 'app.menu.user_history',
          noCache: true
        }
      },
      {
        path: 'feedback',
        component: () => import('@/views/user/feedback'),
        name: 'feedback',
        meta: {
          perms: ['GET /admin/feedback/list'],
          title: 'app.menu.user_feedback',
          noCache: true
        }
      }
    ]
  },

  {
    path: '/mall',
    component: Layout,
    redirect: 'noredirect',
    alwaysShow: true,
    name: 'mallManage',
    meta: {
      title: 'app.menu.mall',
      icon: 'chart'
    },
    children: [
      {
        path: 'region',
        component: () => import('@/views/mall/region'),
        name: 'region',
        meta: {
          title: 'app.menu.mall_region',
          noCache: true
        }
      },
      {
        path: 'brand',
        component: () => import('@/views/mall/brand'),
        name: 'brand',
        meta: {
          perms: ['GET /admin/brand/list', 'POST /admin/brand/create', 'GET /admin/brand/read', 'POST /admin/brand/update', 'POST /admin/brand/delete'],
          title: 'app.menu.mall_brand',
          noCache: true
        }
      },
      {
        path: 'category',
        component: () => import('@/views/mall/category'),
        name: 'category',
        meta: {
          perms: ['GET /admin/category/list', 'POST /admin/category/create', 'GET /admin/category/read', 'POST /admin/category/update', 'POST /admin/category/delete'],
          title: 'app.menu.mall_category',
          noCache: true
        }
      },
      {
        path: 'order',
        component: () => import('@/views/mall/order'),
        name: 'order',
        meta: {
          perms: ['GET /admin/order/list', 'GET /admin/order/detail', 'POST /admin/order/ship', 'POST /admin/order/refund', 'POST /admin/order/delete', 'POST /admin/order/reply'],
          title: 'app.menu.mall_order',
          noCache: true
        }
      },
      {
        path: 'aftersale',
        component: () => import('@/views/mall/aftersale'),
        name: 'aftersale',
        meta: {
          perms: ['GET /admin/aftersale/list', 'GET /admin/aftersale/detail', 'POST /admin/order/receive', 'POST /admin/aftersale/complete', 'POST /admin/aftersale/reject'],
          title: 'app.menu.mall_aftersale',
          noCache: true
        }
      },
      {
        path: 'issue',
        component: () => import('@/views/mall/issue'),
        name: 'issue',
        meta: {
          perms: ['GET /admin/issue/list', 'POST /admin/issue/create', 'GET /admin/issue/read', 'POST /admin/issue/update', 'POST /admin/issue/delete'],
          title: 'app.menu.mall_issue',
          noCache: true
        }
      },
      {
        path: 'keyword',
        component: () => import('@/views/mall/keyword'),
        name: 'keyword',
        meta: {
          perms: ['GET /admin/keyword/list', 'POST /admin/keyword/create', 'GET /admin/keyword/read', 'POST /admin/keyword/update', 'POST /admin/keyword/delete'],
          title: 'app.menu.mall_keyword',
          noCache: true
        }
      }
    ]
  },

  {
    path: '/goods',
    component: Layout,
    redirect: 'noredirect',
    alwaysShow: true,
    name: 'goodsManage',
    meta: {
      title: 'app.menu.goods',
      icon: 'chart'
    },
    children: [
      {
        path: 'list',
        component: () => import('@/views/goods/list'),
        name: 'goodsList',
        meta: {
          perms: ['GET /admin/goods/list', 'POST /admin/goods/delete'],
          title: 'app.menu.goods_list',
          noCache: true
        }
      },
      {
        path: 'create',
        component: () => import('@/views/goods/create'),
        name: 'goodsCreate',
        meta: {
          perms: ['POST /admin/goods/create'],
          title: 'app.menu.goods_create',
          noCache: true
        }
      },
      {
        path: 'edit',
        component: () => import('@/views/goods/edit'),
        name: 'goodsEdit',
        meta: {
          perms: ['GET /admin/goods/detail', 'POST /admin/goods/update', 'POST /admin/goods/catAndBrand'],
          title: 'app.menu.goods_edit',
          noCache: true
        },
        hidden: true
      },
      {
        path: 'comment',
        component: () => import('@/views/goods/comment'),
        name: 'goodsComment',
        meta: {
          perms: ['GET /admin/comment/list', 'POST /admin/comment/delete'],
          title: 'app.menu.goods_comment',
          noCache: true
        }
      }
    ]
  },
  {
    path: '/promotion',
    component: Layout,
    redirect: 'noredirect',
    alwaysShow: true,
    name: 'promotionManage',
    meta: {
      title: 'app.menu.promotion',
      icon: 'chart'
    },
    children: [
      {
        path: 'ad',
        component: () => import('@/views/promotion/ad'),
        name: 'ad',
        meta: {
          perms: ['GET /admin/ad/list', 'POST /admin/ad/create', 'GET /admin/ad/read', 'POST /admin/ad/update', 'POST /admin/ad/delete'],
          title: 'app.menu.promotion_ad',
          noCache: true
        }
      },
      {
        path: 'coupon',
        component: () => import('@/views/promotion/coupon'),
        name: 'coupon',
        meta: {
          perms: ['GET /admin/coupon/list', 'POST /admin/coupon/create', 'POST /admin/coupon/update', 'POST /admin/coupon/delete'],
          title: 'app.menu.promotion_coupon',
          noCache: true
        }
      },
      {
        path: 'couponDetail',
        component: () => import('@/views/promotion/couponDetail'),
        name: 'couponDetail',
        meta: {
          perms: ['GET /admin/coupon/list', 'GET /admin/coupon/listuser'],
          title: 'app.menu.promotion_coupon_detail',
          noCache: true
        },
        hidden: true
      },
      {
        path: 'topic',
        component: () => import('@/views/promotion/topic'),
        name: 'topic',
        meta: {
          perms: ['GET /admin/topic/list', 'POST /admin/topic/create', 'GET /admin/topic/read', 'POST /admin/topic/update', 'POST /admin/topic/delete'],
          title: 'app.menu.promotion_topic',
          noCache: true
        }
      },
      {
        path: 'topic-create',
        component: () => import('@/views/promotion/topicCreate'),
        name: 'topicCreate',
        meta: {
          perms: ['POST /admin/topic/create'],
          title: 'app.menu.promotion_topic_create',
          noCache: true
        },
        hidden: true
      },
      {
        path: 'topic-edit',
        component: () => import('@/views/promotion/topicEdit'),
        name: 'topicEdit',
        meta: {
          perms: ['GET /admin/topic/read', 'POST /admin/topic/update'],
          title: 'app.menu.promotion_topic_edit',
          noCache: true
        },
        hidden: true
      },
      {
        path: 'groupon-rule',
        component: () => import('@/views/promotion/grouponRule'),
        name: 'grouponRule',
        meta: {
          perms: ['GET /admin/groupon/list', 'POST /admin/groupon/create', 'POST /admin/groupon/update', 'POST /admin/groupon/delete'],
          title: 'app.menu.promotion_groupon_rule',
          noCache: true
        }
      },
      {
        path: 'groupon-activity',
        component: () => import('@/views/promotion/grouponActivity'),
        name: 'grouponActivity',
        meta: {
          perms: ['GET /admin/groupon/listRecord'],
          title: 'app.menu.promotion_groupon_activity',
          noCache: true
        }
      }
    ]
  },

  {
    path: '/sys',
    component: Layout,
    redirect: 'noredirect',
    alwaysShow: true,
    name: 'sysManage',
    meta: {
      title: 'app.menu.sys',
      icon: 'chart'
    },
    children: [
      {
        path: 'admin',
        component: () => import('@/views/sys/admin'),
        name: 'admin',
        meta: {
          perms: ['GET /admin/admin/list', 'POST /admin/admin/create', 'POST /admin/admin/update', 'POST /admin/admin/delete'],
          title: 'app.menu.sys_admin',
          noCache: true
        }
      },
      {
        path: 'notice',
        component: () => import('@/views/sys/notice'),
        name: 'sysNotice',
        meta: {
          perms: ['GET /admin/notice/list', 'POST /admin/notice/create', 'POST /admin/notice/update', 'POST /admin/notice/delete'],
          title: 'app.menu.sys_notice',
          noCache: true
        }
      },
      {
        path: 'log',
        component: () => import('@/views/sys/log'),
        name: 'log',
        meta: {
          perms: ['GET /admin/log/list'],
          title: 'app.menu.sys_log',
          noCache: true
        }
      },
      {
        path: 'role',
        component: () => import('@/views/sys/role'),
        name: 'role',
        meta: {
          perms: ['GET /admin/role/list', 'POST /admin/role/create', 'POST /admin/role/update', 'POST /admin/role/delete', 'GET /admin/role/permissions', 'POST /admin/role/permissions'],
          title: 'app.menu.sys_role',
          noCache: true
        }
      },
      {
        path: 'os',
        component: () => import('@/views/sys/os'),
        name: 'os',
        meta: {
          perms: ['GET /admin/storage/list', 'POST /admin/storage/create', 'POST /admin/storage/update', 'POST /admin/storage/delete'],
          title: 'app.menu.sys_os',
          noCache: true
        }
      }
    ]
  },

  {
    path: '/config',
    component: Layout,
    redirect: 'noredirect',
    alwaysShow: true,
    name: 'configManage',
    meta: {
      title: 'app.menu.config',
      icon: 'chart'
    },
    children: [
      {
        path: 'mall',
        component: () => import('@/views/config/mall'),
        name: 'configMall',
        meta: {
          perms: ['GET /admin/config/mall', 'POST /admin/config/mall'],
          title: 'app.menu.config_mall',
          noCache: true
        }
      },
      {
        path: 'express',
        component: () => import('@/views/config/express'),
        name: 'configExpress',
        meta: {
          perms: ['GET /admin/config/express', 'POST /admin/config/express'],
          title: 'app.menu.config_express',
          noCache: true
        }
      },
      {
        path: 'order',
        component: () => import('@/views/config/order'),
        name: 'configOrder',
        meta: {
          perms: ['GET /admin/config/order', 'POST /admin/config/order'],
          title: 'app.menu.config_order',
          noCache: true
        }
      },
      {
        path: 'wx',
        component: () => import('@/views/config/wx'),
        name: 'configWx',
        meta: {
          perms: ['GET /admin/config/wx', 'POST /admin/config/wx'],
          title: 'app.menu.config_wx',
          noCache: true
        }
      }
    ]
  },

  {
    path: '/stat',
    component: Layout,
    redirect: 'noredirect',
    alwaysShow: true,
    name: 'statManage',
    meta: {
      title: 'app.menu.stat',
      icon: 'chart'
    },
    children: [
      {
        path: 'user',
        component: () => import('@/views/stat/user'),
        name: 'statUser',
        meta: {
          perms: ['GET /admin/stat/user'],
          title: 'app.menu.stat_user',
          noCache: true
        }
      },
      {
        path: 'order',
        component: () => import('@/views/stat/order'),
        name: 'statOrder',
        meta: {
          perms: ['GET /admin/stat/order'],
          title: 'app.menu.stat_order',
          noCache: true
        }
      },
      {
        path: 'goods',
        component: () => import('@/views/stat/goods'),
        name: 'statGoods',
        meta: {
          perms: ['GET /admin/stat/goods'],
          title: 'app.menu.stat_goods',
          noCache: true
        }
      }
    ]
  },
  {
    path: '/ai-workbench',
    component: Layout,
    redirect: '/ai-workbench/home',
    alwaysShow: true,
    name: 'aiWorkbench',
    meta: {
      title: 'app.menu.ai_workbench',
      icon: 'chart'
    },
    children: [
      {
        path: 'home',
        component: () => import('@/views/ai-workbench-home/index'),
        name: 'aiWorkbenchHome',
        meta: {
          perms: ['GET /admin/ai/review/list'],
          title: 'app.menu.ai_workbench_home',
          noCache: true
        }
      },
      {
        path: 'governance-flow',
        component: () => import('@/views/ai-governance-flow/index'),
        name: 'aiGovernanceFlow',
        meta: {
          perms: ['GET /admin/ai/review/list'],
          title: 'app.menu.ai_governance_flow',
          noCache: true
        }
      },
      {
        path: 'observability',
        component: () => import('@/views/ai-observability/index'),
        name: 'aiObservability',
        meta: {
          perms: ['GET /admin/ai/review/list'],
          title: 'app.menu.ai_observability',
          noCache: true
        }
      },
      {
        path: 'knowledge-quality',
        component: () => import('@/views/ai-knowledge-quality/index'),
        name: 'aiKnowledgeQuality',
        meta: {
          perms: ['GET /admin/ai/review/list'],
          title: 'app.menu.ai_knowledge_quality',
          noCache: true
        }
      },
      {
        path: 'platform-governance',
        component: () => import('@/views/ai-platform-governance/index'),
        name: 'aiPlatformGovernance',
        meta: {
          perms: ['GET /admin/ai/review/list'],
          title: 'app.menu.ai_platform_governance',
          noCache: true
        }
      },
      {
        path: 'dashboard',
        redirect: '/ai-workbench/home',
        name: 'aiDashboard',
        hidden: true,
        meta: {
          perms: ['GET /admin/ai/review/list'],
          title: 'app.menu.ai_dashboard',
          noCache: true
        }
      },
      {
        path: 'review',
        component: () => import('@/views/ai-review/index'),
        name: 'aiReview',
        hidden: true,
        meta: {
          perms: ['POST /admin/ai/review/analyze', 'GET /admin/ai/review/list'],
          title: 'app.menu.ai_review_analyze',
          noCache: true
        }
      },
      {
        path: '/ai-demo-review/create',
        component: () => import('@/views/ai-demo-review/create'),
        name: 'aiDemoReviewCreate',
        hidden: true,
        meta: {
          perms: ['POST /admin/ai/demo-review/create', 'GET /admin/ai/demo-review/list'],
          title: 'app.menu.ai_demo_review',
          noCache: true
        }
      },
      {
        path: 'patrol',
        redirect: '/ai-workbench/governance-flow?tab=patrol',
        name: 'aiPatrol',
        hidden: true,
        meta: {
          perms: ['GET /admin/ai/review/list'],
          title: 'app.menu.ai_patrol',
          noCache: true
        }
      },
      {
        path: 'risk',
        redirect: '/ai-workbench/governance-flow?tab=risk',
        name: 'aiRisk',
        hidden: true,
        meta: {
          perms: ['GET /admin/ai/review/list'],
          title: 'app.menu.ai_risk',
          noCache: true
        }
      },
      {
        path: 'operation',
        redirect: '/ai-workbench/governance-flow?tab=operation',
        name: 'aiOperation',
        hidden: true,
        meta: {
          perms: ['GET /admin/ai/review/list'],
          title: 'app.menu.ai_operation',
          noCache: true
        }
      },
      {
        path: 'agent-trace',
        redirect: '/ai-workbench/observability?tab=trace',
        name: 'aiAgentTrace',
        hidden: true,
        meta: {
          perms: ['GET /admin/ai/review/list'],
          title: 'app.menu.ai_agent_trace',
          noCache: true
        }
      },
      {
        path: 'agent-eval',
        redirect: '/ai-workbench/observability?tab=eval',
        name: 'aiAgentEval',
        hidden: true,
        meta: {
          perms: ['GET /admin/ai/review/list'],
          title: 'app.menu.ai_agent_eval',
          noCache: true
        }
      },
      {
        path: 'agentops',
        redirect: '/ai-workbench/observability?tab=agentops',
        name: 'aiAgentOps',
        hidden: true,
        meta: {
          perms: ['GET /admin/ai/review/list'],
          title: 'app.menu.ai_agentops',
          noCache: true,
          enterpriseMode: 'agentops'
        }
      },
      {
        path: 'history',
        component: () => import('@/views/ai-history/index'),
        name: 'aiHistory',
        hidden: true,
        meta: {
          perms: ['GET /admin/ai/review/list'],
          title: 'app.menu.ai_history',
          noCache: true
        }
      },
      {
        path: 'case-knowledge',
        redirect: '/ai-workbench/knowledge-quality?tab=case',
        name: 'aiCaseKnowledge',
        hidden: true,
        meta: {
          perms: ['GET /admin/ai/review/list'],
          title: 'app.menu.ai_case_knowledge',
          noCache: true
        }
      },
      {
        path: 'memory-center',
        redirect: '/ai-workbench/knowledge-quality?tab=memory',
        name: 'aiMemoryCenter',
        hidden: true,
        meta: {
          perms: ['GET /admin/ai/review/list'],
          title: 'app.menu.ai_memory_center',
          noCache: true,
          enterpriseMode: 'memory'
        }
      },
      {
        path: 'tool-registry',
        redirect: '/ai-workbench/platform-governance?tab=tools',
        name: 'aiToolRegistry',
        hidden: true,
        meta: {
          perms: ['GET /admin/ai/review/list'],
          title: 'app.menu.ai_tool_registry',
          noCache: true,
          enterpriseMode: 'tool-registry'
        }
      },
      {
        path: 'guardrails',
        redirect: '/ai-workbench/platform-governance?tab=guardrails',
        name: 'aiGuardrails',
        hidden: true,
        meta: {
          perms: ['GET /admin/ai/review/list'],
          title: 'app.menu.ai_guardrails',
          noCache: true,
          enterpriseMode: 'guardrails'
        }
      },
      {
        path: 'agent-registry',
        redirect: '/ai-workbench/platform-governance?tab=agents',
        name: 'aiAgentRegistry',
        hidden: true,
        meta: {
          perms: ['GET /admin/ai/review/list'],
          title: 'app.menu.ai_agent_registry',
          noCache: true,
          enterpriseMode: 'agent-registry'
        }
      },
      {
        path: 'rag-quality',
        redirect: '/ai-workbench/knowledge-quality?tab=rag',
        name: 'aiRagQuality',
        hidden: true,
        meta: {
          perms: ['GET /admin/ai/review/list'],
          title: 'app.menu.ai_rag_quality',
          noCache: true,
          enterpriseMode: 'rag-quality'
        }
      },
      {
        path: 'config',
        redirect: '/ai-workbench/platform-governance?tab=config',
        name: 'aiConfig',
        hidden: true,
        meta: {
          perms: ['GET /admin/ai/review/list'],
          title: 'app.menu.ai_config',
          noCache: true
        }
      }
    ]
  },
  {
    path: '/ai-review',
    component: Layout,
    redirect: '/ai-workbench/review',
    hidden: true,
    children: [
      {
        path: 'index',
        component: () => import('@/views/ai-review/index'),
        name: 'aiReviewLegacy',
        meta: {
          perms: ['POST /admin/ai/review/analyze', 'GET /admin/ai/review/list'],
          title: 'app.menu.ai_review_analyze',
          noCache: true
        }
      }
    ]
  },
  {
    path: '/profile',
    component: Layout,
    redirect: 'noredirect',
    alwaysShow: true,
    children: [
      {
        path: 'password',
        component: () => import('@/views/profile/password'),
        name: 'password',
        meta: { title: 'app.menu.profile_password', noCache: true }
      },
      {
        path: 'notice',
        component: () => import('@/views/profile/notice'),
        name: 'notice',
        meta: { title: 'app.menu.profile_notice', noCache: true }
      }
    ],
    hidden: true
  },

  { path: '*', redirect: '/404', hidden: true }
]

const createRouter = () => new Router({
  // mode: 'history', // require service support
  scrollBehavior: () => ({ y: 0 }),
  routes: constantRoutes
})

const router = createRouter()

// Detail see: vue-router issue note
export function resetRouter() {
  const newRouter = createRouter()
  router.matcher = newRouter.matcher // reset router
}

export default router
