<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import {
  CheckCircle2,
  Cpu,
  Database,
  Gauge,
  KeyRound,
  Plus,
  RefreshCw,
  Settings2,
  ShieldCheck,
  Star,
  Timer,
  Zap,
} from "@lucide/vue";
import Layout from "@/components/settings/Layout.vue";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useWorkspace } from "@/composables/useWorkspace";
import { settingsApi, type ProjectModelConfig } from "@/api/settings";
import { projectApi } from "@/api/projects";

type ModelRecord = {
  id?: number | string;
  name: string;
  provider: string;
  use: string;
  enabled: boolean;
  latency: string;
  modelId: string;
  endpoint: string;
  authType: string;
  credential: string;
  temperature: number;
  topP: number;
  topK: number | null;
  maxTokens: number;
  contextWindow: number;
  frequencyPenalty: number;
  presencePenalty: number;
  seed: number | null;
  stop: string[];
  reasoningEffort: "none" | "low" | "medium" | "high";
  structuredOutputMethod: "json_schema" | "function_calling" | "json_mode";
  extraBody: string;
  timeout: number;
  retries: number;
  description: string;
  note: string;
  scope: "PERSONAL" | "TEAM";
};

type EmbeddingMode = "local" | "api";

type EmbeddingForm = {
  name: string;
  provider: string;
  modelId: string;
  endpoint: string;
  authType: string;
  credential: string;
  dimension: number;
  mode: EmbeddingMode;
  scope: "PERSONAL" | "TEAM";
};

type NewModelForm = {
  name: string;
  provider: string;
  modelId: string;
  use: string;
  description: string;
  endpoint: string;
  authType: string;
  credential: string;
  temperature: number;
  topP: number;
  topK: number | null;
  maxTokens: number;
  contextWindow: number;
  frequencyPenalty: number;
  presencePenalty: number;
  seed: number | null;
  stop: string;
  reasoningEffort: ModelRecord["reasoningEffort"];
  structuredOutputMethod: ModelRecord["structuredOutputMethod"];
  extraBody: string;
  timeout: number;
  retries: number;
  enabled: boolean;
  note: string;
  scope: "PERSONAL" | "TEAM";
};

const { notify, workspaceId, projectId } = useWorkspace();
const settingsProjectId = ref(-1);
const providerEndpoints: Record<string, string> = {
  OpenAI: "https://api.openai.com/v1",
  Anthropic: "https://api.anthropic.com/v1",
  DashScope: "https://dashscope.aliyuncs.com/compatible-mode/v1",
  "Azure OpenAI":
    "https://{resource}.openai.azure.com/openai/deployments/{deployment}",
};

const models = ref<ModelRecord[]>([]);
const embeddingModel = ref<ProjectModelConfig | null>(null);
const defaultModel = ref("");
const addOpen = ref(false);
const advancedOpen = ref(false);
const testingModel = ref("");
const testingEmbedding = ref(false);
const formError = ref("");
const embeddingError = ref("");
const embeddingForm = reactive<EmbeddingForm>({
  name: "项目 Embedding",
  provider: "OpenAI",
  modelId: "text-embedding-3-small",
  endpoint: "https://api.openai.com/v1",
  authType: "API Key",
  credential: "",
  dimension: 1536,
  mode: "local",
  scope: "TEAM",
});
const externalEmbeddingActive = computed(
  () => embeddingForm.mode === "api" && Boolean(embeddingModel.value?.enabled),
);
const newModel = reactive<NewModelForm>({
  name: "",
  provider: "OpenAI",
  modelId: "",
  use: "",
  description: "",
  endpoint: providerEndpoints.OpenAI ?? "",
  authType: "API Key",
  credential: "",
  temperature: 0.3,
  topP: 0.9,
  topK: null as number | null,
  maxTokens: 4096,
  contextWindow: 128000,
  frequencyPenalty: 0,
  presencePenalty: 0,
  seed: null as number | null,
  stop: "",
  reasoningEffort: "none",
  structuredOutputMethod: "json_schema",
  extraBody: "",
  timeout: 60,
  retries: 2,
  enabled: true,
  note: "",
  scope: "TEAM" as "PERSONAL" | "TEAM",
});
const enabledCount = computed(
  () => models.value.filter((model) => model.enabled).length,
);

function parseConfig(value?: string) {
  try {
    return value ? (JSON.parse(value) as Record<string, unknown>) : {};
  } catch {
    return {};
  }
}

function isEmbeddingConfig(model: ProjectModelConfig) {
  return String(parseConfig(model.config).use || "").toUpperCase() === "EMBEDDING";
}

function loadEmbeddingForm(model: ProjectModelConfig | null) {
  if (!model) return;
  const config = parseConfig(model.config);
  Object.assign(embeddingForm, {
    name: model.name,
    provider: model.provider,
    modelId: model.modelId,
    endpoint: model.endpoint,
    authType: model.authType,
    credential: "",
    dimension: Number(config.dimension ?? 1536),
    mode:
      model.enabled && String(config.mode ?? "openai").toLowerCase() !== "hash"
        ? "api"
        : "local",
    scope: model.scope === "PERSONAL" ? "PERSONAL" : "TEAM",
  });
}

