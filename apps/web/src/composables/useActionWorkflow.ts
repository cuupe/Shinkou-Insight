import {computed,onBeforeUnmount,reactive,ref,watch} from "vue";
import {onBeforeRouteLeave,onBeforeRouteUpdate,useRoute} from "vue-router";
import {CircleDot,Clock3,CheckCircle2,AlertCircle,ClipboardCheck} from "@lucide/vue";
import {useWorkspace} from "@/composables/useWorkspace";
import {actionItemsApi} from "@/api/action-items";
import {getApiErrorMessage} from "@/api/core";
import {reportsApi} from "@/api/reports";
import {workspaceApi} from "@/api/workspace";
import {actionRow,actionCommand,actionMetadataEditable,actionDisplayStatus,isActionVerified,type ActionRow} from "@/utils/actionWorkflow";
import type {ActionItem,Report,WorkspaceMember} from "@/api/types";

export function useActionWorkflow(){
 const {notify,workspaceId,projectId,router,routeTo}=useWorkspace();
 const route=useRoute(),items=reactive<ActionRow[]>([]),searchQuery=ref(""),filterStatus=ref("全部"),filterPriority=ref("全部");
 const reportFilter=ref(String(route.query.reportId||"")),sourceReports=ref<Report[]>([]),owners=ref<WorkspaceMember[]>([]);
 const itemsLoading=ref(false),itemsError=ref(""),canManage=ref(false),itemDialogOpen=ref(false),saving=ref(false);
 const editingItemId=ref<string|null>(null),dialogMode=ref<"edit"|"submit"|"accept"|"detail">("detail");
 const completionDraft=ref(""),acceptanceDraft=ref(""),dialogError=ref(""),discardOpen=ref(false),baseline=ref("");
 let scope=0,discardResolver:((value:boolean)=>void)|null=null;
 const actionForm=reactive({title:"",description:"",acceptanceCriteria:"",ownerId:"",due:"",priority:"中",blocksRelease:true,sourceReportId:"",sourceReviewRunId:""});
 const selectedItem=computed(()=>items.find(item=>item.id===editingItemId.value));
 const dialogTitle=computed(()=>dialogMode.value==="submit"?"提交完成证据":dialogMode.value==="accept"?"验收行动项":dialogMode.value==="edit"?(editingItemId.value?"编辑行动项":"新建行动项"):(selectedItem.value?.title||"行动项详情"));
 const metadataEditable=computed(()=>canManage.value&&dialogMode.value==="edit"&&(!selectedItem.value||actionMetadataEditable(selectedItem.value)));
 const activeSource=computed(()=>sourceReports.value.find(report=>String(report.id)===reportFilter.value));
 const filteredActionItems=computed(()=>items.filter(item=>{
  const query=searchQuery.value.trim().toLowerCase();
  return (!reportFilter.value||String(item.sourceReportId||"")===reportFilter.value)&&
   (filterStatus.value==="全部"||actionDisplayStatus(item)===filterStatus.value)&&(filterPriority.value==="全部"||item.priority===filterPriority.value)&&
   (!query||[item.title,item.description,item.owner,item.due,item.sourceReportTitle,item.acceptanceCriteria].join(" ").toLowerCase().includes(query));
 }));
 const relevant=computed(()=>items.filter(item=>!reportFilter.value||String(item.sourceReportId||"")===reportFilter.value));
 const pendingCount=computed(()=>relevant.value.filter(item=>!isActionVerified(item)).length);
 const inProgressCount=computed(()=>relevant.value.filter(item=>item.status==="in-progress").length);
 const highPriorityCount=computed(()=>relevant.value.filter(item=>item.priority==="高"&&!isActionVerified(item)).length);
 const completedCount=computed(()=>relevant.value.filter(isActionVerified).length);
 const statusColumns=[
  {value:"todo",label:"待处理",detail:"确认要求与负责人",tone:"slate",icon:CircleDot},
  {value:"in-progress",label:"进行中",detail:"执行任务并准备证据",tone:"amber",icon:Clock3},
  {value:"pending-acceptance",label:"待验收",detail:"核对证据与验收标准",tone:"amber",icon:ClipboardCheck},
  {value:"done",label:"已验收",detail:"保留完成与验收记录",tone:"teal",icon:CheckCircle2},
  {value:"rejected",label:"退回修改",detail:"按意见补充后重新提交",tone:"amber",icon:AlertCircle},
 ];
 const actionItemStatusFilters=["全部",...statusColumns.map(column=>column.value)];
 const filterLabelMap:Record<string,string>={全部:"全部状态",...Object.fromEntries(statusColumns.map(column=>[column.value,column.label]))};
 const priorityOptions=["全部","高","中","低"];
 function snapshot(){return dialogMode.value==="edit"?JSON.stringify(actionForm):dialogMode.value==="submit"?completionDraft.value:dialogMode.value==="accept"?acceptanceDraft.value:"";}
 const hasUnsavedChanges=computed(()=>itemDialogOpen.value&&dialogMode.value!=="detail"&&snapshot()!==baseline.value);
 function markClean(){baseline.value=snapshot();dialogError.value="";}
 function allowDiscard(){
  if(!hasUnsavedChanges.value)return Promise.resolve(true);
  if(discardResolver)return Promise.resolve(false);
  discardOpen.value=true;
  return new Promise<boolean>(resolve=>{discardResolver=resolve;});
 }
 function decideDiscard(discard:boolean){
  discardOpen.value=false;
  const resolve=discardResolver;discardResolver=null;resolve?.(discard);
 }
 async function requestTaskClose(){
  if(saving.value)return;
  if(await allowDiscard()){itemDialogOpen.value=false;dialogError.value="";}
 }
 async function backToDetail(){
  if(saving.value)return;
  if(!selectedItem.value){await requestTaskClose();return;}
  if(await allowDiscard()){dialogMode.value="detail";populate(selectedItem.value);markClean();}
 }
 function populate(item:ActionRow){
  editingItemId.value=item.id;
  Object.assign(actionForm,{title:item.title,description:item.description,acceptanceCriteria:item.acceptanceCriteria||"",ownerId:item.ownerId==null?"":String(item.ownerId),due:item.dueAt||"",priority:item.priority,blocksRelease:item.blocksRelease!==false,sourceReportId:String(item.sourceReportId||""),sourceReviewRunId:String(item.sourceReviewRunId||"")});
  completionDraft.value=item.completionEvidence||"";acceptanceDraft.value="";
 }
 async function openCreateDialog(){
  if(!canManage.value)return false;
  if(saving.value||!(await allowDiscard()))return false;
  editingItemId.value=null;dialogMode.value="edit";
  Object.assign(actionForm,{title:"",description:"",acceptanceCriteria:"",ownerId:"",due:"",priority:"中",blocksRelease:true,sourceReportId:reportFilter.value,sourceReviewRunId:""});
  itemDialogOpen.value=true;markClean();return true;
 }
 async function openDetailDialog(item:ActionRow){
  if(saving.value||!(await allowDiscard()))return false;
  populate(item);dialogMode.value="detail";itemDialogOpen.value=true;markClean();return true;
 }
 function editSelectedItem(){
  const item=selectedItem.value;
  if(!item||!actionMetadataEditable(item)||saving.value)return;
  populate(item);dialogMode.value="edit";markClean();
 }
 async function consumePrefill(){
  if(typeof route.query.actionTitle!=="string"||!route.query.actionTitle.trim()||itemsLoading.value)return;
  const opened=await openCreateDialog();
  if(!opened)return;
  actionForm.title=route.query.actionTitle.trim();actionForm.description=String(route.query.actionDescription||"");
  actionForm.sourceReportId=String(route.query.sourceReportId||"");actionForm.sourceReviewRunId=String(route.query.sourceReviewRunId||"");
  actionForm.acceptanceCriteria=actionForm.sourceReviewRunId?"逐项处理来源审查记录的问题，并提交修复和验证证据。":"按来源报告的要求完成，并提交可核对的记录。";
  if(actionForm.sourceReportId)reportFilter.value=actionForm.sourceReportId;
  markClean();
  void router.replace({...routeTo("project-action-items"),query:reportFilter.value?{reportId:reportFilter.value}:{}});
 }
 async function loadActionItems(){
  const current=++scope;itemsLoading.value=true;itemsError.value="";itemDialogOpen.value=false;
  items.splice(0);canManage.value=false;owners.value=[];sourceReports.value=[];
  const workspace=workspaceId.value,project=projectId.value;
  if(!workspace||project<=0){itemsLoading.value=false;return;}
  const [tasks,permission,people,reports]=await Promise.allSettled([actionItemsApi.list(workspace,project),actionItemsApi.permissions(workspace,project),workspaceApi.members(workspace),reportsApi.list(workspace,project)]);
  if(current!==scope)return;
  if(tasks.status==="fulfilled")items.splice(0,items.length,...tasks.value.map(actionRow));
  else itemsError.value=getApiErrorMessage(tasks.reason,"行动项加载失败");
  canManage.value=permission.status==="fulfilled"&&permission.value.canManage;
  owners.value=people.status==="fulfilled"?people.value.filter(person=>!person.status||person.status==="ACTIVE"):[];
  sourceReports.value=reports.status==="fulfilled"?reports.value:[];
  itemsLoading.value=false;void consumePrefill();
 }
 function replaceItem(remote:ActionItem){const row=actionRow(remote),index=items.findIndex(item=>item.id===row.id);if(index<0)items.push(row);else items.splice(index,1,row);return row;}
 async function saveActionItem(){
  if(!metadataEditable.value||saving.value||!actionForm.title.trim()||!actionForm.acceptanceCriteria.trim())return;
  saving.value=true;dialogError.value="";const current=scope;
  try{
   const payload={title:actionForm.title.trim(),description:actionForm.description.trim(),acceptanceCriteria:actionForm.acceptanceCriteria.trim(),
    ownerId:actionForm.ownerId||null,dueAt:actionForm.due||null,priority:actionForm.priority,blocksRelease:actionForm.blocksRelease};
   const remote=editingItemId.value?await actionItemsApi.update(workspaceId.value,projectId.value,editingItemId.value,payload):
    await actionItemsApi.create(workspaceId.value,projectId.value,{...payload,sourceReportId:actionForm.sourceReportId||null,sourceReviewRunId:actionForm.sourceReviewRunId||null});
   if(current===scope){populate(replaceItem(remote));dialogMode.value="detail";markClean();notify("行动项已保存，可在详情中继续处理");}
  }catch(exc){if(current===scope)dialogError.value=getApiErrorMessage(exc,"保存失败");}
  finally{if(current===scope)saving.value=false;}
 }
 async function advanceItem(item:ActionRow){
  const action=actionCommand(item);if(!action||saving.value)return;
  if(action.command==="assign"){if(await openDetailDialog(item))editSelectedItem();return;}
  if(action.command!=="start"){
   if(!(await allowDiscard()))return;
   populate(item);dialogMode.value=action.command as "submit"|"accept";itemDialogOpen.value=true;markClean();return;
  }
  saving.value=true;const current=scope;
  try{const remote=await actionItemsApi.update(workspaceId.value,projectId.value,item.id,{status:"IN_PROGRESS"});if(current===scope){replaceItem(remote);notify("任务已开始处理，完成后请提交证据");}}
  catch(exc){if(current===scope){const message=getApiErrorMessage(exc,"状态更新失败");if(itemDialogOpen.value)dialogError.value=message;else notify(message);}}
  finally{if(current===scope)saving.value=false;}
 }
 async function finishWorkflow(decision?:"ACCEPT"|"RETURN"){
  const item=selectedItem.value;if(!item||saving.value)return;
  if(dialogMode.value==="submit"&&!completionDraft.value.trim())return;
  if(dialogMode.value==="accept"&&!acceptanceDraft.value.trim())return;
  saving.value=true;dialogError.value="";const current=scope;
  try{
   const remote=dialogMode.value==="submit"?await actionItemsApi.submit(workspaceId.value,projectId.value,item.id,completionDraft.value.trim()):
    await actionItemsApi.acceptance(workspaceId.value,projectId.value,item.id,decision||"ACCEPT",acceptanceDraft.value.trim());
   if(current===scope){replaceItem(remote);itemDialogOpen.value=false;notify(remote.status==="DONE"?"已验收，请更新报告并返回审查":remote.status==="REJECTED"?"已退回修改，负责人可继续处理":"已提交，等待项目管理者验收");}
  }catch(exc){if(current===scope)dialogError.value=getApiErrorMessage(exc,"操作失败");}
  finally{if(current===scope)saving.value=false;}
 }
 function goSource(item:ActionRow,review=false){
  if(!item.sourceReportId||saving.value)return;
  void router.push({...routeTo(review?"project-review":"project-reports"),query:{reportId:String(item.sourceReportId),...(review&&item.sourceReviewRunId?{reviewRunId:String(item.sourceReviewRunId)}:{})}});
 }
 function returnToReview(){if(reportFilter.value)void router.push({...routeTo("project-review"),query:{reportId:reportFilter.value}});}
 async function navigationAllowed(){
  if(saving.value){notify("正在保存，请稍后离开");return false;}
  return allowDiscard();
 }
 onBeforeRouteLeave(navigationAllowed);
 onBeforeRouteUpdate((to,from)=>to.params.workspaceId!==from.params.workspaceId||to.params.projectId!==from.params.projectId?navigationAllowed():true);
 watch([workspaceId,projectId],()=>{saving.value=false;void loadActionItems();},{immediate:true});
 watch(()=>route.query.reportId,value=>{reportFilter.value=typeof value==="string"?value:"";});
 watch(()=>route.query.actionTitle,()=>{void consumePrefill();});
 onBeforeUnmount(()=>{scope++;decideDiscard(false);});
 return {workspaceId,projectId,items,searchQuery,filterStatus,filterPriority,reportFilter,sourceReports,owners,itemsLoading,itemsError,canManage,
  itemDialogOpen,editingItemId,dialogMode,dialogTitle,dialogError,metadataEditable,actionForm,selectedItem,completionDraft,acceptanceDraft,saving,
  discardOpen,hasUnsavedChanges,decideDiscard,requestTaskClose,backToDetail,editSelectedItem,
  filteredActionItems,pendingCount,inProgressCount,highPriorityCount,completedCount,statusColumns,actionItemStatusFilters,filterLabelMap,priorityOptions,activeSource,
  loadActionItems,openCreateDialog,openDetailDialog,openEditDialog:openDetailDialog,saveActionItem,advanceItem,finishWorkflow,goSource,returnToReview};
}
export type ActionWorkflow=ReturnType<typeof useActionWorkflow>;
