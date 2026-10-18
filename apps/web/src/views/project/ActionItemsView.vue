<script setup lang="ts">
import {computed,ref,watch} from "vue";
import {useLocalStorage} from "@vueuse/core";
import {ArrowRight,CheckCircle2,ChevronDown,ClipboardCheck,FileText,LayoutGrid,List,Plus,RefreshCw,Search,ShieldCheck,X} from "@lucide/vue";
import PageHeader from "@/components/common/PageHeader.vue";
import ProjectWorkflow from "@/components/project/ProjectWorkflow.vue";
import ActionTaskCard from "@/components/project/ActionTaskCard.vue";
import ActionTaskPanel from "@/components/project/ActionTaskPanel.vue";
import ReportActionImportDialog from "@/components/project/ReportActionImportDialog.vue";
import {Dialog,DialogContent,DialogDescription,DialogFooter,DialogHeader,DialogTitle} from "@/components/ui/dialog";
import {Field,FieldGroup,FieldLabel} from "@/components/ui/field";
import {Alert,AlertDescription,AlertTitle} from "@/components/ui/alert";
import {Badge} from "@/components/ui/badge";
import {Button} from "@/components/ui/button";
import {Input} from "@/components/ui/input";
import {Tabs,TabsContent,TabsList,TabsTrigger} from "@/components/ui/tabs";
import {useActionWorkflow} from "@/composables/useActionWorkflow";
import {actionBoardBucket,isActionVerified} from "@/utils/actionWorkflow";

const workflow=useActionWorkflow();
const {workspaceId,projectId,items,searchQuery,filterStatus,filterPriority,reportFilter,sourceReports,itemsLoading,itemsError,canManage,saving,
 filteredActionItems,pendingCount,completedCount,statusColumns,actionItemStatusFilters,filterLabelMap,priorityOptions,activeSource,
 loadActionItems,openCreateDialog,openDetailDialog,advanceItem,goSource,returnToReview}=workflow;
const mobile=window.matchMedia("(max-width:760px)").matches;
const viewMode=useLocalStorage<string>(mobile?"shinkou-action-mobile-view":"shinkou-action-desktop-view",mobile?"list":"board");
const importOpen=ref(false),reportPickerOpen=ref(false),importReportId=ref(""),showWorkflow=ref(false),completedExpanded=ref<boolean|null>(null);
if(!["board","list"].includes(viewMode.value))viewMode.value=mobile?"list":"board";
const scopeItems=computed(()=>items.filter(item=>!reportFilter.value||String(item.sourceReportId||"")===reportFilter.value));
const countFor=(bucket:string)=>scopeItems.value.filter(item=>actionBoardBucket(item)===bucket).length;
const releasePending=computed(()=>scopeItems.value.filter(item=>item.blocksRelease!==false&&!isActionVerified(item)).length);
const progress=computed(()=>scopeItems.value.length?Math.round(completedCount.value/scopeItems.value.length*100):0);
const activeFilters=computed(()=>!!searchQuery.value.trim()||filterStatus.value!=="全部"||filterPriority.value!=="全部");
const groups=computed(()=>statusColumns.slice(0,3).map(column=>({...column,items:filteredActionItems.value.filter(item=>actionBoardBucket(item)===column.value)})).filter(column=>filterStatus.value==="全部"||column.items.length));
const openTasks=computed(()=>filteredActionItems.value.filter(item=>!isActionVerified(item)));
const closedTasks=computed(()=>filteredActionItems.value.filter(isActionVerified));
const showClosed=computed(()=>completedExpanded.value??(filterStatus.value==="done"||!openTasks.value.length));
watch([filterStatus,reportFilter],()=>{completedExpanded.value=null;});
const memberNote=computed(()=>items.some(item=>item.canEdit)?"你可以处理分派给自己的任务；分派和验收由项目管理者负责。":"你可以查看任务与验收记录；任务分派和验收由项目管理者负责。");
function resetFilters(){searchQuery.value="";filterStatus.value="全部";filterPriority.value="全部";}
function openImport(){if(reportFilter.value&&activeSource.value)importOpen.value=true;else{importReportId.value="";reportPickerOpen.value=true;}}
function chooseImportReport(){if(!importReportId.value)return;reportFilter.value=importReportId.value;reportPickerOpen.value=false;importOpen.value=true;}
function imported(id:number|string){reportFilter.value=String(id);void loadActionItems();}
</script>