function fromApiModel(model: ProjectModelConfig): ModelRecord {
  let config: Partial<ModelRecord> = {};
  try {
    config = model.config ? JSON.parse(model.config) : {};
  } catch {
    config = {};
  }
  return {
    id: model.id,
    name: model.name,
    provider: model.provider,
    use: String(config.use || "—"),
    enabled: model.enabled,
    latency: "—",
    modelId: model.modelId,
    endpoint: model.endpoint,
    authType: model.authType,
    credential: "",
    temperature: Number(config.temperature ?? 0.3),
    topP: Number(config.topP ?? 0.9),
    topK: config.topK == null ? null : Number(config.topK),
    maxTokens: Number(config.maxTokens ?? 4096),
    contextWindow: Number(config.contextWindow ?? 128000),
    frequencyPenalty: Number(config.frequencyPenalty ?? 0),
    presencePenalty: Number(config.presencePenalty ?? 0),
    seed: config.seed == null ? null : Number(config.seed),
    stop: Array.isArray(config.stop) ? config.stop.map(String) : [],
    reasoningEffort: ["none", "low", "medium", "high"].includes(String(config.reasoningEffort)) ? String(config.reasoningEffort) as ModelRecord["reasoningEffort"] : "none",
    structuredOutputMethod: ["json_schema", "function_calling", "json_mode"].includes(String(config.structuredOutputMethod)) ? String(config.structuredOutputMethod) as ModelRecord["structuredOutputMethod"] : "json_schema",
    extraBody: config.extraBody ? JSON.stringify(config.extraBody, null, 2) : "",
    timeout: Number(config.timeout ?? 0),
    retries: Number(config.retries ?? 0),
    description: String(config.description || ""),
    note: String(config.note || ""),
    scope: model.scope === "PERSONAL" ? "PERSONAL" : config.scope === "PERSONAL" ? "PERSONAL" : "TEAM",
  };
}

onMounted(async () => {
  try {
    const resolvedProjectId =
      projectId.value > 0
        ? projectId.value
        : (await projectApi.list(workspaceId.value))[0]?.id || -1;
    settingsProjectId.value = resolvedProjectId;
    if (resolvedProjectId <= 0) return;
    const remoteModels = await settingsApi.models.list(
      workspaceId.value,
      resolvedProjectId,
    );
    embeddingModel.value = remoteModels.find(isEmbeddingConfig) || null;
    loadEmbeddingForm(embeddingModel.value);
    models.value = remoteModels.filter((model) => !isEmbeddingConfig(model)).map(fromApiModel);
    defaultModel.value = models.value.find((model) => model.enabled)?.name || "";
  } catch {
    notify("模型配置加载失败");
  }
});

function embeddingPayload(enabled: boolean) {
  return {
    name: embeddingForm.name.trim(),
    provider: embeddingForm.provider.trim(),
    modelId: embeddingForm.modelId.trim(),
    endpoint: embeddingForm.endpoint.trim(),
    authType: embeddingForm.authType,
    ...(embeddingForm.credential.trim()
      ? { credential: embeddingForm.credential.trim() }
      : {}),
    enabled,
    scope: embeddingForm.scope,
    config: JSON.stringify({
      use: "EMBEDDING",
      mode: "openai",
      dimension: embeddingForm.dimension,
    }),
  };
}

async function useLocalEmbedding() {
  if (!embeddingModel.value?.id) {
    embeddingForm.mode = "local";
    notify("已启用本地向量化，不会调用外部 API");
    return;
  }

  try {
    embeddingModel.value = await settingsApi.models.update(
      workspaceId.value,
      settingsProjectId.value,
      embeddingModel.value.id,
      embeddingPayload(false),
    );
    embeddingForm.mode = "local";
    embeddingForm.credential = "";
    notify("已切换到本地向量化，外部 API 已停用");
  } catch (error) {
    embeddingError.value =
      error instanceof Error ? error.message : "本地向量化设置保存失败";
  }
}

async function saveEmbedding() {
  embeddingError.value = "";
  if (embeddingForm.mode === "local") {
    await useLocalEmbedding();
    return;
  }
  if (!embeddingForm.name.trim() || !embeddingForm.modelId.trim()) {
    embeddingError.value = "请填写配置名称和模型 ID";
    return;
  }
  if (!/^https?:\/\//.test(embeddingForm.endpoint.trim())) {
    embeddingError.value = "服务地址必须以 http:// 或 https:// 开头";
    return;
  }
  if (!embeddingModel.value && !embeddingForm.credential.trim()) {
    embeddingError.value = "首次保存必须填写访问凭证";
    return;
  }
  if (!Number.isInteger(embeddingForm.dimension) || embeddingForm.dimension < 1) {
    embeddingError.value = "向量维度必须是正整数，并且要与当前 Milvus 集合一致";
    return;
  }
  try {
    const payload = embeddingPayload(true);
    embeddingModel.value = embeddingModel.value?.id
      ? await settingsApi.models.update(
          workspaceId.value,
          settingsProjectId.value,
          embeddingModel.value.id,
          payload,
        )
      : await settingsApi.models.create(
          workspaceId.value,
          settingsProjectId.value,
          payload,
        );
    embeddingForm.credential = "";
    notify("Embedding 配置已保存");
  } catch (error) {
    embeddingError.value = error instanceof Error ? error.message : "Embedding 配置保存失败";
  }
}

async function testEmbedding() {
  if (!embeddingModel.value?.id || !embeddingModel.value.enabled) {
    embeddingError.value = "请先保存并启用外部 Embedding API";
    return;
  }
  testingEmbedding.value = true;
  try {
    const result = await settingsApi.models.testEmbedding(
      workspaceId.value,
      settingsProjectId.value,
      embeddingModel.value.id,
    );
    notify(`Embedding 连接成功 · ${result.dimension || embeddingForm.dimension} 维`);
  } catch (error) {
    embeddingError.value = error instanceof Error ? error.message : "Embedding 连接测试失败";
  } finally {
    testingEmbedding.value = false;
  }
}

