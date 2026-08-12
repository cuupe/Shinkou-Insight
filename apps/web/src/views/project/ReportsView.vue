<script setup lang="ts">
import {
  CheckCircle2,
  Download,
  FileText,
  SlidersHorizontal,
} from "@lucide/vue";
import PageHeader from "@/components/common/PageHeader.vue";
import { useWorkspace } from "@/composables/useWorkspace";
const { reports, notify } = useWorkspace();
</script>

<template>
  <PageHeader
    eyebrow="PROJECT / OUTPUT"
    title="报告"
    subtitle="把可验证的证据组织成可执行的决策依据"
    ><template #action
      ><button
        class="button button-secondary"
        type="button"
        @click="notify('导出接口待接入')"
      >
        <Download :size="16" />导出报告
      </button></template
    ></PageHeader
  >
  <div class="reports-layout">
    <section class="panel reports-list-panel">
      <div class="panel-heading">
        <div>
          <h2>全部报告</h2>
          <p>{{ reports.length }} 份报告 · 按更新时间排序</p>
        </div>
        <button
          class="icon-button small"
          type="button"
          @click="notify('报告筛选接口待接入')"
        >
          <SlidersHorizontal :size="16" />
        </button>
      </div>
      <div class="report-list full-list">
        <button
          v-for="report in reports"
          :key="report.id"
          class="report-item report-item-selected"
          type="button"
        >
          <span class="report-file"><FileText :size="17" /></span
          ><span
            ><strong>{{ report.title }}</strong
            ><small>{{ report.project }} · {{ report.updated }}</small
            ><em>{{ report.version }} · {{ report.citations }} 条引用</em></span
          ><span
            class="status-badge"
            :class="
              report.status === '已发布' ? 'status-indexed' : 'status-muted'
            "
            ><i />{{ report.status }}</span
          >
        </button>
      </div>
    </section>
    <section class="panel report-reader">
      <div class="reader-toolbar">
        <span class="status-badge status-indexed"><i />已发布 · v1.4</span
        ><button
          class="text-button"
          type="button"
          @click="notify('报告编辑接口待接入')"
        >
          编辑
        </button>
      </div>
      <article class="markdown-body">
        <p class="eyebrow">TECHNICAL DECISION REPORT</p>
        <h2>消息队列技术选型建议</h2>
        <p class="lead">
          结合内部业务约束与现有团队能力，建议当前阶段采用 Kafka
          作为核心消息总线，并以明确的可靠性边界控制迁移风险。
        </p>
        <hr />
        <h3>01 / 执行摘要</h3>
        <p>
          Kafka
          在吞吐能力、生态成熟度和团队已有经验之间取得了更好的平衡。RabbitMQ
          在低延迟与简单路由场景中仍有优势。
        </p>
        <div class="recommendation-box">
          <span class="quick-icon teal-bg"><CheckCircle2 :size="18" /></span>
          <div>
            <strong>推荐方案：Kafka</strong>
            <p>优先验证跨地域复制与积压治理，完成后进入灰度迁移。</p>
          </div>
        </div>
      </article>
    </section>
  </div>
</template>
