<script setup lang="ts">
import {
  ArrowRight,
  CheckCircle2,
  FileText,
  Search,
  SlidersHorizontal,
} from "@lucide/vue";
import { ref } from "vue";
import PageHeader from "@/components/common/PageHeader.vue";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useWorkspace } from "@/composables/useWorkspace";
import { retrievalApi } from "@/api/retrieval";
import type { KnowledgeSearchItem } from "@/api/types";
const {
  playgroundQuery,
  retrievalMode,
  topK,
  rerank,
  notify,
  workspaceId,
  projectId,
} = useWorkspace();
type RetrievalResult = {
  rank: number;
  source: string;
  title: string;
  score: string;
  vector: string;
  keyword: string;
  fusion: string;
  reranked: boolean;
  text: string;
};
const retrievalModes = [
  { label: "Hybrid", value: "HYBRID" },
  { label: "Vector", value: "VECTOR" },
  { label: "Keyword", value: "KEYWORD" },
];
const retrievalResults = ref<RetrievalResult[]>([]);
const isSearching = ref(false);
const selectedRank = ref<number | null>(null);
const parameterOpen = ref(false);
const parameterMode = ref(retrievalMode.value);
const parameterTopK = ref(topK.value);
const parameterRerank = ref(rerank.value);
const evidenceOpen = ref(false);
const selectedResult = ref<RetrievalResult | null>(null);

function formatScore(value: unknown) {
  const score = Number(value);
  return Number.isFinite(score) ? score.toFixed(2) : "—";
}

function mapResult(item: KnowledgeSearchItem, index: number): RetrievalResult {
  const score =
    item.rerankScore ??
    item.fusionScore ??
    item.vectorScore ??
    item.keywordScore;
  return {
    rank: index + 1,
    source: `${item.assetName}${item.pageNumber ? ` · p.${item.pageNumber}` : ""}`,
    title: item.sectionTitle || item.assetName,
    score: formatScore(score),
    vector: formatScore(item.vectorScore),
    keyword: formatScore(item.keywordScore),
    fusion: formatScore(item.fusionScore),
    reranked: item.rerankScore != null,
    text: item.content,
  };
}

async function runSearch() {
  if (!playgroundQuery.value.trim() || isSearching.value) return;
  if (projectId.value <= 0) {
    notify("请先选择一个项目");
    return;
  }
  isSearching.value = true;
  selectedRank.value = null;
  try {
    const response = await retrievalApi.search(
      workspaceId.value,
      projectId.value,
      {
        query: playgroundQuery.value.trim(),
        topK: topK.value,
        retrievalMode: retrievalMode.value,
        useReranker: rerank.value,
      },
    );
    retrievalResults.value = response.items.map(mapResult);
    notify(
      retrievalResults.value.length
        ? `检索完成，返回 ${retrievalResults.value.length} 条结果`
        : "检索完成，但没有召回结果",
    );
  } catch (error) {
    retrievalResults.value = [];
    notify(error instanceof Error ? error.message : "检索失败，请稍后重试");
  } finally {
    isSearching.value = false;
  }
}

function openParameters() {
  parameterMode.value = retrievalMode.value;
  parameterTopK.value = topK.value;
  parameterRerank.value = rerank.value;
  parameterOpen.value = true;
}

function applyParameters() {
  retrievalMode.value = parameterMode.value;
  topK.value = Math.min(20, Math.max(1, Number(parameterTopK.value) || 1));
  rerank.value = parameterRerank.value;
  parameterOpen.value = false;
  notify(`检索参数已更新：${retrievalMode.value} · Top K ${topK.value}`);
}

function openEvidence(result: RetrievalResult) {
  selectedRank.value = result.rank;
  selectedResult.value = result;
  evidenceOpen.value = true;
}
</script>