async function toggleModel(model: ModelRecord) {
  if (model.name === defaultModel.value && model.enabled) {
    notify("请先选择其他默认模型");
    return;
  }
  model.enabled = !model.enabled;
  if (model.id) {
    try {
      await settingsApi.models.update(
        workspaceId.value,
        settingsProjectId.value,
        model.id,
        {
          name: model.name,
          provider: model.provider,
          modelId: model.modelId,
          endpoint: model.endpoint,
          authType: model.authType,
          scope: model.scope,
          enabled: model.enabled,
        },
      );
    } catch {
      model.enabled = !model.enabled;
      notify("模型状态保存失败");
      return;
    }
  }
  if (!model.enabled && defaultModel.value === model.name)
    defaultModel.value =
      models.value.find((candidate) => candidate.enabled)?.name || "";
  notify(`${model.name} 已${model.enabled ? "启用" : "停用"}`);
}

async function testConnection(model: ModelRecord) {
  if (!model.id) return;
  testingModel.value = model.name;
  const started = performance.now();
  try {
    await settingsApi.models.test(workspaceId.value, settingsProjectId.value, model.id);
    model.latency = `${Math.round(performance.now() - started)} ms`;
    notify(`${model.name} 连接测试成功 · ${model.latency}`);
  } catch (error) {
    model.latency = "失败";
    notify(error instanceof Error ? error.message : `${model.name} 连接测试失败`);
  } finally {
    testingModel.value = "";
  }
}

async function removeModel(model: ModelRecord) {
  if (!model.id) {
    models.value = models.value.filter((item) => item !== model);
    return;
  }
  try {
    await settingsApi.models.remove(workspaceId.value, settingsProjectId.value, model.id);
  } catch {
    notify("模型配置删除失败");
    return;
  }
  models.value = models.value.filter((item) => item.id !== model.id);
  if (defaultModel.value === model.name)
    defaultModel.value =
      models.value.find((candidate) => candidate.enabled)?.name || "";
  notify(`${model.name} 已删除`);
}

function saveDefaultModel() {
  notify(`默认模型已切换为 ${defaultModel.value}`);
}

function resetNewModel() {
  Object.assign(newModel, {
    name: "",
    provider: "OpenAI",
    modelId: "",
    use: "",
    description: "",
    endpoint: providerEndpoints.OpenAI ?? "",
    authType: "API Key",
    credential: "",
    temperature: 0.3,
    topP: 0.9,
    topK: null,
    maxTokens: 4096,
    contextWindow: 128000,
    frequencyPenalty: 0,
    presencePenalty: 0,
    seed: null,
    stop: "",
    reasoningEffort: "none",
    structuredOutputMethod: "json_schema",
    extraBody: "",
    timeout: 60,
    retries: 2,
    enabled: true,
    note: "",
    scope: "TEAM",
  });
  formError.value = "";
  advancedOpen.value = false;
}

function openAddModel() {
  resetNewModel();
  addOpen.value = true;
}

function updateProviderDefaults() {
  newModel.endpoint = providerEndpoints[newModel.provider] ?? "";
}

async function saveModel() {
  if (
    !newModel.name.trim() ||
    !newModel.provider ||
    !newModel.modelId.trim() ||
    !newModel.use.trim()
  ) {
    formError.value = "请填写模型名称、提供方、模型 ID 和使用场景";
    return;
  }
  if (!newModel.endpoint || !/^https?:\/\//.test(newModel.endpoint.trim())) {
    formError.value = "服务地址必须以 http:// 或 https:// 开头";
    return;
  }
  if (!newModel.credential.trim()) {
    formError.value = "请填写访问凭证，凭证只会保存在当前会话中";
    return;
  }
  if (
    models.value.some(
      (model) =>
        model.name.toLowerCase() === newModel.name.trim().toLowerCase(),
    )
  ) {
    formError.value = "已存在同名模型，请换一个显示名称";
    return;
  }
  if (
    newModel.temperature < 0 ||
    newModel.temperature > 2 ||
    newModel.topP <= 0 ||
    newModel.topP > 1 ||
    (newModel.topK !== null && (!Number.isInteger(newModel.topK) || newModel.topK < 1 || newModel.topK > 1000)) ||
    newModel.frequencyPenalty < -2 ||
    newModel.frequencyPenalty > 2 ||
    newModel.presencePenalty < -2 ||
    newModel.presencePenalty > 2 ||
    (newModel.seed !== null && (!Number.isInteger(newModel.seed) || newModel.seed < 0))
  ) {
    formError.value = "Temperature 需要在 0–2，Top P 需要在 0–1 之间";
    return;
  }
  if (
    newModel.maxTokens < 1 ||
    newModel.contextWindow < 1 ||
    newModel.timeout < 1 ||
    newModel.retries < 0
  ) {
    formError.value = "请检查 Token、超时和重试次数配置";
    return;
  }
  let extraBody: Record<string, unknown> = {};
  if (newModel.extraBody.trim()) {
    try {
      const parsed = JSON.parse(newModel.extraBody);
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error("object required");
      extraBody = parsed as Record<string, unknown>;
    } catch {
      formError.value = "供应商扩展参数必须是合法 JSON 对象";
      return;
    }
  }

  const savedName = newModel.name.trim();
  const endpoint = newModel.endpoint.trim();
  const payload = {
    name: savedName,
    provider: newModel.provider,
    modelId: newModel.modelId.trim(),
    endpoint,
    authType: newModel.authType,
    credential: newModel.credential.trim(),
    enabled: newModel.enabled,
    scope: newModel.scope,
    config: JSON.stringify({
      use: newModel.use.trim(),
      temperature: newModel.temperature,
      topP: newModel.topP,
      ...(newModel.topK === null ? {} : { topK: newModel.topK }),
      maxTokens: newModel.maxTokens,
      contextWindow: newModel.contextWindow,
      frequencyPenalty: newModel.frequencyPenalty,
      presencePenalty: newModel.presencePenalty,
      ...(newModel.seed === null ? {} : { seed: newModel.seed }),
      stop: newModel.stop.split("\n").map((item) => item.trim()).filter(Boolean).slice(0, 4),
      reasoningEffort: newModel.reasoningEffort,
      structuredOutputMethod: newModel.structuredOutputMethod,
      extraBody,
      timeout: newModel.timeout,
      retries: newModel.retries,
      description: newModel.description.trim(),
      note: newModel.note.trim(),
    }),
  };
  let savedModel: ModelRecord;
  try {
    savedModel = fromApiModel(
      await settingsApi.models.create(
        workspaceId.value,
        settingsProjectId.value,
        payload,
      ),
    );
  } catch (error) {
    formError.value =
      error instanceof Error ? error.message : "模型配置保存失败";
    return;
  }
  models.value.push({
    id: savedModel.id,
    name: savedName,
    provider: newModel.provider,
    use: newModel.use.trim(),
    enabled: newModel.enabled,
    latency: "—",
    modelId: newModel.modelId.trim(),
    endpoint,
    authType: newModel.authType,
    credential: newModel.credential.trim(),
    temperature: newModel.temperature,
    topP: newModel.topP,
    topK: newModel.topK,
    maxTokens: newModel.maxTokens,
    contextWindow: newModel.contextWindow,
    frequencyPenalty: newModel.frequencyPenalty,
    presencePenalty: newModel.presencePenalty,
    seed: newModel.seed,
    stop: newModel.stop.split("\n").map((item) => item.trim()).filter(Boolean).slice(0, 4),
    reasoningEffort: newModel.reasoningEffort,
    structuredOutputMethod: newModel.structuredOutputMethod,
    extraBody: newModel.extraBody,
    timeout: newModel.timeout,
    retries: newModel.retries,
    description: newModel.description.trim(),
    note: newModel.note.trim(),
    scope: newModel.scope,
  });
  addOpen.value = false;
  resetNewModel();
  notify(`${savedName} 配置已添加`);
}
</script>

