<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import {
  CheckCircle2,
  Cpu,
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

type CapabilityKey = "streaming" | "functionCalling" | "vision" | "jsonMode";

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
  maxTokens: number;
  contextWindow: number;
  timeout: number;
  retries: number;
  capabilities: Record<CapabilityKey, boolean>;
  description: string;
  note: string;
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

const defaultCapabilities = (): Record<CapabilityKey, boolean> => ({
  streaming: true,
  functionCalling: true,
  vision: false,
  jsonMode: true,
});
const emptyCapabilities = (): Record<CapabilityKey, boolean> => ({
  streaming: false,
  functionCalling: false,
  vision: false,
  jsonMode: false,
});

const models = ref<ModelRecord[]>([]);
const defaultModel = ref("");
const addOpen = ref(false);
const testingModel = ref("");
const formError = ref("");
const newModel = reactive({
  name: "",
  provider: "OpenAI",
  modelId: "",
  use: "",
  description: "",
  endpoint: providerEndpoints.OpenAI,
  authType: "API Key",
  credential: "",
  temperature: 0.3,
  topP: 0.9,
  maxTokens: 4096,
  contextWindow: 128000,
  timeout: 60,
  retries: 2,
  enabled: true,
  note: "",
  capabilities: defaultCapabilities(),
});
const enabledCount = computed(
  () => models.value.filter((model) => model.enabled).length,
);

function fromApiModel(model: ProjectModelConfig): ModelRecord {
  let config: Partial<ModelRecord> & { capabilities?: Partial<Record<CapabilityKey, boolean>> } = {};
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
    temperature: Number(config.temperature ?? 0),
    topP: Number(config.topP ?? 0),
    maxTokens: Number(config.maxTokens ?? 0),
    contextWindow: Number(config.contextWindow ?? 0),
    timeout: Number(config.timeout ?? 0),
    retries: Number(config.retries ?? 0),
    capabilities: { ...emptyCapabilities(), ...config.capabilities },
    description: String(config.description || ""),
    note: String(config.note || ""),
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
    models.value = remoteModels.map(fromApiModel);
    defaultModel.value = "";
  } catch {
    notify("模型配置加载失败");
  }
});

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

function testConnection(modelName: string) {
  notify(`${modelName} 暂无后端连接测试接口，未修改连接状态`);
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
    endpoint: providerEndpoints.OpenAI,
    authType: "API Key",
    credential: "",
    temperature: 0.3,
    topP: 0.9,
    maxTokens: 4096,
    contextWindow: 128000,
    timeout: 60,
    retries: 2,
    enabled: true,
    note: "",
    capabilities: defaultCapabilities(),
  });
  formError.value = "";
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
    newModel.topP < 0 ||
    newModel.topP > 1
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
    config: JSON.stringify({
      use: newModel.use.trim(),
      temperature: newModel.temperature,
      topP: newModel.topP,
      maxTokens: newModel.maxTokens,
      contextWindow: newModel.contextWindow,
      timeout: newModel.timeout,
      retries: newModel.retries,
      capabilities: newModel.capabilities,
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
    maxTokens: newModel.maxTokens,
    contextWindow: newModel.contextWindow,
    timeout: newModel.timeout,
    retries: newModel.retries,
    capabilities: { ...newModel.capabilities },
    description: newModel.description.trim(),
    note: newModel.note.trim(),
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
    subtitle="配置工作区的模型能力、默认模型和连接状态"
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
        >默认模型<select v-model="defaultModel" disabled>
          <option value="">后端未提供默认模型配置</option>
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
              >{{ model.provider }} · {{ model.use }} ·
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
            @click="testConnection(model.name)"
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
            >完整配置模型连接、生成参数和 Agent
            能力后，再加入工作区模型池。</DialogDescription
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
                <strong>生成参数</strong
                ><small>控制输出随机性、长度和上下文容量</small>
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
                >Top P<input
                  v-model.number="newModel.topP"
                  type="number"
                  min="0"
                  max="1"
                  step="0.05"
                /><small>建议与 Temperature 只调整一个。</small></label
              ><label class="field-label"
                >最大输出 Tokens<input
                  v-model.number="newModel.maxTokens"
                  type="number"
                  min="1"
                  step="256" /></label
              ><label class="field-label"
                >上下文窗口 Tokens<input
                  v-model.number="newModel.contextWindow"
                  type="number"
                  min="1"
                  step="1024"
              /></label>
            </div>
          </section>
          <section class="model-form-section">
            <div class="form-section-heading">
              <span class="form-section-icon"><Timer :size="15" /></span>
              <div>
                <strong>运行策略</strong
                ><small>控制请求时长、失败重试和能力开关</small>
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
              ><label class="capability-toggle"
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
            <div class="capability-list">
              <span class="capability-title">模型能力</span
              ><label
                ><input
                  v-model="newModel.capabilities.streaming"
                  type="checkbox"
                />流式输出</label
              ><label
                ><input
                  v-model="newModel.capabilities.functionCalling"
                  type="checkbox"
                />函数调用</label
              ><label
                ><input
                  v-model="newModel.capabilities.vision"
                  type="checkbox"
                />图像理解</label
              ><label
                ><input
                  v-model="newModel.capabilities.jsonMode"
                  type="checkbox"
                />JSON 输出</label
              >
            </div>
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
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
  max-width: none;
}
.model-form-grid .field-wide {
  grid-column: 1 / -1;
}
.field-label small,
.capability-toggle small {
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
.capability-toggle {
  display: flex;
  align-items: center;
  gap: 0.5625rem;
  min-height: 2.25rem;
  cursor: pointer;
}
.capability-toggle > span:last-child {
  display: grid;
  gap: 0.1875rem;
}
.capability-toggle strong {
  color: var(--workspace-text);
  font-size: 0.625rem;
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
.capability-list {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.5rem 0.875rem;
  margin-top: 0.875rem;
  padding-top: 0.75rem;
  border-top: 0.0625rem solid var(--workspace-divider);
  color: var(--workspace-muted);
  font-size: 0.5625rem;
}
.capability-title {
  color: var(--workspace-text);
  font-weight: 650;
}
.capability-list label {
  display: inline-flex;
  align-items: center;
  gap: 0.3125rem;
  cursor: pointer;
}
.capability-list input {
  accent-color: var(--teal);
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
  .model-form-grid .field-wide {
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
