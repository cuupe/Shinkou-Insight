<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import {
  ArrowRight,
  BarChart3,
  BookOpen,
  CheckCircle2,
  ChevronDown,
  CircleHelp,
  FileText,
  HelpCircle,
  MessageCircle,
  Network,
  Search,
  ShieldCheck,
  Sparkles,
  Users,
  X,
} from "@lucide/vue";
import PageHeader from "@/components/common/PageHeader.vue";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useWorkspace } from "@/composables/useWorkspace";

type HelpArticle = {
  id: string;
  category: string;
  title: string;
  description: string;
  readTime: string;
  icon: typeof BookOpen;
  tags: string[];
  content: string[];
};

const { router, routeTo, notify } = useWorkspace();
const searchQuery = ref("");
const searchInput = ref<HTMLInputElement | null>(null);
const selectedCategory = ref("全部");
const selectedArticle = ref<HelpArticle | null>(null);
const articleOpen = ref(false);
const openFaq = ref<string | null>("faq-1");
const feedbackState = ref<"helpful" | "not-helpful" | "">("");

const categories = [
  { label: "全部", icon: BookOpen },
  { label: "快速开始", icon: Sparkles },
  { label: "知识库", icon: FileText },
  { label: "Agent 调研", icon: MessageCircle },
  { label: "报告与评估", icon: BarChart3 },
  { label: "工作区与权限", icon: ShieldCheck },
];

const articles: HelpArticle[] = [
  {
    id: "start-here",
    category: "快速开始",
    title: "从零开始查看调研结果",
    description: "了解从准备资料、查看运行到沉淀报告的完整工作流。",
    readTime: "3 分钟",
    icon: Sparkles,
    tags: ["入门", "工作流"],
    content: [
      "Shinkou Insight 的项目流程从项目启动工作台开始：先和 Agent 描述目标，再由 Agent 串联规划、资料搜集、市场比较、审查和报告输出。",
      "先在项目中上传 PDF、Markdown 或 TXT 资料。资料完成索引后，可以前往检索 Playground 验证召回结果，再到 Agent 任务队列查看已有运行。",
      "调研完成后，报告会出现在报告页面。你可以编辑摘要、发布报告，并从报告中继续创建行动项。",
    ],
  },
  {
    id: "knowledge-base",
    category: "知识库",
    title: "如何准备高质量知识库",
    description: "掌握资料格式、索引状态与召回效果之间的关系。",
    readTime: "4 分钟",
    icon: FileText,
    tags: ["知识库", "检索"],
    content: [
      "清晰的资料结构会直接影响 Agent 的检索质量。建议将长文档按主题拆分，并为文件使用容易识别的名称。",
      "上传后，资料会经历等待索引、索引中、已索引或失败几个状态。只有已索引的资料会参与检索。",
      "如果召回结果不理想，可以先在 Playground 中调整检索模式、Top K 和 Rerank，再回到调研流程中验证。",
    ],
  },
  {
    id: "agent-research",
    category: "Agent 调研",
    title: "查看调研任务与运行过程",
    description: "理解 Agent 任务状态、运行过程和结果入口。",
    readTime: "5 分钟",
    icon: MessageCircle,
    tags: ["Agent", "任务队列"],
    content: [
      "任务进入队列后，可在 Agent 任务队列查看状态与运行详情。运行记录会保留任务的处理进度和结果入口。",
      "如果需要验证知识库效果，可以先在 Playground 中检查召回结果，再回到任务队列查看已有运行。",
      "运行中的任务会持续记录检索证据和关键事件。完成后可以从运行详情跳转到报告或继续追问。",
    ],
  },
  {
    id: "reports-evaluation",
    category: "报告与评估",
    title: "让报告和评估结果可复用",
    description: "学习如何编辑报告、管理引用并使用评估集检查质量。",
    readTime: "4 分钟",
    icon: BarChart3,
    tags: ["报告", "评估"],
    content: [
      "报告页面会保留标题、导语、执行摘要和推荐方案。编辑后可以发布为团队可查看的正式版本。",
      "评估用例用于检查召回率、引用准确率和结构化输出。用例越贴近真实业务问题，质量基线越有参考价值。",
      "当前质量拆解会根据后端返回的评估用例实时计算；质量趋势需要积累多次评估运行记录后展示。",
    ],
  },
  {
    id: "workspace-permissions",
    category: "工作区与权限",
    title: "成员角色与访问权限说明",
    description: "了解所有者、管理员和成员可以执行哪些操作。",
    readTime: "3 分钟",
    icon: Users,
    tags: ["成员", "权限"],
    content: [
      "工作区所有者拥有完整管理权限，可以邀请成员、调整角色和修改工作区设置。管理员可以管理普通成员，但不能修改所有者。",
      "普通成员默认可以查看工作区概览和项目内容，具体编辑权限会根据页面能力逐步开放。",
      "邀请成员时请补充部门、职位和邀请说明，便于团队成员确认访问范围。",
    ],
  },
  {
    id: "retrieval-playground",
    category: "知识库",
    title: "用 Playground 调试一次检索",
    description: "从查询、参数到证据片段，快速定位召回问题。",
    readTime: "3 分钟",
    icon: Search,
    tags: ["Playground", "调试"],
    content: [
      "在检索 Playground 输入完整的问题，而不是只输入几个关键词。这样更接近 Agent 实际使用知识库的场景。",
      "Hybrid 模式会综合语义和关键词召回，Vector 模式更偏向语义相似度。Top K 决定返回的候选数量，Rerank 会对候选结果二次排序。",
      "没有召回结果时，页面会保持空状态。可以先检查资料是否已完成索引，再逐步调整参数。",
    ],
  },
  {
    id: "model-configuration",
    category: "工作区与权限",
    title: "模型配置与连接器怎么设置",
    description: "了解模型、工具连接器和权限配置的职责边界。",
    readTime: "4 分钟",
    icon: Network,
    tags: ["模型配置", "连接器", "设置"],
    content: [
      "模型配置用于指定 Agent 使用的模型服务和推理参数。建议先确认模型名称、服务地址和凭据配置，再进行连通性测试。",
      "工具与连接器用于接入外部搜索或业务系统。连接器只应开放完成当前任务所需的最小权限，并定期检查授权状态。",
      "如果模型或连接器不可用，请先查看对应页面的测试结果，再确认工作区权限和网络配置是否符合要求。",
    ],
  },
  {
    id: "troubleshooting",
    category: "快速开始",
    title: "常见问题排查清单",
    description: "从登录、项目选择到任务失败，按顺序定位问题。",
    readTime: "4 分钟",
    icon: HelpCircle,
    tags: ["排查", "错误", "故障"],
    content: [
      "先确认当前账号仍处于登录状态，并且 URL 中的工作区和项目是当前账号有权限访问的对象。",
      "如果页面显示为空，优先检查后端是否返回数据；空状态不会使用静态业务记录填充。对于索引、检索或评估问题，先查看页面上的状态提示。",
      "如果任务进入失败状态，请打开运行详情查看错误信息，记录任务编号和发生时间，再进行重试或调整配置。",
    ],
  },
];