<template>
  <Layout
    eyebrow="WORKSPACE / SETTINGS"
    title="模型配置"
    subtitle="配置工作区的模型、Embedding、默认模型和连接状态"
  >
    <div class="settings-section model-overview">
      <div class="overview-copy">
        <span class="overview-icon"><Cpu :size="18" /></span>
        <div>
          <h2>模型路由</h2>
          <p>
            当前有 {{ enabledCount }} 个模型可供 Agent
            调用，默认模型用于未指定场景。
          </p>
        </div>
      </div>
      <label class="default-model"
        >默认模型<select v-model="defaultModel" @change="saveDefaultModel">
          <option value="">未选择默认模型（运行时使用第一个启用模型）</option>
          <option
            v-for="model in models.filter((item) => item.enabled)"
            :key="model.name"
            :value="model.name"
          >
            {{ model.name }}
          </option>
        </select></label
      >
    </div>
    <div class="settings-section embedding-settings">
      <div class="section-intro">
        <div>
          <h2><Database :size="15" />知识库向量化</h2>
          <p>默认使用本地向量化；只有手动启用外部 API 后才会调用第三方 Embedding 服务。</p>
        </div>
        <span class="embedding-status" :class="{ configured: externalEmbeddingActive }">
          {{ externalEmbeddingActive ? "外部 API 已启用" : "本地向量化" }}
        </span>
      </div>
      <p v-if="embeddingError" class="form-error" role="alert">{{ embeddingError }}</p>
      <div class="embedding-mode-picker" role="radiogroup" aria-label="向量化方式">
        <span class="embedding-mode-title">向量化方式</span>
        <label class="embedding-mode-option" :class="{ active: embeddingForm.mode === 'local' }">
          <input v-model="embeddingForm.mode" type="radio" value="local" />
          <span><strong>本地向量化</strong><small>无需 API，适合本地开发</small></span>
        </label>
        <label class="embedding-mode-option" :class="{ active: embeddingForm.mode === 'api' }">
          <input v-model="embeddingForm.mode" type="radio" value="api" />
          <span><strong>外部 Embedding API</strong><small>手动启用后调用第三方服务</small></span>
        </label>
      </div>
      <p v-if="embeddingForm.mode === 'local'" class="embedding-local-note">
        <Database :size="14" />当前使用本地开发向量化，不会调用外部 Embedding API。切换到外部 API 后需要保存配置才会生效。
      </p>
      <div v-else class="embedding-form-grid">
        <label class="field-label">配置名称<input v-model="embeddingForm.name" maxlength="50" placeholder="例如：项目 Embedding" /></label>
        <label class="field-label">提供方<input v-model="embeddingForm.provider" placeholder="例如：OpenAI、DashScope" /></label>
        <label class="field-label">模型 ID<input v-model="embeddingForm.modelId" placeholder="例如：text-embedding-3-small" /></label>
        <label class="field-label">向量维度<input v-model.number="embeddingForm.dimension" type="number" min="1" step="1" /><small>必须和当前 Milvus 集合维度一致。</small></label>
        <label class="field-label field-wide">服务地址<input v-model="embeddingForm.endpoint" placeholder="https://api.openai.com/v1" /><small>支持 OpenAI 兼容 Embedding 接口。</small></label>
        <label class="field-label field-wide">访问凭证<input v-model="embeddingForm.credential" type="password" autocomplete="new-password" placeholder="首次配置必填；已有配置留空即可保留" /></label>
        <label class="field-label">配置作用域<select v-model="embeddingForm.scope"><option value="TEAM">团队共享</option><option value="PERSONAL">仅自己可用</option></select></label>
      </div>
      <div class="embedding-actions">
        <span v-if="embeddingForm.mode === 'api'" class="dialog-security-note"><ShieldCheck :size="13" />凭证加密保存在后端，不会回显。</span>
        <span v-else class="dialog-security-note"><Database :size="13" />本地模式不会发送外部 Embedding 请求。</span>
        <button v-if="embeddingForm.mode === 'api'" class="button button-secondary button-sm" type="button" :disabled="testingEmbedding || !embeddingModel?.enabled" @click="testEmbedding">{{ testingEmbedding ? "测试中" : "测试连接" }}</button>
        <button class="button button-primary button-sm" type="button" @click="saveEmbedding">{{ embeddingForm.mode === 'api' ? "保存并启用外部 API" : "启用本地向量化" }}</button>
      </div>
    </div>
    <div class="settings-section">
      <div class="section-intro">
        <div>
          <h2>已配置模型</h2>
          <p>为不同任务选择合适的模型，并在变更前测试连接。</p>
        </div>
        <button
          class="button button-secondary button-sm"
          type="button"
          @click="openAddModel"
        >
          <Plus :size="15" />添加模型
        </button>
      </div>
      <div class="config-list model-list">
        <div
          v-for="model in models"
          :key="model.name"
          class="config-row model-row"
        >
          <span class="config-icon"><Cpu :size="17" /></span
          ><span class="model-copy"
            ><strong
              >{{ model.name }}
              <span v-if="defaultModel === model.name" class="default-tag"
                ><Star :size="10" />默认</span
              ></strong
            ><small
              >{{ model.provider }} · {{ model.scope === "PERSONAL" ? "个人" : "团队" }} · {{ model.use }} ·
              {{ model.modelId }}</small
            ></span
          ><span class="latency"><Gauge :size="12" />{{ model.latency }}</span
          ><button
            class="switch-button"
            :class="{ active: model.enabled }"
            type="button"
            :aria-label="`${model.name}${model.enabled ? '停用' : '启用'}`"
            @click="toggleModel(model)"
          >
            <span /></button
          ><button
            class="text-button test-button"
            type="button"
            :disabled="testingModel === model.name"
            @click="testConnection(model)"
          >
            <RefreshCw
              :size="13"
              :class="{ spinning: testingModel === model.name }"
            />{{ testingModel === model.name ? "测试中" : "测试连接" }}
          </button
          ><button
            class="text-button danger-text-button"
            type="button"
            @click="removeModel(model)"
          >
            删除
          </button>
        </div>
        <div v-if="!models.length" class="empty-state">
          <Cpu :size="18" />
          <strong>暂无模型配置</strong>
          <span>添加模型后，这里会显示后端保存的模型配置。</span>
        </div>
      </div>
    </div>
    <div class="settings-section model-note">
      <CheckCircle2 :size="16" />
      <div>
        <strong>连接安全</strong>
        <p>模型凭证仅用于当前连接测试与 Agent 调用，页面不会展示明文内容。</p>
      </div>
    </div>

    <Dialog v-model:open="addOpen"
      ><DialogContent class="model-dialog sm:max-w-4xl"
        ><DialogHeader
          ><DialogTitle>添加模型配置</DialogTitle
          ><DialogDescription
            >完整配置模型连接和生成参数后，再加入工作区模型池。</DialogDescription
          ></DialogHeader
        >
        <div class="model-form-scroll">
          <p v-if="formError" class="form-error" role="alert">
            {{ formError }}
          </p>
          <section class="model-form-section">
            <div class="form-section-heading">
              <span class="form-section-icon"><Settings2 :size="15" /></span>
              <div>
                <strong>基础信息</strong
                ><small>用于识别模型和选择调用场景</small>
              </div>
            </div>
            <div class="model-form-grid">
              <label class="field-label"
                >显示名称<input
                  v-model="newModel.name"
                  maxlength="50"
                  placeholder="例如：GPT-4.1 mini" /></label
              ><label class="field-label"
                >提供方<select
                  v-model="newModel.provider"
                  @change="updateProviderDefaults"
                >
                  <option>OpenAI</option>
                  <option>Anthropic</option>
                  <option>DashScope</option>
                  <option>Azure OpenAI</option>
                </select></label
              ><label class="field-label"
                >配置作用域<select v-model="newModel.scope">
                  <option value="TEAM">团队共享</option>
                  <option value="PERSONAL">仅自己可用</option>
                </select><small>个人配置只对创建者可见，团队配置按项目成员权限使用。</small></label
              ><label class="field-label"
                >模型 ID<input
                  v-model="newModel.modelId"
                  placeholder="例如：gpt-4.1-mini"
                /><small>发送请求时使用的真实模型标识。</small></label
              ><label class="field-label"
                >使用场景<input
                  v-model="newModel.use"
                  maxlength="60"
                  placeholder="例如：快速摘要与分类" /></label
              ><label class="field-label field-wide"
                >配置描述<textarea
                  v-model="newModel.description"
                  rows="2"
                  maxlength="160"
                  placeholder="说明这个模型适合处理哪些任务"
                ></textarea>
              </label>
            </div>
          </section>
          <section class="model-form-section">
            <div class="form-section-heading">
              <span class="form-section-icon"><KeyRound :size="15" /></span>
              <div>
                <strong>连接与凭证</strong
                ><small>配置 API 地址和当前会话使用的认证方式</small>
              </div>
            </div>
            <div class="model-form-grid">
              <label class="field-label"
                >认证方式<select v-model="newModel.authType">
                  <option>API Key</option>
                  <option>OAuth 2.0</option>
                  <option>Workspace Token</option>
                </select></label
              ><label class="field-label"
                >服务地址<input
                  v-model="newModel.endpoint"
                  placeholder="https://api.example.com/v1"
                /><small>支持 OpenAI 兼容接口或厂商原生接口。</small></label
              ><label class="field-label field-wide"
                >访问凭证<input
                  v-model="newModel.credential"
                  type="password"
                  autocomplete="new-password"
                  placeholder="输入 API Key、Token 或 OAuth 凭证"
              /></label>
            </div>
          </section>
          <section class="model-form-section">
            <div class="form-section-heading">
              <span class="form-section-icon"><Zap :size="15" /></span>
              <div>
                <strong>常规设置</strong
                ><small>控制日常运行时最常用的生成参数</small>
              </div>
            </div>
            <div class="model-form-grid">
              <label class="field-label"
                >Temperature<input
                  v-model.number="newModel.temperature"
                  type="number"
                  min="0"
                  max="2"
                  step="0.1"
                /><small>0 更稳定，数值越高越有创造性。</small></label
              ><label class="field-label"
                >最大输出 Tokens<input
                  v-model.number="newModel.maxTokens"
                  type="number"
                  min="1"
                  step="256" /></label>
            </div>
            <button class="advanced-toggle" type="button" :aria-expanded="advancedOpen" @click="advancedOpen = !advancedOpen">
              <span>高级设置</span><span>{{ advancedOpen ? "收起" : "展开" }}</span>
            </button>
            <div v-if="advancedOpen" class="advanced-settings-grid">
              <label class="field-label">Top P<input v-model.number="newModel.topP" type="number" min="0.01" max="1" step="0.05" /><small>采样概率质量，和 Temperature 可独立配置。</small></label>
              <label class="field-label">Top K<input v-model.number="newModel.topK" type="number" min="1" max="1000" step="1" placeholder="供应商默认" /><small>供应商支持时限制候选 Token 数；不同于检索 Top K。</small></label>
              <label class="field-label">频率惩罚<input v-model.number="newModel.frequencyPenalty" type="number" min="-2" max="2" step="0.1" /></label>
              <label class="field-label">存在惩罚<input v-model.number="newModel.presencePenalty" type="number" min="-2" max="2" step="0.1" /></label>
              <label class="field-label">随机种子<input v-model.number="newModel.seed" type="number" min="0" step="1" placeholder="不固定" /><small>供应商支持时用于复现输出。</small></label>
              <label class="field-label">上下文窗口 Tokens<input v-model.number="newModel.contextWindow" type="number" min="1" step="1024" /></label>
              <label class="field-label">停止序列<textarea v-model="newModel.stop" rows="2" placeholder="每行一个停止序列" /><small>最多 4 个；按行填写。</small></label>
              <label class="field-label">推理强度<select v-model="newModel.reasoningEffort"><option value="none">不指定</option><option value="low">低</option><option value="medium">中</option><option value="high">高</option></select></label>
              <label class="field-label">结构化输出方式<select v-model="newModel.structuredOutputMethod"><option value="json_schema">JSON Schema</option><option value="function_calling">Function Calling</option><option value="json_mode">JSON Mode</option></select></label>
              <label class="field-label field-wide">供应商扩展参数<textarea v-model="newModel.extraBody" rows="3" placeholder='例如：{"min_p": 0.05}' /><small>仅在供应商明确支持时填写，必须是 JSON 对象。</small></label>
            </div>
          </section>
          <section class="model-form-section">
            <div class="form-section-heading">
              <span class="form-section-icon"><Timer :size="15" /></span>
              <div>
                <strong>运行策略</strong
                ><small>控制请求时长、失败重试和启用状态</small>
              </div>
            </div>
            <div class="model-form-grid">
              <label class="field-label"
                >请求超时（秒）<input
                  v-model.number="newModel.timeout"
                  type="number"
                  min="1"
                  max="600" /></label
              ><label class="field-label"
                >失败重试次数<input
                  v-model.number="newModel.retries"
                  type="number"
                  min="0"
                  max="5" /></label
              ><label class="enable-model-toggle"
                ><input
                  v-model="newModel.enabled"
                  type="checkbox"
                  class="switch-input"
                /><span class="switch-ui" /><span
                  ><strong>添加后立即启用</strong
                  ><small>关闭后仅保存配置，不参与默认路由。</small></span
                ></label
              ><label class="field-label field-wide"
                >内部备注<textarea
                  v-model="newModel.note"
                  rows="2"
                  maxlength="160"
                  placeholder="例如：仅在海外资料调研时使用"
                ></textarea>
              </label>
            </div>
            <p class="model-capability-note">
              模型能力由实际模型与提供方决定，此处不手动配置。
            </p>
          </section>
        </div>
        <DialogFooter
          ><span class="dialog-security-note"
            ><ShieldCheck :size="13" />凭证不会显示在模型列表中</span
          ><button
            class="button button-secondary"
            type="button"
            @click="addOpen = false"
          >
            取消</button
          ><button
            class="button button-primary"
            type="button"
            @click="saveModel"
          >
            保存并添加
          </button></DialogFooter
        ></DialogContent
      ></Dialog
    >
  </Layout>
