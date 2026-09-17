<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { CheckCircle2, Globe2, Link2, RefreshCw, Save, ShieldCheck, Wifi } from "@lucide/vue";
import Layout from "@/components/settings/Layout.vue";
import { getApiErrorMessage } from "@/api/core";
import { projectApi } from "@/api/projects";
import { settingsApi, type WebSearchConfig } from "@/api/settings";
import { useWorkspace } from "@/composables/useWorkspace";

const { notify, workspaceId, projectId } = useWorkspace();
const settingsProjectId = ref(-1);
const hasProject = computed(() => settingsProjectId.value > 0);
const config = ref<WebSearchConfig | null>(null);
const loading = ref(true);
const saving = ref(false);
const testing = ref(false);
const error = ref("");
const testMessage = ref("");
const form = reactive({
  provider: "duckduckgo",
  baseUrl: "https://html.duckduckgo.com/html/",
  apiKey: "",
  language: "zh-hans",
  enabled: true,
});

const configured = computed(() => Boolean(
  config.value?.provider === form.provider && (config.value.hasCredential || !requiresApiKey.value),
));
const requiresApiKey = computed(() => form.provider === "brave");
const statusLabel = computed(() => {
  if (!config.value) return "尚未设置";
  if (!config.value.enabled) return "已停用";
  return configured.value ? "已配置" : requiresApiKey.value ? "缺少 API Key" : "待保存";
});

function loadForm(value: WebSearchConfig | null) {
  config.value = value;
  if (!value) return;
  Object.assign(form, {
    provider: value.provider || "duckduckgo",
    baseUrl: value.baseUrl || (value.provider === "brave" ? "https://api.search.brave.com/res/v1/web/search" : "https://html.duckduckgo.com/html/"),
    language: value.language || "zh-hans",
    enabled: value.enabled,
    apiKey: "",
  });
}

function changeProvider() {
  form.baseUrl = form.provider === "brave"
    ? "https://api.search.brave.com/res/v1/web/search"
    : "https://html.duckduckgo.com/html/";
  form.apiKey = "";
}

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const resolvedProjectId = projectId.value > 0
      ? projectId.value
      : (await projectApi.list(workspaceId.value))[0]?.id || -1;
    settingsProjectId.value = resolvedProjectId;
    if (resolvedProjectId > 0) loadForm(await settingsApi.webSearch.get(workspaceId.value, resolvedProjectId));
  } catch (cause) {
    error.value = getApiErrorMessage(cause, "联网搜索配置加载失败");
  } finally {
    loading.value = false;
  }
}

async function save() {
  if (!hasProject.value) {
    error.value = "请先创建项目后配置联网搜索";
    return;
  }
  if (!form.baseUrl.trim() || !/^https?:\/\//.test(form.baseUrl.trim())) {
    error.value = "请输入以 http:// 或 https:// 开头的搜索地址";
    return;
  }
  if (requiresApiKey.value && !configured.value && !form.apiKey.trim()) {
    error.value = "Brave Search 必须填写 API Key";
    return;
  }
  saving.value = true;
  error.value = "";
  try {
    loadForm(await settingsApi.webSearch.save(workspaceId.value, settingsProjectId.value, {
      provider: form.provider,
      baseUrl: form.baseUrl.trim(),
      ...(form.apiKey.trim() ? { apiKey: form.apiKey.trim() } : {}),
      language: form.language.trim() || "zh-hans",
      enabled: form.enabled,
    }));
    notify("联网搜索配置已保存");
  } catch (cause) {
    error.value = getApiErrorMessage(cause, "联网搜索配置保存失败");
  } finally {
    saving.value = false;
  }
}

async function testConnection() {
  if (!hasProject.value) {
    error.value = "请先创建项目后测试联网搜索";
    return;
  }
  testing.value = true;
  testMessage.value = "";
  error.value = "";
  try {
    const result = await settingsApi.webSearch.test(workspaceId.value, settingsProjectId.value);
    testMessage.value = `连接正常 · 返回 ${result.resultCount ?? 0} 条结果 · ${result.latencyMs ?? 0} ms`;
  } catch (cause) {
    error.value = getApiErrorMessage(cause, "联网搜索连接测试失败");
  } finally {
    testing.value = false;
  }
}