const faqs = [
  {
    id: "faq-1",
    question: "为什么上传的资料还没有出现在检索结果中？",
    answer:
      "资料需要先完成索引才能参与检索。请在知识库页面查看索引状态；如果状态为失败，可以查看错误提示并重新索引。",
  },
  {
    id: "faq-2",
    question: "没有召回结果时，应该先检查什么？",
    answer:
      "先确认当前项目已选择、资料已完成索引，再检查问题是否足够具体。之后可以在 Playground 中切换 Hybrid / Vector、调整 Top K 或启用 Rerank。",
  },
  {
    id: "faq-3",
    question: "谁可以邀请成员和修改角色？",
    answer:
      "工作区所有者和管理员可以邀请成员；所有者可以在管理员和成员之间分配角色，管理员只能管理普通成员。",
  },
  {
    id: "faq-4",
    question: "评估页面为什么暂时没有质量趋势？",
    answer:
      "质量趋势依赖多次历史评估运行记录。当前页面会先展示基于现有评估用例计算的质量拆解，积累历史数据后再生成趋势。",
  },
  {
    id: "faq-5",
    question: "工作区设置、模型配置和连接器有什么区别？",
    answer:
      "工作区设置管理基础信息和通用策略；模型配置决定 Agent 使用哪类模型服务；连接器负责授权外部工具或数据源，三者可以分别测试和维护。",
  },
  {
    id: "faq-6",
    question: "页面显示为空时，是否代表系统没有数据？",
    answer:
      "页面空状态只表示当前接口没有返回可展示的数据，不会自动填充演示内容。请先确认工作区、项目和筛选条件，再检查对应后端接口状态。",
  },
];

const shortcuts = [
  {
    label: "项目启动",
    detail: "从 Agent 对话发起项目流程",
    icon: MessageCircle,
    route: "project-agent-chat",
  },
  {
    label: "知识库",
    detail: "管理资料和索引",
    icon: FileText,
    route: "project-assets",
  },
  {
    label: "报告",
    detail: "阅读和发布报告",
    icon: BarChart3,
    route: "project-reports",
  },
  {
    label: "成员与权限",
    detail: "管理工作区成员",
    icon: Users,
    route: "workspace-members",
  },
];