<template>
  <PageHeader
    eyebrow="PROJECT / RETRIEVAL"
    title="检索 Playground"
    subtitle="快速验证知识库召回质量与证据覆盖"
    ><template #action
      ><button
        class="button button-secondary"
        type="button"
        @click="openParameters"
      >
        <SlidersHorizontal :size="16" />参数设置
      </button></template
    ></PageHeader
  >
  <div class="playground-layout">
    <section class="panel playground-query">
      <div class="panel-heading">
        <div>
          <h2>输入问题</h2>
          <p>使用真实业务问题检查检索结果。</p>
        </div>
      </div>
      <textarea v-model="playgroundQuery" rows="5" />
      <div class="playground-config-summary">
        <div>
          <span>当前检索参数</span>
          <strong
            >{{ retrievalMode }} · Top K {{ topK }} · Rerank
            {{ rerank ? "已启用" : "未启用" }}</strong
          >
        </div>
        <button class="text-button" type="button" @click="openParameters">
          调整参数 <SlidersHorizontal :size="14" />
        </button>
      </div>
      <button class="button button-primary" type="button" @click="runSearch">
        <Search :size="16" />{{ isSearching ? "检索中..." : "运行检索" }}
      </button>
    </section>
    <section class="panel retrieval-results">
      <div class="panel-heading">
        <div>
          <h2>召回结果</h2>
          <p>{{ retrievalResults.length }} 条结果 · {{ retrievalMode }}</p>
        </div>
      </div>
      <article
        v-for="result in retrievalResults"
        :key="result.rank"
        class="retrieval-card"
        :class="{ selected: selectedRank === result.rank }"
        @click="selectedRank = result.rank"
      >
        <div class="retrieval-card-top">
          <span class="rank-number">0{{ result.rank }}</span
          ><span class="status-badge status-indexed"
            ><i />{{ result.score }}</span
          >
        </div>
        <h3>{{ result.title }}</h3>
        <small class="retrieval-source"
          ><FileText :size="13" />{{ result.source }}</small
        >
        <p>{{ result.text }}</p>
        <button
          class="text-button"
          type="button"
          :aria-label="`查看${result.title}的证据`"
          @click.stop="openEvidence(result)"
        >
          查看证据 <ArrowRight :size="14" />
        </button>
      </article>
      <div
        v-if="!retrievalResults.length"
        class="empty-state panel-empty-state retrieval-empty"
      >
        <Search :size="20" />
        <strong>{{ isSearching ? "正在检索知识库" : "暂无召回结果" }}</strong>
        <span>{{
          isSearching
            ? "检索完成后会在这里显示后端返回的证据片段。"
            : "输入问题并运行检索；没有命中时保持真实空状态。"
        }}</span>
      </div>
    </section>
  </div>
  <Dialog v-model:open="evidenceOpen">
    <DialogContent class="playground-evidence-dialog">
      <DialogHeader>
        <div class="evidence-dialog-heading">
          <span class="evidence-rank">0{{ selectedResult?.rank }}</span>
          <div>
            <DialogTitle>{{ selectedResult?.title }}</DialogTitle>
            <DialogDescription>{{ selectedResult?.source }}</DialogDescription>
          </div>
        </div>
      </DialogHeader>
      <div v-if="selectedResult" class="evidence-dialog-body">
        <div class="evidence-score-grid">
          <div>
            <span>相关性</span><strong>{{ selectedResult.score }}</strong>
          </div>
          <div>
            <span>Vector</span><strong>{{ selectedResult.vector }}</strong>
          </div>
          <div>
            <span>Keyword</span><strong>{{ selectedResult.keyword }}</strong>
          </div>
          <div>
            <span>Fusion</span><strong>{{ selectedResult.fusion }}</strong>
          </div>
        </div>
        <div class="evidence-quote">
          <p class="eyebrow">引用片段</p>
          <blockquote>{{ selectedResult.text }}</blockquote>
        </div>
        <div class="evidence-note">
          <CheckCircle2 :size="16" />
          <span>该片段已纳入当前检索结果，可作为报告引用依据。</span>
        </div>
      </div>
      <DialogFooter>
        <button
          class="button button-secondary button-sm"
          type="button"
          @click="evidenceOpen = false"
        >
          关闭
        </button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
  <Dialog v-model:open="parameterOpen">
    <DialogContent class="playground-parameter-dialog">
      <form @submit.prevent="applyParameters">
        <DialogHeader>
          <DialogTitle>检索参数设置</DialogTitle>
          <DialogDescription
            >调整本次 Playground
            的召回策略，保存后再运行检索。</DialogDescription
          >
        </DialogHeader>
        <div class="playground-parameter-form">
          <div class="parameter-field">
            <label for="playground-mode">检索模式</label>
            <Select v-model="parameterMode">
              <SelectTrigger id="playground-mode" aria-label="选择检索模式">
                <SelectValue placeholder="选择模式" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem
                  v-for="mode in retrievalModes"
                  :key="mode.value"
                  :value="mode.value"
                >
                  {{ mode.label }}
                </SelectItem>
              </SelectContent>
            </Select>
            <small
              >Hybrid 综合语义与关键词召回，Vector 更偏向语义相似度。</small
            >
          </div>
          <div class="parameter-field">
            <label for="playground-top-k">Top K</label>
            <input
              id="playground-top-k"
              v-model.number="parameterTopK"
              type="number"
              min="1"
              max="20"
            />
            <small>控制返回的候选证据数量，范围为 1–20。</small>
          </div>
          <label class="parameter-switch" for="playground-rerank">
            <span>
              <strong>启用 Rerank</strong>
              <small>对初步召回结果进行二次排序。</small>
            </span>
            <input
              id="playground-rerank"
              v-model="parameterRerank"
              type="checkbox"
            />
          </label>
        </div>
        <DialogFooter>
          <button
            class="button button-secondary button-sm"
            type="button"
            @click="parameterOpen = false"
          >
            取消
          </button>
          <button class="button button-primary button-sm" type="submit">
            保存参数
          </button>
        </DialogFooter>
      </form>
    </DialogContent>
  </Dialog>