<template>
 <div class="actions-page">
  <PageHeader eyebrow="交付" title="行动项" subtitle="分派、执行与验收">
   <template #action><Button aria-label="新建行动项" :disabled="!canManage||itemsLoading" @click="openCreateDialog"><Plus data-icon="inline-start"/><span class="create-label-wide">新建行动项</span><span class="create-label-small">新建</span></Button></template>
  </PageHeader>

  <section class="scope-bar" aria-label="任务范围与交付入口">
   <Field class="scope-field"><FieldLabel for="action-filter-report" class="sr-only">筛选来源报告</FieldLabel><FileText :size="16"/><select id="action-filter-report" v-model="reportFilter" class="action-select" :title="activeSource?.title||'全部来源报告'"><option value="">项目全部行动项</option><option v-for="report in sourceReports" :key="report.id" :value="String(report.id)">{{report.title}}</option></select></Field>
   <div class="scope-actions"><Button v-if="canManage" variant="outline" size="sm" :disabled="itemsLoading||!sourceReports.length" @click="openImport">从报告导入任务</Button><Button v-if="reportFilter" variant="outline" size="sm" @click="returnToReview">返回报告审查<ArrowRight data-icon="inline-end"/></Button><Button variant="ghost" size="sm" :aria-expanded="showWorkflow" @click="showWorkflow=!showWorkflow">流程说明<ChevronDown data-icon="inline-end"/></Button></div>
  </section>
  <ProjectWorkflow v-if="showWorkflow"/>

  <div class="task-progress-strip">
   <div class="progress-counts"><span>待处理 <strong>{{countFor('todo')}}</strong></span><span>进行中 <strong>{{countFor('in-progress')}}</strong></span><span>待验收 <strong>{{countFor('pending-acceptance')}}</strong></span><span>已验收 <strong>{{completedCount}}</strong></span></div>
   <div class="progress-completion"><span>{{completedCount}} / {{scopeItems.length}} 已验收</span><div class="completion-track" role="progressbar" aria-label="任务验收进度" :aria-valuenow="progress" aria-valuemin="0" aria-valuemax="100"><span :style="{width:progress+'%'}"/></div></div>
  </div>
  <p v-if="reportFilter&&releasePending" class="release-note"><ShieldCheck :size="14"/>{{releasePending}} 项发布前置任务尚未验收，关闭后可返回审查。</p>
  <p v-else-if="reportFilter&&scopeItems.length" class="release-note"><CheckCircle2 :size="14"/>当前已建立的前置任务已验收，请更新报告后重新审查签署。</p>
  <p v-if="!canManage&&!itemsLoading" class="member-note">{{memberNote}}</p>
  <Alert v-if="itemsError" variant="destructive"><AlertTitle>行动项读取失败</AlertTitle><AlertDescription>{{itemsError}}<Button variant="outline" size="sm" @click="loadActionItems">重新加载</Button></AlertDescription></Alert>

  <Tabs v-model="viewMode" class="task-workspace">
   <div class="action-toolbar">
    <Field class="search-field"><FieldLabel for="action-search" class="sr-only">搜索行动项</FieldLabel><Search :size="16"/><Input id="action-search" v-model="searchQuery" type="search" placeholder="搜索任务、负责人或验收要求"/></Field>
    <FieldGroup class="filter-fields"><Field><FieldLabel for="action-filter-status" class="sr-only">筛选行动项状态</FieldLabel><select id="action-filter-status" v-model="filterStatus" class="action-select"><option v-for="filter in actionItemStatusFilters" :key="filter" :value="filter">{{filterLabelMap[filter]}}</option></select></Field><Field><FieldLabel for="action-filter-priority" class="sr-only">筛选行动项优先级</FieldLabel><select id="action-filter-priority" v-model="filterPriority" class="action-select"><option v-for="priority in priorityOptions" :key="priority" :value="priority">{{priority==='全部'?'全部优先级':priority+'优先级'}}</option></select></Field></FieldGroup>
    <TabsList aria-label="任务展示方式"><TabsTrigger value="board"><LayoutGrid/>看板</TabsTrigger><TabsTrigger value="list"><List/>列表</TabsTrigger></TabsList>
   </div>
   <div class="task-view-heading"><span>{{filteredActionItems.length}} 项任务<span v-if="activeFilters">符合筛选</span></span><Button v-if="activeFilters" variant="ghost" size="sm" @click="resetFilters"><X data-icon="inline-start"/>清除筛选</Button></div>

   <div v-if="itemsLoading" class="task-loading" role="status"><RefreshCw class="is-spinning" :size="20"/>正在读取任务与验收记录…</div>
   <section v-else-if="!itemsError&&!filteredActionItems.length" class="task-empty">
    <ClipboardCheck :size="30"/><h2>{{activeFilters?'没有找到匹配的行动项':reportFilter?'该报告尚未建立行动项':'开始落实下一步行动'}}</h2><p>{{activeFilters?'调整关键词或清除筛选，查看其他任务。':'从报告导入任务，或手工建立行动项。'}}</p>
    <div><Button v-if="activeFilters" variant="outline" @click="resetFilters">清除筛选</Button><template v-else-if="canManage"><Button v-if="sourceReports.length" variant="outline" @click="openImport">从报告建立任务</Button><Button @click="openCreateDialog">手工建立行动项</Button></template></div>
   </section>

   <template v-else-if="!itemsError&&!itemsLoading">
    <TabsContent value="board" class="board-panel">
     <section v-if="openTasks.length" class="action-board" :class="{'single-group':filterStatus!=='全部'}" aria-label="执行任务看板">
      <article v-for="column in groups" :key="column.value" class="action-column" :data-status="column.value">
       <header class="action-column-header"><div><h2><component :is="column.icon" :size="16"/>{{column.label}}<Badge variant="secondary">{{column.items.length}}</Badge></h2><p>{{column.detail}}<span v-if="column.value==='todo'"> · 退回的任务也在这里</span></p></div><Button v-if="column.value==='todo'&&canManage" variant="ghost" size="icon-sm" aria-label="新建待处理任务" @click="openCreateDialog"><Plus/></Button></header>
       <div class="action-card-list"><ActionTaskCard v-for="item in column.items" :key="item.id" :item="item" :saving="saving" :show-source="!reportFilter" @open="openDetailDialog" @advance="advanceItem" @source="goSource"/><p v-if="!column.items.length" class="empty-column">暂无{{column.label}}任务</p></div>
      </article>
     </section>
     <section v-if="closedTasks.length" class="completed-section"><button class="completed-heading" type="button" :aria-expanded="showClosed" @click="completedExpanded=!showClosed"><span><CheckCircle2 :size="16"/>已验收 <Badge variant="secondary">{{closedTasks.length}}</Badge></span><span>{{showClosed?'收起记录':'查看验收记录'}}<ChevronDown :size="14" :class="{'is-expanded':showClosed}"/></span></button><div v-if="showClosed" class="completed-grid"><ActionTaskCard v-for="item in closedTasks" :key="item.id" :item="item" :saving="saving" :show-source="!reportFilter" @open="openDetailDialog" @advance="advanceItem" @source="goSource"/></div></section>
    </TabsContent>
    <TabsContent value="list" class="list-panel"><div class="task-list-legend"><span>任务与优先级</span><span>状态 · 负责人 · 截止日期</span><span>操作</span></div><div class="action-list"><ActionTaskCard v-for="item in filteredActionItems" :key="item.id" :item="item" view="list" :saving="saving" :show-source="!reportFilter" @open="openDetailDialog" @advance="advanceItem" @source="goSource"/></div></TabsContent>
   </template>
  </Tabs>

  <ReportActionImportDialog v-model:open="importOpen" :workspace-id="workspaceId" :project-id="projectId" :report-id="reportFilter||undefined" @imported="imported" @manual="openCreateDialog"/>
  <Dialog v-model:open="reportPickerOpen"><DialogContent><DialogHeader><DialogTitle>选择来源报告</DialogTitle><DialogDescription>选择一份报告，确认任务清单后再导入。</DialogDescription></DialogHeader><FieldGroup><Field><FieldLabel for="import-source-report">来源报告</FieldLabel><select id="import-source-report" v-model="importReportId" class="action-select"><option value="" disabled>请选择报告</option><option v-for="report in sourceReports" :key="report.id" :value="String(report.id)">{{report.title}}</option></select></Field></FieldGroup><DialogFooter><Button variant="outline" @click="reportPickerOpen=false">取消</Button><Button :disabled="!importReportId" @click="chooseImportReport">查看报告任务<ArrowRight data-icon="inline-end"/></Button></DialogFooter></DialogContent></Dialog>
  <ActionTaskPanel :workflow="workflow"/>
 </div>