const featuredArticles = computed(() => articles.slice(0, 3));
const filteredArticles = computed(() => {
  const query = searchQuery.value.trim().toLowerCase();
  return articles.filter((article) => {
    const matchesCategory =
      selectedCategory.value === "全部" ||
      article.category === selectedCategory.value;
    const matchesQuery =
      !query ||
      [article.title, article.description, article.category, ...article.tags]
        .join(" ")
        .toLowerCase()
        .includes(query);
    return matchesCategory && matchesQuery;
  });
});

function focusSearch(event: KeyboardEvent) {
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
    event.preventDefault();
    searchInput.value?.focus();
  }
}

onMounted(() => window.addEventListener("keydown", focusSearch));
onBeforeUnmount(() => window.removeEventListener("keydown", focusSearch));

function categoryCount(category: string) {
  return category === "全部"
    ? articles.length
    : articles.filter((article) => article.category === category).length;
}

function openArticle(article: HelpArticle) {
  selectedArticle.value = article;
  articleOpen.value = true;
  feedbackState.value = "";
}

function toggleFaq(id: string) {
  openFaq.value = openFaq.value === id ? null : id;
}

function submitFeedback(value: "helpful" | "not-helpful") {
  feedbackState.value = value;
  notify(
    value === "helpful"
      ? "感谢反馈，很高兴这篇内容帮到了你"
      : "已记录反馈，我们会继续完善帮助内容",
  );
}
</script>