</template>

<style scoped>
.playground-layout {
  display: grid;
  grid-template-columns: 17.8125rem minmax(0, 1fr);
  gap: 1.25rem;
  align-items: start;
}
.playground-controls {
  padding-bottom: 1.25rem;
}
.playground-controls .panel-heading {
  padding-bottom: 1.375rem;
}
.playground-controls .field-label {
  margin: 0 1.25rem 1.3125rem;
}
.mode-switch {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.1875rem;
  background: #f1f5f5;
  padding: 0.1875rem;
  border-radius: 0.4375rem;
}
.mode-switch button {
  border: 0;
  background: transparent;
  color: #89979b;
  height: 1.8125rem;
  border-radius: 0.3125rem;
  font: inherit;
  font-size: 0.75rem;
  cursor: pointer;
}
.mode-switch button.active {
  background: white;
  color: var(--teal-dark);
  box-shadow: 0 0.0625rem 0.1875rem rgba(39, 72, 70, 0.08);
  font-weight: 650;
}
.range-line {
  display: flex;
  align-items: center;
  gap: 0.5625rem;
}
.range-line input {
  accent-color: var(--teal);
  flex: 1;
}
.range-line strong {
  color: #3a5357;
  font-size: 0.8125rem;
}
.toggle-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  margin: 0 1.25rem 1.3125rem;
}
.toggle-row > span:first-child {
  min-width: 0;
}
.toggle-row strong,
.toggle-row small {
  display: block;
}
.toggle-row strong {
  color: #4b5d62;
  font-size: 0.75rem;
}
.toggle-row small {
  color: #9aa7aa;
  font-size: 0.75rem;
  line-height: 1.45;
  margin-top: 0.25rem;
}
.toggle {
  width: 2.125rem;
  height: 1.25rem;
  padding: 0.125rem;
  background: #dbe3e3;
  border: 0;
  border-radius: 6.1875rem;
  cursor: pointer;
  transition: background 0.2s;
  flex: 0 0 auto;
}
.toggle i {
  display: block;
  width: 1rem;
  height: 1rem;
  border-radius: 50%;
  background: #fff;
  box-shadow: 0 0.0625rem 0.1875rem rgba(0, 0, 0, 0.12);
  transition: transform 0.2s;
}
.toggle.on {
  background: var(--teal);
}
.toggle.on i {
  transform: translateX(0.875rem);
}
.filter-box {
  display: flex;
  align-items: center;
  margin: 0 1.25rem;
  padding: 0.6875rem 0.75rem;
  border: 0.0625rem solid #e7eeee;
  border-radius: 0.5rem;
}
.filter-box div {
  flex: 1;
}
.filter-box strong,
.filter-box span {
  display: block;
}
.filter-box strong {
  color: #516369;
  font-size: 0.75rem;
}
.filter-box span {
  color: #a1adb0;
  font-size: 0.75rem;
  margin-top: 0.25rem;
}
.playground-controls .full-button {
  margin: 0.1875rem 1.25rem 0;
  width: calc(100% - 2.5rem);
}
.playground-config-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  margin: 0.875rem 0;
  padding: 0.75rem 0.8125rem;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.5rem;
  background: var(--surface-soft);
}
.playground-config-summary div {
  display: grid;
  min-width: 0;
  gap: 0.25rem;
}
.playground-config-summary span {
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.playground-config-summary strong {
  overflow: hidden;
  color: var(--workspace-text);
  font-size: 0.75rem;
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.playground-parameter-dialog {
  width: min(30rem, calc(100vw - 2rem));
}
.playground-parameter-dialog form {
  display: grid;
  gap: 1.25rem;
}
.playground-parameter-form {
  display: grid;
  gap: 1rem;
}
.parameter-field {
  display: grid;
  gap: 0.4375rem;
}
.parameter-field > label,
.parameter-switch strong {
  color: var(--workspace-text);
  font-size: 0.8125rem;
  font-weight: 650;
}
.parameter-field > small,
.parameter-switch small {
  color: var(--workspace-muted);
  font-size: 0.75rem;
  line-height: 1.5;
}
.parameter-field > input {
  width: 100%;
  min-height: 2rem;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.4375rem;
  background: var(--surface-raised);
  color: var(--workspace-text);
  padding: 0.4375rem 0.5625rem;
  font: inherit;
  font-size: 0.8125rem;
  outline: 0;
}
.parameter-field > input:focus {
  border-color: var(--teal);
  box-shadow: 0 0 0 0.1875rem color-mix(in oklab, var(--teal) 14%, transparent);
}
.parameter-switch {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.8125rem;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.5rem;
  background: var(--surface-soft);
  cursor: pointer;
}
.parameter-switch span {
  display: grid;
  gap: 0.25rem;
}
.parameter-switch input {
  width: 1rem;
  height: 1rem;
  accent-color: var(--teal);
}
.playground-results {
  min-width: 0;
}
.playground-query {
  padding: 1.25rem;
}
.playground-query textarea {
  width: 100%;
  min-height: 8.25rem;
  resize: vertical;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.5rem;
  background: var(--surface-raised);
  color: var(--workspace-text);
  padding: 0.6875rem 0.75rem;
  font: inherit;
  font-size: 0.8125rem;
  line-height: 1.65;
  outline: 0;
}
.playground-query textarea:focus {
  border-color: var(--teal);
  box-shadow: 0 0 0 0.1875rem color-mix(in oklab, var(--teal) 12%, transparent);
}
.playground-query > .panel-heading {
  padding: 0 0 1rem;
}
.playground-controls {
  display: grid;
  grid-template-columns: 1.2fr 0.8fr;
  gap: 0.625rem;
  margin: 0.875rem 0;
  padding: 0;
}
.playground-controls label {
  display: grid;
  gap: 0.375rem;
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.playground-controls input[type="number"] {
  width: 100%;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.4375rem;
  background: var(--surface-raised);
  color: var(--workspace-text);
  padding: 0.5rem 0.5625rem;
  font: inherit;
  font-size: 0.75rem;
}
.playground-mode-select {
  width: 100%;
  min-height: 2rem;
}
.playground-controls .toggle-label {
  display: flex;
  grid-column: 1 / -1;
  align-items: center;
  gap: 0.4375rem;
  cursor: pointer;
}
.playground-controls .toggle-label input {
  accent-color: var(--teal);
}
.playground-query > .button {
  width: 100%;
}
.retrieval-results {
  min-width: 0;
  overflow: hidden;
}
.retrieval-results > .panel-heading {
  padding-bottom: 0.875rem;
  border-bottom: 0.0625rem solid var(--workspace-divider);
}
.retrieval-card {
  margin: 0 0.875rem 0.75rem;
  padding: 1rem 1.125rem;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.6875rem;
  background: var(--surface-raised);
  cursor: pointer;
  transition:
    border-color 0.2s ease,
    box-shadow 0.2s ease,
    transform 0.2s ease;
}
.retrieval-card:hover,
.retrieval-card.selected {
  border-color: color-mix(in oklab, var(--teal) 48%, var(--workspace-border));
  box-shadow: 0 0.5rem 1.375rem rgba(25, 89, 83, 0.08);
  transform: translateY(-0.0625rem);
}
.retrieval-card:last-child {
  margin-bottom: 1rem;
}
.retrieval-card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.retrieval-card h3 {
  color: var(--workspace-text);
  font-size: 0.75rem;
  margin: 0.75rem 0 0.3125rem;
}
.retrieval-card small,
.retrieval-card p {
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.retrieval-source {
  display: inline-flex;
  align-items: center;
  gap: 0.3125rem;
}
.retrieval-card p {
  line-height: 1.7;
  margin: 0.6875rem 0;
}
.retrieval-card .text-button {
  font-size: 0.75rem;
}
.retrieval-card .text-button:hover {
  padding-inline: 0.4375rem;
  border-radius: 0.3125rem;
  background: color-mix(in oklab, var(--teal) 10%, var(--surface));
}
.playground-evidence-dialog {
  width: min(36rem, calc(100vw - 2rem));
}
.playground-parameter-dialog .button-secondary,
.playground-evidence-dialog .button-secondary {
  border-color: var(--workspace-border, #2c4147);
  background: var(--surface, #142329);
  color: var(--workspace-text, #e7f1f0);
}
.playground-parameter-dialog .button-secondary:hover,
.playground-evidence-dialog .button-secondary:hover {
  border-color: var(--workspace-muted, #9cafb2);
  background: var(--surface-soft, #1c3036);
  color: var(--workspace-text, #e7f1f0);
}
.playground-parameter-dialog .button-primary,
.playground-evidence-dialog .button-primary {
  border-color: transparent;
  background: var(--teal, #1a6861);
  color: #eafffb;
}
.playground-parameter-dialog .button-primary:hover,
.playground-evidence-dialog .button-primary:hover {
  background: var(--teal-dark, #0d625a);
}
.evidence-dialog-heading {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}
.evidence-rank {
  display: grid;
  width: 2.25rem;
  height: 2.25rem;
  place-items: center;
  flex: 0 0 auto;
  border-radius: 0.625rem;
  background: color-mix(in oklab, var(--teal) 14%, var(--surface));
  color: var(--teal-dark);
  font-size: 0.75rem;
  font-weight: 750;
}
.evidence-dialog-heading > div {
  min-width: 0;
}
.evidence-dialog-heading [data-slot="dialog-title"] {
  color: var(--workspace-text);
  font-size: 0.9375rem;
}
.evidence-dialog-heading [data-slot="dialog-description"] {
  overflow: hidden;
  margin-top: 0.3125rem;
  color: var(--workspace-muted);
  font-size: 0.75rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.evidence-dialog-body {
  display: grid;
  gap: 1rem;
}
.evidence-score-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.5rem;
}
.evidence-score-grid div {
  display: grid;
  gap: 0.3125rem;
  padding: 0.625rem 0.6875rem;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.5rem;
  background: var(--surface-soft);
}
.evidence-score-grid span {
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.evidence-score-grid strong {
  color: var(--workspace-text);
  font-size: 0.8125rem;
}
.evidence-quote {
  padding: 0.875rem 1rem;
  border-left: 0.1875rem solid var(--teal);
  border-radius: 0 0.5rem 0.5rem 0;
  background: color-mix(in oklab, var(--teal) 7%, var(--surface));
}
.evidence-quote .eyebrow {
  margin: 0 0 0.5rem;
}
.evidence-quote blockquote {
  margin: 0;
  color: var(--workspace-text);
  font-size: 0.8125rem;
  line-height: 1.75;
}
.evidence-note {
  display: flex;
  align-items: center;
  gap: 0.4375rem;
  color: var(--teal-dark);
  font-size: 0.75rem;
}
.results-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 0.8125rem;
}
.result-count {
  color: #3a4e54;
  font-size: 0.75rem;
  font-weight: 650;
}
.results-header p {
  color: #9ba8ab;
  font-size: 0.75rem;
  margin: 0.3125rem 0 0;
}
.result-card {
  background: #fff;
  border: 0.0625rem solid #e3ebeb;
  border-radius: 0.625rem;
  padding: 1.3125rem 1.375rem 1.125rem;
  margin-bottom: 0.75rem;
}
.result-card-head {
  gap: 0.75rem;
}
.rank-number {
  color: #aab5b8;
  font-size: 0.875rem;
  font-weight: 700;
  align-self: flex-start;
}
.result-card-head > div {
  flex: 1;
  min-width: 0;
}
.result-card-head strong {
  display: block;
  color: #31444a;
  font-size: 0.75rem;
}
.source-link {
  display: inline-flex;
  align-items: center;
  gap: 0.3125rem;
  border: 0;
  background: none;
  color: var(--teal-dark);
  padding: 0;
  margin-top: 0.4375rem;
  font: inherit;
  font-size: 0.75rem;
  cursor: pointer;
}
.source-link:hover {
  text-decoration: underline;
}
.score-total {
  color: var(--teal-dark);
  font-size: 1.25rem;
  font-weight: 680;
  letter-spacing: -0.04em;
  text-align: right;
}
.score-total small {
  color: #a1adaf;
  display: block;
  font-size: 0.75rem;
  font-weight: 500;
  margin-top: 0.0625rem;
}
.result-text {
  color: #68787d;
  font-size: 0.8125rem;
  line-height: 1.7;
  margin: 0.9375rem 0 0.8125rem;
}
.score-row {
  display: flex;
  gap: 1.125rem;
  border-top: 0.0625rem solid #edf1f1;
  padding-top: 0.6875rem;
  color: #a0acae;
  font-size: 0.75rem;
}
.score-row strong {
  color: #60767a;
  margin-left: 0.1875rem;
}
.score-row span:last-child {
  color: #a6b1b2;
  margin-left: auto;
}
.score-row .rerank-on {
  color: var(--teal-dark);
}

@media (max-width: 47.5rem) {
  .playground-layout {
    grid-template-columns: 1fr;
  }

  .playground-config-summary {
    align-items: flex-start;
    flex-direction: column;
  }

  .evidence-score-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
.result-card,
.playground-result-card {
  background: var(--surface);
  border-color: var(--workspace-border);
  color: var(--workspace-text);
}
.result-text,
.score-row {
  color: var(--workspace-muted);
}
.score-row span:last-child {
  color: var(--workspace-subtle);
}
.result-card input,
.result-card textarea {
  background: var(--surface-soft);
  border-color: var(--workspace-border);
  color: var(--workspace-text);
}
</style>