</template>

<style scoped>
.section-intro {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}
.section-intro > .button {
  flex: 0 0 auto;
}
.model-overview {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  background: linear-gradient(
    110deg,
    color-mix(in oklab, var(--teal) 7%, var(--surface)),
  var(--surface)
  );
}
.embedding-settings {
  display: grid;
  gap: 0.875rem;
}
.embedding-settings h2 {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  margin: 0;
  color: var(--workspace-text);
  font-size: 0.875rem;
}
.embedding-settings h2 svg {
  color: var(--teal-dark);
}
.embedding-status {
  flex: 0 0 auto;
  padding: 0.3125rem 0.5rem;
  border-radius: 999px;
  color: var(--workspace-muted);
  background: var(--surface-raised);
  font-size: 0.5625rem;
}
.embedding-status.configured {
  color: var(--teal-dark);
  background: #e4f6f3;
}
.embedding-mode-picker {
  display: flex;
  align-items: stretch;
  gap: 0.5rem;
  margin-bottom: 0.875rem;
}
.embedding-mode-title {
  display: flex;
  min-width: 5rem;
  align-items: center;
  color: var(--workspace-muted);
  font-size: 0.5625rem;
  font-weight: 650;
}
.embedding-mode-option {
  position: relative;
  display: flex;
  flex: 1 1 0;
  align-items: center;
  gap: 0.5rem;
  min-width: 0;
  padding: 0.625rem 0.75rem;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.5rem;
  background: var(--surface);
  color: var(--workspace-muted);
  cursor: pointer;
  transition: border-color 160ms ease, background 160ms ease;
}
.embedding-mode-option::before {
  width: 0.75rem;
  height: 0.75rem;
  flex: 0 0 auto;
  border: 0.125rem solid var(--workspace-border);
  border-radius: 50%;
  background: transparent;
  content: "";
}
.embedding-mode-option:hover {
  border-color: color-mix(in oklab, var(--teal) 42%, var(--workspace-border));
}
.embedding-mode-option.active {
  border-color: var(--teal);
  background: color-mix(in oklab, var(--teal) 9%, var(--surface));
  color: var(--workspace-text);
}
.embedding-mode-option.active::before {
  border-color: var(--teal);
  background: var(--teal);
  box-shadow: inset 0 0 0 0.1875rem var(--surface);
}
.embedding-mode-option input {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
  pointer-events: none;
}
.embedding-mode-option span {
  display: grid;
  min-width: 0;
  gap: 0.1875rem;
}
.embedding-mode-option strong {
  color: inherit;
  font-size: 0.625rem;
}
.embedding-mode-option small {
  overflow: hidden;
  color: var(--workspace-muted);
  font-size: 0.5rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.embedding-local-note {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  margin: 0;
  padding: 0.75rem;
  border: 0.0625rem solid color-mix(in oklab, var(--teal) 24%, var(--workspace-border));
  border-radius: 0.5rem;
  background: color-mix(in oklab, var(--teal) 7%, var(--surface));
  color: var(--workspace-muted);
  font-size: 0.5625rem;
}
.embedding-local-note svg {
  flex: 0 0 auto;
  color: var(--teal);
}
.embedding-form-grid,
.model-form-grid {
  display: grid;
  align-items: start;
}
.embedding-form-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.75rem;
}
.embedding-form-grid .field-wide {
  grid-column: 1 / -1;
}
.embedding-actions {
  display: flex;
  align-items: center;
  gap: 0.625rem;
  padding-top: 0.75rem;
  border-top: 0.0625rem solid var(--workspace-divider);
}
.embedding-actions .dialog-security-note {
  margin-right: auto;
}
.overview-copy {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}
.overview-icon {
  display: grid;
  place-items: center;
  width: 2.25rem;
  height: 2.25rem;
  border-radius: 0.5625rem;
  color: var(--teal-dark);
  background: #e2f7f3;
}
.overview-copy h2 {
  margin: 0;
  color: var(--workspace-text);
  font-size: 0.875rem;
}
.overview-copy p {
  margin: 0.3125rem 0 0;
  color: var(--workspace-muted);
  font-size: 0.625rem;
}
.default-model {
  display: grid;
  gap: 0.375rem;
  min-width: 11.25rem;
  color: var(--workspace-muted);
  font-size: 0.5625rem;
}
.default-model select {
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.4375rem;
  padding: 0.5rem 0.625rem;
  color: var(--workspace-text);
  background: var(--surface);
  font: inherit;
  font-size: 0.625rem;
}
.model-list {
  max-width: none;
}
.model-row {
  min-height: 4.25rem;
}
.model-copy {
  flex: 1;
  min-width: 0;
}
.model-copy strong,
.model-copy small {
  display: block;
}
.model-copy strong {
  color: var(--workspace-text);
  font-size: 0.6875rem;
}
.model-copy small {
  margin-top: 0.25rem;
  color: var(--workspace-muted);
  font-size: 0.5625rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.default-tag {
  display: inline-flex;
  align-items: center;
  gap: 0.1875rem;
  margin-left: 0.3125rem;
  color: var(--teal-dark);
  font-size: 0.5rem;
  font-weight: 500;
}
.latency {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  min-width: 3.5rem;
  color: var(--workspace-muted);
  font-size: 0.5625rem;
}
.switch-button {
  width: 2.125rem;
  height: 1.1875rem;
  padding: 0;
  border: 0;
  border-radius: 999px;
  background: #d8e2e2;
  cursor: pointer;
}
.switch-button span {
  display: block;
  width: 0.875rem;
  height: 0.875rem;
  margin: 0.15625rem;
  border-radius: 50%;
  background: #fff;
  transition: transform 0.16s;
  box-shadow: 0 0.0625rem 0.125rem rgba(0, 0, 0, 0.12);
}
.switch-button.active {
  background: var(--teal);
}
.switch-button.active span {
  transform: translateX(0.9375rem);
}
.test-button:disabled {
  cursor: wait;
  opacity: 0.65;
}
.spinning {
  animation: spin 800ms linear infinite;
}
.model-note {
  display: flex;
  align-items: center;
  gap: 0.625rem;
  color: var(--teal-dark);
  background: #f3fbfa;
}
.model-note strong {
  display: block;
  color: var(--workspace-text);
  font-size: 0.625rem;
}
.model-note p {
  margin: 0.25rem 0 0;
  color: var(--workspace-muted);
  font-size: 0.5625rem;
}
.model-dialog {
  max-width: 54rem !important;
}
.model-form-scroll {
  display: grid;
  gap: 0.75rem;
  max-height: min(68vh, 42rem);
  overflow: auto;
  padding: 0.125rem 0.25rem 0.125rem 0;
}
.model-form-section {
  padding: 1rem;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.625rem;
  background: #fbfdfd;
}
.form-section-heading {
  display: flex;
  align-items: center;
  gap: 0.5625rem;
  margin-bottom: 0.875rem;
}
.form-section-heading > div {
  display: grid;
  gap: 0.1875rem;
}
.form-section-heading strong {
  color: var(--workspace-text);
  font-size: 0.6875rem;
}
.form-section-heading small {
  color: var(--workspace-muted);
  font-size: 0.5625rem;
}
.form-section-icon {
  display: grid;
  place-items: center;
  width: 1.75rem;
  height: 1.75rem;
  border-radius: 0.4375rem;
  color: var(--teal-dark);
  background: #e4f6f3;
}
.model-form-grid {
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
  max-width: none;
}
.advanced-toggle {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  margin-top: 0.875rem;
  padding: 0.625rem 0.75rem;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.4375rem;
  color: var(--workspace-text);
  background: var(--surface);
  font: inherit;
  font-size: 0.625rem;
  font-weight: 650;
  cursor: pointer;
}
.advanced-toggle span:last-child {
  color: var(--teal-dark);
  font-size: 0.5625rem;
  font-weight: 500;
}
.advanced-settings-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
  margin-top: 0.75rem;
  padding-top: 0.75rem;
  border-top: 0.0625rem solid var(--workspace-divider);
}
.advanced-settings-grid .field-wide {
  grid-column: 1 / -1;
}
.model-form-grid .field-wide {
  grid-column: 1 / -1;
}
.field-label small,
.enable-model-toggle small {
  color: var(--workspace-subtle);
  font-size: 0.5rem;
  font-weight: 400;
  line-height: 1.35;
}
.form-error {
  margin: 0;
  padding: 0.625rem 0.75rem;
  border: 0.0625rem solid #f0caca;
  border-radius: 0.4375rem;
  color: #a14d4d;
  background: #fff5f5;
  font-size: 0.625rem;
}
.enable-model-toggle {
  display: flex;
  align-items: center;
  gap: 0.5625rem;
  min-height: 2.25rem;
  cursor: pointer;
}
.enable-model-toggle > span:last-child {
  display: grid;
  gap: 0.1875rem;
}
.enable-model-toggle strong {
  color: var(--workspace-text);
  font-size: 0.625rem;
}
.model-capability-note {
  margin: 0.75rem 0 0;
  color: var(--workspace-muted);
  font-size: 0.5rem;
  line-height: 1.35;
}
.switch-input {
  position: absolute;
  opacity: 0;
  pointer-events: none;
}
.switch-ui {
  width: 2.125rem;
  height: 1.1875rem;
  flex: 0 0 auto;
  border-radius: 999px;
  background: #d8e2e2;
  transition: background 0.16s;
}
.switch-ui::after {
  display: block;
  width: 0.875rem;
  height: 0.875rem;
  margin: 0.15625rem;
  border-radius: 50%;
  background: #fff;
  content: "";
  transition: transform 0.16s;
  box-shadow: 0 0.0625rem 0.125rem rgba(0, 0, 0, 0.12);
}
.switch-input:checked + .switch-ui {
  background: var(--teal);
}
.switch-input:checked + .switch-ui::after {
  transform: translateX(0.9375rem);
}
.dialog-security-note {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  margin-right: auto;
  color: var(--workspace-muted);
  font-size: 0.5rem;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
@media (max-width: 47.5rem) {
  .model-overview {
    align-items: stretch;
    flex-direction: column;
  }
  .default-model {
    min-width: 0;
  }
  .model-row {
    align-items: flex-start;
    flex-wrap: wrap;
  }
  .model-row .test-button {
    margin-left: 2.625rem;
  }
  .latency {
    margin-left: auto;
  }
  .model-form-grid {
    grid-template-columns: 1fr;
  }
  .advanced-settings-grid {
    grid-template-columns: 1fr;
  }
  .embedding-form-grid {
    grid-template-columns: 1fr;
  }
  .embedding-mode-picker {
    flex-wrap: wrap;
  }
  .embedding-mode-title {
    flex-basis: 100%;
    min-height: 1.25rem;
  }
  .embedding-form-grid .field-wide {
    grid-column: auto;
  }
  .embedding-actions {
    align-items: stretch;
    flex-wrap: wrap;
  }
  .embedding-actions .dialog-security-note {
    flex-basis: 100%;
  }
  .model-form-grid .field-wide {
    grid-column: auto;
  }
  .advanced-settings-grid .field-wide {
    grid-column: auto;
  }
  .model-form-section {
    padding: 0.8125rem;
  }
  .dialog-security-note {
    display: none;
  }
}
</style>