<template>
  <PageHeader
    eyebrow="SUPPORT / HELP CENTER"
    title="帮助中心"
    subtitle="从第一次使用到深入调试，找到你需要的答案"
  >
  </PageHeader>

  <div class="help-center">
    <section class="help-hero panel">
      <div class="help-hero-copy">
        <span class="help-hero-kicker"
          ><CircleHelp :size="14" />有什么可以帮你？</span
        >
        <h2>从这里开始探索 Shinkou Insight</h2>
        <p>搜索产品指南、使用技巧和常见问题，快速找到下一步。</p>
        <label class="help-search">
          <Search :size="18" />
          <input
            ref="searchInput"
            v-model="searchQuery"
            type="search"
            placeholder="搜索帮助主题，例如：如何查看调研运行…"
            aria-label="搜索帮助内容"
          />
          <button
            v-if="searchQuery"
            class="help-search-clear"
            type="button"
            aria-label="清除搜索"
            @click="searchQuery = ''"
          >
            <X :size="14" />
          </button>
          <kbd v-else>Ctrl K</kbd>
        </label>
        <div class="help-search-suggestions">
          <span>热门搜索</span>
          <button
            v-for="term in ['上传资料', '查看调研运行', '成员权限']"
            :key="term"
            type="button"
            @click="searchQuery = term"
          >
            {{ term }}
          </button>
        </div>
      </div>
      <div class="help-hero-visual" aria-hidden="true">
        <div class="help-orbit help-orbit-one" />
        <div class="help-orbit help-orbit-two" />
        <div class="help-hero-icon"><Sparkles :size="28" /></div>
        <span class="help-hero-chip chip-top"
          ><CheckCircle2 :size="13" />可验证</span
        >
        <span class="help-hero-chip chip-right"
          ><ShieldCheck :size="13" />有依据</span
        >
        <span class="help-hero-chip chip-bottom"
          ><Network :size="13" />可协作</span
        >
      </div>
    </section>

    <section class="help-featured-section">
      <div class="help-section-heading">
        <div>
          <span class="section-kicker">START HERE</span>
          <h2>推荐阅读</h2>
          <p>三篇内容，带你快速走完第一条工作流</p>
        </div>
        <span class="help-result-count">{{ articles.length }} 篇帮助内容</span>
      </div>
      <div class="help-featured-grid">
        <button
          v-for="(article, index) in featuredArticles"
          :key="article.id"
          class="help-featured-card"
          type="button"
          @click="openArticle(article)"
        >
          <span class="help-card-index">0{{ index + 1 }}</span>
          <span class="help-card-icon"
            ><component :is="article.icon" :size="18"
          /></span>
          <strong>{{ article.title }}</strong>
          <span>{{ article.description }}</span>
          <small>{{ article.readTime }}阅读 <ArrowRight :size="13" /></small>
        </button>
      </div>
    </section>

    <div class="help-content-layout">
      <aside class="panel help-category-panel">
        <div class="help-category-heading">
          <span>浏览主题</span><BookOpen :size="15" />
        </div>
        <nav class="help-category-list" aria-label="帮助内容分类">
          <button
            v-for="category in categories"
            :key="category.label"
            type="button"
            :class="{ active: selectedCategory === category.label }"
            :aria-pressed="selectedCategory === category.label"
            @click="selectedCategory = category.label"
          >
            <component :is="category.icon" :size="15" /><span>{{
              category.label
            }}</span
            ><small>{{ categoryCount(category.label) }}</small>
          </button>
        </nav>
        <div class="help-category-note">
          <HelpCircle :size="15" /><span
            >找不到想要的内容？试试其他主题或清除搜索条件。</span
          >
        </div>
      </aside>

      <main class="help-main-column">
        <section class="panel help-articles-panel">
          <div class="help-section-heading help-articles-heading">
            <div>
              <span class="section-kicker">KNOWLEDGE BASE</span>
              <h2>
                {{
                  selectedCategory === "全部"
                    ? "全部帮助内容"
                    : selectedCategory
                }}
              </h2>
              <p>
                {{
                  searchQuery
                    ? `正在查找“${searchQuery}”`
                    : "按主题浏览产品说明和使用指南"
                }}
              </p>
            </div>
            <span
              v-if="searchQuery || selectedCategory !== '全部'"
              class="help-result-count"
              >{{ filteredArticles.length }} 条结果</span
            >
          </div>
          <div v-if="filteredArticles.length" class="help-article-list">
            <button
              v-for="article in filteredArticles"
              :key="article.id"
              class="help-article-row"
              type="button"
              @click="openArticle(article)"
            >
              <span class="help-article-row-icon"
                ><component :is="article.icon" :size="17"
              /></span>
              <span class="help-article-row-copy"
                ><strong>{{ article.title }}</strong
                ><small>{{ article.description }}</small
                ><em
                  ><span>{{ article.category }}</span
                  ><i />{{ article.readTime }}阅读</em
                ></span
              >
              <ArrowRight :size="16" />
            </button>
          </div>
          <div v-else class="help-no-results">
            <Search :size="20" /><strong>没有找到相关内容</strong
            ><span>试试更短的关键词，或清除搜索条件后浏览全部主题。</span
            ><button
              class="button button-secondary button-sm"
              type="button"
              @click="
                searchQuery = '';
                selectedCategory = '全部';
              "
            >
              查看全部内容
            </button>
          </div>
        </section>

        <section class="panel help-faq-panel">
          <div class="help-section-heading">
            <div>
              <span class="section-kicker">FREQUENTLY ASKED</span>
              <h2>常见问题</h2>
              <p>遇到相似问题时，可以先从这里开始排查</p>
            </div>
            <CircleHelp :size="20" class="help-heading-icon" />
          </div>
          <div class="help-faq-list">
            <div
              v-for="faq in faqs"
              :key="faq.id"
              class="help-faq-item"
              :class="{ open: openFaq === faq.id }"
            >
              <button
                type="button"
                :aria-expanded="openFaq === faq.id"
                @click="toggleFaq(faq.id)"
              >
                <span>{{ faq.question }}</span
                ><ChevronDown :size="16" />
              </button>
              <p v-if="openFaq === faq.id">{{ faq.answer }}</p>
            </div>
          </div>
        </section>
      </main>
    </div>

    <section class="help-shortcuts-section">
      <div class="help-section-heading">
        <div>
          <span class="section-kicker">QUICK ACCESS</span>
          <h2>直接进入工作区</h2>
          <p>不用离开帮助中心，直接打开常用功能</p>
        </div>
      </div>
      <div class="help-shortcuts-grid">
        <button
          v-for="shortcut in shortcuts"
          :key="shortcut.label"
          class="help-shortcut-card"
          type="button"
          @click="router.push(routeTo(shortcut.route))"
        >
          <span class="help-shortcut-icon"
            ><component :is="shortcut.icon" :size="17" /></span
          ><span
            ><strong>{{ shortcut.label }}</strong
            ><small>{{ shortcut.detail }}</small></span
          ><ArrowRight :size="15" />
        </button>
      </div>
    </section>
  </div>

  <Dialog v-model:open="articleOpen">
    <DialogContent class="help-article-dialog">
      <DialogHeader>
        <div class="help-article-dialog-kicker">
          <span class="help-article-row-icon"
            ><component
              :is="selectedArticle?.icon || BookOpen"
              :size="17" /></span
          ><span
            >{{ selectedArticle?.category }} ·
            {{ selectedArticle?.readTime }}阅读</span
          >
        </div>
        <DialogTitle>{{ selectedArticle?.title }}</DialogTitle>
        <DialogDescription>{{
          selectedArticle?.description
        }}</DialogDescription>
      </DialogHeader>
      <article v-if="selectedArticle" class="help-article-body">
        <p v-for="paragraph in selectedArticle.content" :key="paragraph">
          {{ paragraph }}
        </p>
      </article>
      <div class="help-article-feedback">
        <span>这篇内容对你有帮助吗？</span>
        <div>
          <button
            type="button"
            :class="{ selected: feedbackState === 'helpful' }"
            @click="submitFeedback('helpful')"
          >
            <CheckCircle2 :size="14" />有帮助</button
          ><button
            type="button"
            :class="{ selected: feedbackState === 'not-helpful' }"
            @click="submitFeedback('not-helpful')"
          >
            <CircleHelp :size="14" />需要改进
          </button>
        </div>
      </div>
      <DialogFooter
        ><button
          class="button button-secondary button-sm"
          type="button"
          @click="articleOpen = false"
        >
          关闭
        </button></DialogFooter
      >
    </DialogContent>
  </Dialog>
