<script setup lang="ts">
import { ArrowLeft, Check, Copy, FileText, X } from "@lucide/vue";
import { useRouter } from "vue-router";
import { recentRuns } from "@/data/mock";
import { useWorkspace } from "@/composables/useWorkspace";
const router = useRouter();
const { copied, selectedEvidence, copyEvidence, notify } = useWorkspace();
const run = recentRuns[0]!;
const evidence = [
  {
    code: "E1",
    title: "生产端等待持久化确认",
    source: "订单系统架构说明.pdf · p.12",
  },
  {
    code: "E2",
    title: "团队具备 Kafka 基础运维经验",
    source: "团队技术能力评估.txt · 现状",
  },
  {
    code: "C1",
    title: "重试策略存在冲突",
    source: "峰值流量与可靠性要求.md · 峰值流量",
  },
];
</script>

<template>
  <button class="text-button back-button" type="button" @click="router.back()">
    <ArrowLeft :size="15" />返回调研运行
  </button>
  <div class="run-detail-top">
    <div>
      <p class="eyebrow">RESEARCH / RUN DETAIL</p>
      <h1>{{ run.title }}</h1>
      <p class="page-subtitle">
        {{ run.id }} · {{ run.project }} · {{ run.time }}
      </p>
    </div>
    <span class="status-badge status-completed"><i />已完成</span>
  </div>
  <div class="run-metrics">
    <div>
      <span>运行耗时</span><strong>{{ run.duration }}</strong>
    </div>
    <div>
      <span>消耗 Tokens</span><strong>{{ run.tokens }}</strong>
    </div>
    <div><span>引用证据</span><strong>24</strong></div>
    <div><span>可信度</span><strong>91%</strong></div>
  </div>
  <div class="research-workspace">
    <section class="panel markdown-body">
      <p class="eyebrow">FINAL SUMMARY</p>
      <h2>结论摘要</h2>
      <p>
        结合内部业务约束与已检索证据，当前阶段建议采用 Kafka
        作为核心消息总线，并优先验证跨地域复制与积压治理能力。
      </p>
      <h3>关键判断</h3>
      <ul>
        <li>吞吐能力和团队已有经验使 Kafka 更适合当前阶段。</li>
        <li>生产端应等待持久化确认，消费端在事务提交后手动 ack。</li>
        <li>跨地域复制与长期运维成本仍需补充验证。</li>
      </ul>
      <button
        class="button button-secondary button-sm"
        type="button"
        @click="notify('报告生成接口待接入')"
      >
        <FileText :size="14" />生成报告
      </button>
    </section>
    <aside class="panel evidence-panel">
      <div class="panel-heading">
        <div>
          <h2>证据与冲突</h2>
          <p>点击证据查看引用片段</p>
        </div>
      </div>
      <button
        v-for="(item, index) in evidence"
        :key="item.code"
        class="evidence-card"
        :class="{ selected: selectedEvidence === index }"
        type="button"
        @click="selectedEvidence = index"
      >
        <div>
          <span
            class="evidence-code"
            :class="{ conflict: item.code === 'C1' }"
            >{{ item.code }}</span
          ><strong>{{ item.title }}</strong>
        </div>
        <small>{{ item.source }}</small>
      </button>
      <div v-if="selectedEvidence >= 0" class="evidence-drawer">
        <div>
          <span class="eyebrow">EVIDENCE</span>
          <h2>{{ evidence[selectedEvidence]?.title }}</h2>
          <p>
            生产端必须等待 Broker
            返回持久化确认，消费端在业务事务提交后确认消息。
          </p>
        </div>
        <div>
          <button
            class="button button-secondary button-sm"
            type="button"
            @click="copyEvidence"
          >
            <Copy :size="14" />{{ copied ? "已复制" : "复制引用" }}</button
          ><button
            class="icon-button small"
            type="button"
            @click="selectedEvidence = -1"
          >
            <X :size="17" />
          </button>
        </div>
      </div>
    </aside>
  </div>
</template>