onMounted(load);
</script>

<template>
  <Layout
    eyebrow="SETTINGS / WEB SEARCH"
    title="联网搜索"
    subtitle="联网搜索是独立能力，只负责获取外部资料并留下来源记录，不会读取或调用其他连接器。"
  >
    <section class="settings-section web-search-section">
      <div class="web-search-heading">
        <div>
          <h2>搜索提供商</h2>
          <p>聊天中的“允许本次联网搜索”只会使用这里的配置。搜索结果进入运行记录，由你决定是否保存到知识库。</p>
        </div>
        <span class="status-badge" :class="configured && form.enabled ? 'status-indexed' : 'status-muted'"><i />{{ statusLabel }}</span>
      </div>

      <div v-if="loading" class="web-search-loading"><RefreshCw :size="16" class="spin" />正在读取联网搜索配置…</div>
      <template v-else>
        <p v-if="!hasProject" class="web-search-info">当前工作区还没有项目；联网搜索配置按项目保存，请先创建项目。</p>
        <fieldset class="web-search-form-fields" :disabled="!hasProject">
        <div class="web-search-card">
          <div class="web-search-card-title"><span class="web-search-icon"><Globe2 :size="18" /></span><div><strong>联网搜索适配器</strong><small>{{ form.provider === "brave" ? "Brave Search API" : form.provider === "multi" ? "通用网页 + 论文 + 技术站点" : "DuckDuckGo 公共搜索" }}</small></div></div>
          <div class="web-search-fields">
            <label class="field-label"><span>搜索提供商</span><select v-model="form.provider" @change="changeProvider"><option value="multi">多源混合搜索（推荐）</option><option value="duckduckgo">DuckDuckGo（无需 API Key）</option><option value="brave">Brave Search（需要 API Key）</option></select></label>
            <label class="field-label"><span>搜索地址</span><input v-model="form.baseUrl" type="url" placeholder="https://api.search.brave.com/res/v1/web/search" /></label>
            <label class="field-label"><span>搜索语言</span><input v-model="form.language" type="text" placeholder="zh-hans" /></label>
            <label v-if="requiresApiKey" class="field-label field-wide"><span>API Key <small>{{ configured ? "已保存；留空表示保持不变" : "必填" }}</small></span><input v-model="form.apiKey" type="password" autocomplete="off" placeholder="输入 Brave Search API Key" /></label>
          </div>
          <label class="web-search-toggle"><input v-model="form.enabled" type="checkbox" /><span class="fake-checkbox"><CheckCircle2 :size="14" /></span><span><strong>允许聊天使用联网搜索</strong><small>关闭后，聊天仍可使用知识库和历史记录，但不会发起外部搜索。</small></span></label>
        </div>
        </fieldset>

        <div class="web-search-actions">
          <button class="button button-primary" type="button" :disabled="saving || !hasProject" @click="save"><Save :size="15" />{{ saving ? "保存中…" : "保存配置" }}</button>
          <button class="button button-secondary" type="button" :disabled="testing || !configured || !form.enabled || !hasProject" @click="testConnection"><Wifi :size="15" />{{ testing ? "测试中…" : "测试联网搜索" }}</button>
          <span v-if="testMessage" class="web-search-success">{{ testMessage }}</span>
        </div>
        <p v-if="error" class="web-search-error">{{ error }}</p>
      </template>
    </section>

    <section class="settings-section web-search-boundary">
      <div class="web-search-boundary-icon"><ShieldCheck :size="17" /></div>
      <div><h2>边界说明</h2><p>通用工具与连接器仍在“工具与连接器”中独立管理；它们不会被当作联网搜索提供商，也不会因为开启本开关而自动执行。</p></div>
      <Link2 :size="17" />
    </section>
  </Layout>
</template>