</template>

<style scoped>
.help-center {
  display: grid;
  gap: 1.375rem;
  padding-bottom: 1.5rem;
}
.help-hero {
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(18rem, 0.75fr);
  min-height: 18rem;
  overflow: hidden;
  border-color: color-mix(in oklab, var(--teal) 18%, var(--workspace-border));
  background: linear-gradient(
    115deg,
    color-mix(in oklab, var(--teal) 8%, var(--surface)),
    var(--surface) 65%
  );
}
.help-hero-copy {
  display: flex;
  flex-direction: column;
  justify-content: center;
  min-width: 0;
  padding: 2.25rem 2.5rem;
}
.help-hero-kicker {
  display: inline-flex;
  align-items: center;
  gap: 0.4375rem;
  width: fit-content;
  color: var(--teal-dark);
  font-size: 0.75rem;
  font-weight: 750;
}
.help-hero-copy h2 {
  max-width: 34rem;
  margin: 0.875rem 0 0;
  color: var(--workspace-text);
  font-size: clamp(1.5rem, 2.8vw, 2.25rem);
  letter-spacing: -0.055em;
  line-height: 1.12;
}
.help-hero-copy p {
  margin: 0.6875rem 0 0;
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.help-search {
  display: flex;
  align-items: center;
  gap: 0.5625rem;
  max-width: 38rem;
  margin-top: 1.5rem;
  padding: 0.25rem 0.4375rem 0.25rem 0.8125rem;
  border: 0.0625rem solid
    color-mix(in oklab, var(--teal) 22%, var(--workspace-border));
  border-radius: 0.625rem;
  background: var(--surface);
  box-shadow: 0 0.5rem 1.5rem rgb(16 93 85 / 7%);
  color: var(--teal-dark);
}
.help-search:focus-within {
  border-color: var(--teal);
  box-shadow: 0 0 0 0.1875rem color-mix(in oklab, var(--teal) 13%, transparent);
}
.help-search input {
  min-width: 0;
  flex: 1;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--workspace-text);
  font: inherit;
  font-size: 0.8125rem;
}
.help-search input::placeholder {
  color: var(--workspace-subtle);
}
.help-search kbd {
  padding: 0.25rem 0.375rem;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.3125rem;
  background: var(--surface-soft);
  color: var(--workspace-subtle);
  font-size: 0.75rem;
}
.help-search-suggestions {
  display: flex;
  align-items: center;
  gap: 0.625rem;
  margin-top: 0.625rem;
  color: var(--workspace-subtle);
  font-size: 0.75rem;
}
.help-search-suggestions button {
  border: 0;
  padding: 0;
  background: none;
  color: var(--teal-dark);
  font: inherit;
  cursor: pointer;
}
.help-search-suggestions button:hover {
  text-decoration: underline;
}
.help-hero-visual {
  position: relative;
  min-height: 18rem;
  overflow: hidden;
  background: radial-gradient(
    circle at 50% 50%,
    color-mix(in oklab, var(--teal) 15%, transparent),
    transparent 58%
  );
}
.help-orbit {
  position: absolute;
  border: 0.0625rem solid color-mix(in oklab, var(--teal) 20%, transparent);
  border-radius: 50%;
}
.help-orbit-one {
  inset: 13% 13%;
  transform: rotate(-18deg) scaleY(0.68);
}
.help-orbit-two {
  inset: 22% 3%;
  transform: rotate(36deg) scaleY(0.48);
}
.help-hero-icon {
  position: absolute;
  top: 50%;
  left: 50%;
  display: grid;
  width: 4.25rem;
  height: 4.25rem;
  place-items: center;
  border: 0.0625rem solid
    color-mix(in oklab, var(--teal) 30%, var(--workspace-border));
  border-radius: 1.25rem;
  background: color-mix(in oklab, var(--teal) 16%, var(--surface));
  color: var(--teal-dark);
  box-shadow: 0 1rem 2.5rem rgb(14 121 109 / 16%);
  transform: translate(-50%, -50%);
}
.help-hero-chip {
  position: absolute;
  display: inline-flex;
  align-items: center;
  gap: 0.3125rem;
  padding: 0.4375rem 0.5625rem;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.5rem;
  background: color-mix(in oklab, var(--surface) 90%, transparent);
  box-shadow: 0 0.375rem 1rem rgb(16 61 58 / 8%);
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.help-hero-chip svg {
  color: var(--teal);
}
.chip-top {
  top: 19%;
  left: 17%;
}
.chip-right {
  top: 36%;
  right: 9%;
}
.chip-bottom {
  right: 22%;
  bottom: 18%;
}
.help-section-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}
.help-section-heading h2 {
  margin: 0.3rem 0 0;
  color: var(--workspace-text);
  font-size: 0.9375rem;
  letter-spacing: -0.025em;
}
.help-section-heading p {
  margin: 0.3125rem 0 0;
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.section-kicker {
  color: var(--teal-dark);
  font-size: 0.75rem;
  font-weight: 800;
  letter-spacing: 0.14em;
}
.help-result-count {
  flex: 0 0 auto;
  color: var(--workspace-subtle);
  font-size: 0.75rem;
}
.help-featured-section,
.help-shortcuts-section {
  display: grid;
  gap: 0.8125rem;
}
.help-featured-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.8125rem;
}
.help-featured-card {
  position: relative;
  display: grid;
  justify-items: start;
  gap: 0.4375rem;
  min-width: 0;
  min-height: 10.25rem;
  padding: 1.125rem;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.75rem;
  background: var(--surface);
  color: inherit;
  text-align: left;
  cursor: pointer;
  transition:
    border-color 0.18s ease,
    transform 0.18s ease,
    box-shadow 0.18s ease;
}
.help-featured-card:hover {
  border-color: color-mix(in oklab, var(--teal) 42%, var(--workspace-border));
  box-shadow: 0 0.5rem 1.25rem rgb(16 78 73 / 7%);
  transform: translateY(-0.125rem);
}
.help-card-index {
  position: absolute;
  top: 1rem;
  right: 1.125rem;
  color: var(--workspace-subtle);
  font:
    700 0.75rem ui-monospace,
    monospace;
  letter-spacing: 0.12em;
}
.help-card-icon,
.help-article-row-icon,
.help-shortcut-icon {
  display: grid;
  place-items: center;
  width: 2rem;
  height: 2rem;
  border-radius: 0.5625rem;
  background: color-mix(in oklab, var(--teal) 12%, var(--surface));
  color: var(--teal-dark);
}
.help-featured-card strong {
  margin-top: 0.25rem;
  color: var(--workspace-text);
  font-size: 0.75rem;
}
.help-featured-card > span:not(.help-card-index):not(.help-card-icon) {
  color: var(--workspace-muted);
  font-size: 0.75rem;
  line-height: 1.6;
}
.help-featured-card small {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  margin-top: auto;
  color: var(--teal-dark);
  font-size: 0.75rem;
}
.help-content-layout {
  display: grid;
  grid-template-columns: 14rem minmax(0, 1fr);
  gap: 1rem;
  align-items: start;
}
.help-category-panel {
  position: sticky;
  top: 1rem;
  padding: 0.875rem;
}
.help-category-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.25rem 0.3125rem 0.75rem;
  border-bottom: 0.0625rem solid var(--workspace-divider);
  color: var(--workspace-text);
  font-size: 0.8125rem;
  font-weight: 700;
}
.help-category-heading svg {
  color: var(--teal);
}
.help-category-list {
  display: grid;
  gap: 0.1875rem;
  padding-top: 0.625rem;
}
.help-category-list button {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  min-height: 2.25rem;
  padding: 0 0.5625rem;
  border: 0;
  border-radius: 0.4375rem;
  background: transparent;
  color: var(--workspace-muted);
  font: inherit;
  font-size: 0.75rem;
  text-align: left;
  cursor: pointer;
}
.help-category-list button:hover {
  background: var(--surface-soft);
  color: var(--workspace-text);
}
.help-category-list button.active {
  background: color-mix(in oklab, var(--teal) 12%, var(--surface));
  color: var(--teal-dark);
  font-weight: 700;
}
.help-category-list button span {
  min-width: 0;
  flex: 1;
}
.help-category-list button small {
  color: var(--workspace-subtle);
  font-size: 0.75rem;
}
.help-category-list button.active small {
  color: var(--teal-dark);
}
.help-category-note {
  display: flex;
  gap: 0.4375rem;
  margin-top: 1rem;
  padding: 0.625rem;
  border-radius: 0.5rem;
  background: color-mix(in oklab, var(--teal) 7%, var(--surface));
  color: var(--workspace-muted);
  font-size: 0.75rem;
  line-height: 1.5;
}
.help-category-note svg {
  flex: 0 0 auto;
  color: var(--teal);
}
.help-main-column {
  display: grid;
  gap: 1rem;
  min-width: 0;
}
.help-articles-panel,
.help-faq-panel {
  overflow: hidden;
}
.help-articles-heading {
  padding: 1.25rem 1.25rem 0.875rem;
  border-bottom: 0.0625rem solid var(--workspace-divider);
}
.help-article-list {
  display: grid;
  padding: 0.25rem 1.25rem 0.75rem;
}
.help-article-row {
  display: flex;
  align-items: center;
  gap: 0.6875rem;
  padding: 0.875rem 0;
  border: 0;
  border-bottom: 0.0625rem solid var(--workspace-divider);
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
}
.help-article-row:last-child {
  border-bottom: 0;
}
.help-article-row:hover > .help-article-row-icon {
  background: color-mix(in oklab, var(--teal) 20%, var(--surface));
}
.help-article-row > svg {
  flex: 0 0 auto;
  color: var(--workspace-subtle);
}
.help-article-row-copy {
  display: grid;
  min-width: 0;
  flex: 1;
  gap: 0.1875rem;
}
.help-article-row-copy strong,
.help-article-row-copy small,
.help-article-row-copy em {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.help-article-row-copy strong {
  color: var(--workspace-text);
  font-size: 0.8125rem;
}
.help-article-row-copy small {
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.help-article-row-copy em {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  margin-top: 0.125rem;
  color: var(--workspace-subtle);
  font-size: 0.75rem;
  font-style: normal;
}
.help-article-row-copy em i {
  width: 0.1875rem;
  height: 0.1875rem;
  border-radius: 50%;
  background: var(--workspace-subtle);
}
.help-article-row-copy em span {
  color: var(--teal-dark);
}
.help-no-results {
  display: grid;
  justify-items: center;
  gap: 0.4375rem;
  padding: 3rem 1rem;
  color: var(--workspace-muted);
  text-align: center;
}
.help-no-results svg {
  color: var(--teal);
}
.help-no-results strong {
  color: var(--workspace-text);
  font-size: 0.8125rem;
}
.help-no-results span {
  font-size: 0.75rem;
}
.help-no-results .button {
  margin-top: 0.375rem;
}
.help-faq-panel .help-section-heading {
  padding: 1.25rem 1.25rem 0.875rem;
  border-bottom: 0.0625rem solid var(--workspace-divider);
}
.help-heading-icon {
  color: var(--teal);
}
.help-faq-list {
  padding: 0.25rem 1.25rem 0.75rem;
}
.help-faq-item {
  border-bottom: 0.0625rem solid var(--workspace-divider);
}
.help-faq-item:last-child {
  border-bottom: 0;
}
.help-faq-item button {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  width: 100%;
  padding: 0.875rem 0;
  border: 0;
  background: none;
  color: var(--workspace-text);
  font: inherit;
  font-size: 0.8125rem;
  text-align: left;
  cursor: pointer;
}
.help-faq-item button svg {
  flex: 0 0 auto;
  color: var(--workspace-subtle);
  transition: transform 0.18s ease;
}
.help-faq-item.open button svg {
  color: var(--teal);
  transform: rotate(180deg);
}
.help-faq-item p {
  max-width: 48rem;
  margin: -0.25rem 2rem 0.875rem 0;
  color: var(--workspace-muted);
  font-size: 0.75rem;
  line-height: 1.7;
}
.help-shortcuts-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.75rem;
}
.help-shortcut-card {
  display: flex;
  align-items: center;
  gap: 0.5625rem;
  min-width: 0;
  padding: 0.75rem;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.625rem;
  background: var(--surface);
  color: inherit;
  text-align: left;
  cursor: pointer;
}
.help-shortcut-card:hover {
  border-color: color-mix(in oklab, var(--teal) 38%, var(--workspace-border));
  background: color-mix(in oklab, var(--teal) 4%, var(--surface));
}
.help-shortcut-card > span:nth-child(2) {
  display: grid;
  min-width: 0;
  flex: 1;
  gap: 0.1875rem;
}
.help-shortcut-card strong,
.help-shortcut-card small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.help-shortcut-card strong {
  color: var(--workspace-text);
  font-size: 0.75rem;
}
.help-shortcut-card small {
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.help-shortcut-card > svg {
  flex: 0 0 auto;
  color: var(--workspace-subtle);
}
.help-contact-panel {
  display: flex;
  align-items: center;
  gap: 0.8125rem;
  padding: 1rem 1.125rem;
  background: linear-gradient(
    105deg,
    color-mix(in oklab, var(--teal) 9%, var(--surface)),
    var(--surface)
  );
}
.help-contact-icon {
  display: grid;
  width: 2.5rem;
  height: 2.5rem;
  flex: 0 0 auto;
  place-items: center;
  border-radius: 0.75rem;
  background: color-mix(in oklab, var(--teal) 16%, var(--surface));
  color: var(--teal-dark);
}
.help-contact-panel > div:nth-child(2) {
  min-width: 0;
  flex: 1;
}
.help-contact-panel h2 {
  margin: 0.25rem 0 0;
  color: var(--workspace-text);
  font-size: 0.8125rem;
}
.help-contact-panel p {
  margin: 0.25rem 0 0;
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.help-contact-panel a {
  flex: 0 0 auto;
  text-decoration: none;
}
.help-article-dialog {
  width: min(38rem, calc(100vw - 2rem));
  max-height: min(42rem, calc(100vh - 2rem));
  overflow: auto;
}
.help-article-dialog-kicker {
  display: flex;
  align-items: center;
  gap: 0.5625rem;
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.help-article-dialog .help-article-row-icon {
  width: 1.875rem;
  height: 1.875rem;
}
.help-article-body {
  display: grid;
  gap: 0.875rem;
  color: var(--workspace-muted);
  font-size: 0.8125rem;
  line-height: 1.75;
}
.help-article-body p {
  margin: 0;
}
.help-article-feedback {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding-top: 0.875rem;
  border-top: 0.0625rem solid var(--workspace-divider);
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.help-article-feedback > div {
  display: flex;
  gap: 0.375rem;
}
.help-article-feedback button {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.375rem 0.5rem;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.375rem;
  background: var(--surface);
  color: var(--workspace-muted);
  font: inherit;
  cursor: pointer;
}
.help-article-feedback button:hover,
.help-article-feedback button.selected {
  border-color: color-mix(in oklab, var(--teal) 42%, var(--workspace-border));
  background: color-mix(in oklab, var(--teal) 10%, var(--surface));
  color: var(--teal-dark);
}
@media (max-width: 68.75rem) {
  .help-hero {
    grid-template-columns: 1fr;
  }
  .help-hero-visual {
    display: none;
  }
  .help-featured-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
  .help-shortcuts-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 47.5rem) {
  .help-center {
    gap: 1rem;
  }
  .help-hero-copy {
    padding: 1.5rem 1.125rem;
  }
  .help-hero-copy h2 {
    font-size: 1.5rem;
  }
  .help-search {
    margin-top: 1.125rem;
  }
  .help-search kbd {
    display: none;
  }
  .help-featured-grid {
    grid-template-columns: 1fr;
  }
  .help-featured-card {
    min-height: 8.5rem;
  }
  .help-content-layout {
    grid-template-columns: 1fr;
  }
  .help-category-panel {
    position: static;
  }
  .help-category-list {
    display: flex;
    overflow-x: auto;
    padding-bottom: 0.125rem;
  }
  .help-category-list button {
    flex: 0 0 auto;
  }
  .help-category-note {
    display: none;
  }
  .help-articles-heading,
  .help-faq-panel .help-section-heading {
    padding-inline: 1rem;
  }
  .help-article-list,
  .help-faq-list {
    padding-inline: 1rem;
  }
  .help-contact-panel {
    align-items: flex-start;
    flex-wrap: wrap;
  }
  .help-contact-panel a {
    margin-left: 3.3125rem;
  }
  .help-article-feedback {
    align-items: flex-start;
    flex-direction: column;
  }
}
@media (max-width: 30rem) {
  .help-search-suggestions {
    gap: 0.4375rem;
  }
  .help-search-suggestions span {
    display: none;
  }
  .help-shortcuts-grid {
    grid-template-columns: 1fr;
  }
  .help-contact-panel a {
    margin-left: 0;
  }
  .help-contact-panel p {
    line-height: 1.5;
  }
}
.help-search-clear {
  display: inline-grid;
  width: 1.75rem;
  height: 1.75rem;
  flex: 0 0 auto;
  place-items: center;
  border: 0;
  border-radius: 0.375rem;
  background: var(--surface-soft);
  color: var(--workspace-muted);
  cursor: pointer;
}
.help-search-clear:hover {
  background: color-mix(in oklab, var(--teal) 12%, var(--surface));
  color: var(--teal-dark);
}
</style>