</template>

<style scoped>
.actions-page{--card:var(--surface);--card-foreground:var(--workspace-text);--background:var(--surface);--foreground:var(--workspace-text);--input:var(--workspace-border);--border:var(--workspace-border);--muted:var(--surface-soft);--muted-foreground:var(--workspace-muted);display:flex;flex-direction:column;gap:.85rem;flex:1 1 0;min-width:0;min-height:0;overflow:auto;padding:.125rem .125rem 1rem;scrollbar-gutter:stable}
.actions-page>*{flex-shrink:0}
.create-label-small{display:none}
@media(max-width:47.5rem){.create-label-wide{display:none}.create-label-small{display:inline}}
.scope-bar{display:flex;align-items:center;justify-content:space-between;gap:1rem;min-width:0}
.scope-field{position:relative;min-width:0;flex:1 1 18rem;max-width:34rem}
.scope-field>svg{position:absolute;left:.6rem;top:50%;translate:0 -50%;width:1rem;height:1rem;color:var(--workspace-muted);pointer-events:none}
.scope-field select{padding-left:2rem}
.scope-actions{display:flex;align-items:center;gap:.4rem;flex-shrink:0}
.action-select{height:2.3rem;min-width:0;width:100%;padding:.35rem .5rem .35rem .65rem;border:1px solid var(--input);border-radius:.5rem;background:var(--background);color:var(--foreground);font:inherit;font-size:.75rem;text-overflow:ellipsis;outline:none}
.action-select:focus-visible{border-color:var(--ring);box-shadow:0 0 0 3px color-mix(in oklab,var(--ring) 25%,transparent)}
.task-progress-strip{display:flex;align-items:center;justify-content:space-between;gap:1rem;padding:.8rem 0;border-bottom:1px solid var(--workspace-border)}
.progress-counts{display:flex;align-items:center;gap:1.3rem;flex-wrap:wrap;font-size:.75rem;color:var(--workspace-muted)}
.progress-counts strong{font-size:.9rem;color:var(--workspace-text);font-variant-numeric:tabular-nums;margin-left:.3rem}
.progress-completion{display:flex;align-items:center;gap:.7rem;color:var(--workspace-subtle);font-size:.72rem;white-space:nowrap}
.completion-track{height:.3rem;width:6rem;border-radius:1rem;background:var(--surface-soft);overflow:hidden}
.completion-track>span{display:block;height:100%;background:var(--teal)}
.release-note,.member-note{display:flex;align-items:center;gap:.4rem;font-size:.72rem;color:var(--workspace-muted);margin:0;line-height:1.7}
.release-note svg{flex-shrink:0}
.task-workspace{min-width:0;gap:.65rem}
.action-toolbar{display:grid;grid-template-columns:minmax(12rem,1fr) auto auto;align-items:center;gap:.65rem}
.search-field{position:relative;display:block;min-width:0}
.search-field>svg{position:absolute;top:50%;left:.65rem;width:1rem;height:1rem;translate:0 -50%;color:var(--workspace-muted);pointer-events:none}
.search-field :deep(input){padding-left:2rem;height:2.3rem}
.filter-fields{display:grid;grid-template-columns:8rem 8rem;gap:.5rem;min-width:0}
.filter-fields :deep([data-slot=field]){min-width:0}
.action-toolbar :deep([role=tab]){gap:.3rem}
.task-view-heading{display:flex;align-items:center;justify-content:space-between;min-height:1.7rem;color:var(--workspace-subtle);font-size:.72rem}
.board-panel,.list-panel{min-width:0}
.action-board{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1rem;min-width:0;max-width:100%;overflow:visible;align-items:start}
.action-column{min-width:0;border:1px solid var(--workspace-border);border-radius:.75rem;background:var(--surface-soft);overflow:hidden}
.action-column-header{display:flex;align-items:flex-start;justify-content:space-between;gap:.5rem;padding:1rem .85rem .8rem;border-bottom:1px solid var(--workspace-border)}
.action-column-header h2{display:flex;align-items:center;gap:.45rem;font-size:.85rem;font-weight:600;margin:0}
.action-column-header p{color:var(--workspace-subtle);font-size:.68rem;line-height:1.7;margin:.4rem 0 0}
.action-card-list{display:flex;flex-direction:column;gap:.75rem;padding:.85rem;min-width:0}
.empty-column{font-size:.75rem;color:var(--workspace-subtle);text-align:center;margin:1.5rem 0}
.single-group{grid-template-columns:1fr}
.single-group .action-card-list{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,19rem),1fr))}
.completed-section{border:1px solid var(--workspace-border);border-radius:.75rem;margin-top:1rem;overflow:hidden}
.completed-heading{display:flex;align-items:center;justify-content:space-between;gap:1rem;width:100%;border:0;background:var(--surface);color:var(--workspace-text);padding:1rem;cursor:pointer;text-align:left}
.completed-heading>span{display:flex;align-items:center;gap:.5rem;font-size:.8rem}
.completed-heading>span:last-child{font-size:.72rem;color:var(--workspace-muted)}
.completed-heading svg.is-expanded{rotate:180deg}
.completed-heading:focus-visible{outline:2px solid var(--ring);outline-offset:-2px}
.completed-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,19rem),1fr));gap:.75rem;padding:1rem;border-top:1px solid var(--workspace-border)}
.task-loading{min-height:12rem;display:flex;align-items:center;justify-content:center;gap:.6rem;color:var(--workspace-muted);font-size:.8rem}
.task-empty{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:.9rem;min-height:15rem;border:1px dashed var(--workspace-border);border-radius:.75rem;padding:1.5rem;text-align:center}
.task-empty h2{font-size:1rem;margin:0}.task-empty p{font-size:.8rem;color:var(--workspace-muted);margin:0}.task-empty>div{display:flex;gap:.6rem;flex-wrap:wrap;justify-content:center}
.task-list-legend{display:grid;grid-template-columns:minmax(13rem,1fr) minmax(20rem,.9fr) auto;gap:.75rem;padding:.65rem 1rem;font-size:.7rem;color:var(--workspace-subtle)}
.task-list-legend>span:last-child{min-width:10rem;text-align:right}
.action-list{border:1px solid var(--workspace-border);border-radius:.75rem;overflow:hidden}
.action-list :deep(.action-card:last-child){border-bottom:0}
@media(max-width:80rem){.scope-bar{align-items:stretch;flex-wrap:wrap}.scope-field{max-width:none}.scope-actions{flex-wrap:wrap}.task-list-legend{grid-template-columns:1fr 1fr}.task-list-legend>span:last-child{display:none}}
@media(max-width:68.75rem){.action-board{grid-template-columns:1fr}.action-card-list{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,17rem),1fr))}.action-column-header{align-items:center}.action-column-header p span{display:none}}
@media(max-width:47.5rem){.actions-page{gap:.65rem;scrollbar-gutter:auto}.scope-bar{gap:.6rem}.scope-field{flex-basis:100%}.scope-actions{width:100%}.scope-actions :deep(button){flex:1;font-size:.68rem}.task-progress-strip{padding:.6rem 0;flex-wrap:wrap;gap:.6rem}.progress-counts{justify-content:space-between;gap:.6rem;width:100%;font-size:.7rem}.progress-counts strong{font-size:.8rem}.progress-completion{width:100%;justify-content:space-between}.completion-track{width:45%}.action-toolbar{grid-template-columns:1fr auto}.search-field{grid-column:1/-1}.filter-fields{grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:.4rem}.action-select{font-size:.72rem}.action-toolbar :deep([role=tab]){font-size:.72rem}.action-board{gap:.8rem}.action-card-list{display:flex}.action-column-header h2{font-size:.8rem}.completed-heading{padding:.85rem}.task-list-legend{display:none}.action-list{border:0;display:flex;flex-direction:column;gap:.75rem;overflow:visible}.action-list :deep(.action-card:last-child){border-bottom:1px solid var(--workspace-border)}}
</style>