<style scoped>
.web-search-section { padding-top: 1.35rem; }
.web-search-heading, .web-search-boundary, .web-search-card-title, .web-search-actions, .web-search-toggle { display: flex; align-items: center; }
.web-search-heading { justify-content: space-between; gap: 1rem; }
.web-search-heading p { margin-bottom: 1.1rem !important; }
.web-search-info { max-width: 52rem; margin: 0 0 .75rem; padding: .65rem .8rem; border: 1px solid color-mix(in oklab, var(--teal) 24%, var(--workspace-border)); border-radius: .5rem; color: var(--workspace-muted); background: color-mix(in oklab, var(--teal) 6%, var(--surface)); font-size: .78rem; }
.web-search-form-fields { min-width: 0; margin: 0; padding: 0; border: 0; }
.web-search-card { max-width: 52rem; padding: 1rem; border: 1px solid var(--workspace-border); border-radius: .75rem; background: var(--surface-raised); color: var(--workspace-text); }
.web-search-card-title { gap: .65rem; margin-bottom: 1rem; }
.web-search-card-title strong, .web-search-card-title small { display: block; }
.web-search-card-title strong { color: var(--workspace-text); font-size: .85rem; }
.web-search-card-title small { margin-top: .22rem; color: var(--workspace-muted); font-size: 0.8125rem; }
.web-search-icon, .web-search-boundary-icon { display: grid; place-items: center; color: var(--teal-dark); background: color-mix(in oklab, var(--teal) 12%, var(--surface)); border-radius: .55rem; }
.web-search-icon { width: 2.25rem; height: 2.25rem; }
.web-search-fields { display: grid; grid-template-columns: minmax(0, 1fr) 12rem; gap: .75rem; }
.web-search-fields .field-wide { grid-column: 1 / -1; }
.field-label { color: var(--workspace-muted); }
.field-label small { color: var(--workspace-subtle); font-weight: 400; }
.field-label input, .field-label select { border-color: var(--workspace-border); background: var(--surface); color: var(--workspace-text); }
.field-label input::placeholder { color: var(--workspace-subtle); }
.web-search-toggle { gap: .55rem; margin-top: 1rem; padding-top: 1rem; border-top: 1px solid var(--workspace-divider); color: var(--workspace-text); cursor: pointer; }
.web-search-toggle input { position: absolute; opacity: 0; pointer-events: none; }
.fake-checkbox { display: grid; place-items: center; width: 1.2rem; height: 1.2rem; color: transparent; border: 1px solid var(--workspace-border); border-radius: .32rem; }
.web-search-toggle input:checked + .fake-checkbox { color: white; background: var(--teal-dark); border-color: var(--teal-dark); }
.web-search-toggle strong, .web-search-toggle small { display: block; }
.web-search-toggle strong { color: var(--workspace-text); font-size: 0.75rem; }
.web-search-toggle small { margin-top: .22rem; color: var(--workspace-muted); font-size: 0.8125rem; }
.web-search-actions { gap: .65rem; max-width: 52rem; margin-top: 1rem; }
.web-search-success { color: var(--teal-dark); font-size: 0.8125rem; }
.web-search-error { color: var(--red) !important; margin-top: .75rem !important; }
.web-search-loading { display: flex; align-items: center; gap: .5rem; min-height: 9rem; color: var(--workspace-muted); font-size: .78rem; }
.spin { animation: spin 1s linear infinite; }
.web-search-boundary { display: flex; align-items: flex-start; gap: .7rem; color: var(--workspace-muted); }
.web-search-boundary-icon { width: 2rem; height: 2rem; flex: 0 0 auto; }
.web-search-boundary h2 { color: var(--workspace-text) !important; font-size: .82rem !important; }
.web-search-boundary p { margin-bottom: 0 !important; }
.web-search-boundary > svg { margin-left: auto; margin-top: .45rem; color: var(--workspace-muted); }
@keyframes spin { to { transform: rotate(360deg); } }
@media (max-width: 700px) { .web-search-fields { grid-template-columns: 1fr; } .web-search-fields .field-wide { grid-column: auto; } .web-search-actions { flex-wrap: wrap; } }
</style>
