import json
from pathlib import Path

import pytest

from agents.decision_engine import DecisionEngine
from agents.decisions import AgentDecision, AnswerAudit, AnswerRevision, DECISION_PROMPT
from models.llm import ModelTimeoutError, ModelOutputLimitError
from models.schemas import Evidence, ExecuteRunRequest
from test_semantic_agent import ScriptedModel, decision, intent, need, records, runtime_for


def fixture():
    return json.loads((Path(__file__).parent/'fixtures/research_stop_run12.json').read_text(encoding='utf-8'))


def completed_revision(data):
    sources = {item['id']:item['content'] for item in [*data['evidence'],data['additional']]}
    links = {'n1':['E9','E7'],'n2':['E9'],'n3':['E12'],'n4':['E13','E4'],'n5':['E1']}
    claims = [dict(statement=text,basis='material',need_ids=[key],supports=[dict(evidence_id=source,quote=sources[source]) for source in links[key]])
        for key,text in [('n1','样本300，正确276，覆盖288，严重错误3，周活跃15/20。'),
          ('n2','平均检索120秒降至66秒，降低45%。'),('n3','六周含税成本139000元，预算剩余11000元。'),
          ('n4','三项推广前置条件尚未关闭，不能批准对外上线。'),('n5','试点周期2026-08-31至2026-10-11，共42天即6周。')]]
    answer = ('## 验收结论\n\n八项量化门槛在合成资料范围内满足，三项推广前置条件未关闭，不能批准对外上线。[E4][E13]\n\n'
        '| 指标 | 测量与计算 |\n|---|---|\n|样本|300条|\n|准确率|276/300=92%|\n|覆盖率|288/300=96%|\n'
        '|检索耗时降低|(120-66)/120=45%|\n|严重错误率|3/300=1%|\n|周活跃|15/20=75%|\n'
        '|周期|2026-08-31至2026-10-11，42天=6周|\n|六周成本|36000+48000+24000+19000+12000=139000元|\n\n'
        '统计口径和原始测量见资料，周期有项目记录支持。[E8][E9][E7][E1]\n\n'
        '预算剩余150000-139000=11000元，成本不再乘人数或月份。[E12]\n\n'
        '## 推广限制与行动\n\n完成权限撤销传播验收、值班和故障处置演练、新增50条独立样本回归，'
        '留存证据后再复核扩大范围。当前均未关闭，50条不能并入300条已测样本。[E13]')
    return dict(summary='量化指标已核对，三项推广条件待关闭',answer=answer,claims=claims,
        needs=[{'id':key,'status':'covered','evidence_ids':ids} for key,ids in links.items()])


@pytest.mark.asyncio
async def test_run12_planner_sees_all_retrieved_numbers_even_above_optional_history_budget():
    data=fixture();req=ExecuteRunRequest.model_validate(data['request']);runtime=runtime_for(ScriptedModel([]))
    engine=DecisionEngine(runtime,req,await runtime.accept(req),[])
    engine.evidence={item['id']:Evidence.model_validate(item) for item in data['evidence']}
    engine.receipts=data['ledger']
    engine.apply_decision(AgentDecision.model_validate(decision(answer='尚在规划',needs=data['needs'])))
    state=json.loads(engine.bounded_messages(DECISION_PROMPT,engine.snapshot())[-1]['content'].split('\n',1)[1])
    shown={item['id']:item['content'] for item in state['evidence']}
    assert all(shown[item['id']] == item['content'] for item in data['evidence'])
    assert '平均为 120 秒' in shown['E9'] and '平均为 66 秒' in shown['E9']
    assert '139000' in shown['E12'] and '2026-08-31' in shown['E1']
    assert engine.context_metrics[-1]['inputTokenEstimate'] > 16000


@pytest.mark.asyncio
@pytest.mark.parametrize('capacity',[32,1])
async def test_new_chapters_are_not_silently_lost_at_twelve_candidates(capacity):
    data=fixture()
    async def search(**kwargs):return [Evidence.model_validate(item) for item in [*data['evidence'],data['additional']]]
    runtime=runtime_for(ScriptedModel([]),search,max_evidence=capacity)
    req=ExecuteRunRequest.model_validate(data['request']);engine=DecisionEngine(runtime,req,await runtime.accept(req),[])
    engine.apply_decision(AgentDecision.model_validate(decision(answer='待检索',needs=[need()])))
    from agents.decisions import ToolIntent
    receipt=await engine.invoke(ToolIntent.model_validate(intent(query='星桥完整验收资料')))
    if capacity==32:
        assert len(engine.evidence)==13 and '尚未关闭' in engine.evidence['E13'].content
        assert not receipt.get('droppedCandidateCount')
    else:
        assert len(engine.evidence)==1 and receipt['droppedCandidateCount']==12
        assert receipt['result']['evidenceCapacity']==1
        assert '不能据此判定资料不存在' in records(runtime,req.run_id,kind='tool.completed')[-1].payload['detail']


@pytest.mark.asyncio
@pytest.mark.parametrize('mode',['complete','audit_timeout','unsupported'])
async def test_planner_ignoring_final_only_is_forced_to_write_and_audit_actual_known_results(mode):
    data=fixture();req=ExecuteRunRequest.model_validate(data['request'])
    async def search(**kwargs):return [Evidence.model_validate(item) for item in [*data['evidence'],data['additional']]]
    planner=decision('execute',needs=[{**item,'status':'missing','evidenceIds':[]} for item in data['needs']],
        tools=[dict(tool='search_knowledge',purpose='核对项目资料',need_ids=['n1','n2','n3','n4','n5'],query='星桥试点验收')])
    revision=completed_revision(data)
    if mode=='unsupported':
        revision={**revision,'claims':[dict(statement='伪造事实',basis='material',supports=[dict(evidence_id='E999',quote='不存在')])]}
    class Model(ScriptedModel):
        async def structured(self,messages,schema,**kwargs):
            if schema is AnswerAudit and mode=='audit_timeout':raise ModelTimeoutError('review service timeout')
            return await super().structured(messages,schema,**kwargs)
    model=Model([planner]*3+[revision]*2)
    runtime=runtime_for(model,search)
    await runtime.execute(req)
    saved=runtime.repository.get(req.run_id)
    assert len(records(runtime,req.run_id,kind='tool.started'))==1
    assert [schema for schema,_ in model.requests].count(AnswerRevision)>=1
    writer_state=json.loads(next(messages for schema,messages in model.requests if schema is AnswerRevision)[-1]['content'].split('\n',1)[1])
    assert '139000' in next(item for item in writer_state['evidence'] if item['id']=='E12')['content']
    if mode=='complete':
        assert saved.status=='COMPLETED' and saved.review_result['approved']
        report=saved.report
        assert report['outcome']=='COMPLETE' and report['limitations_in_body']
        assert '45%' in report['sections'][0]['content'] and '139000' in report['sections'][0]['content']
        assert '当前资料尚不能支持' not in report['sections'][0]['content']
        completion=records(runtime,req.run_id,kind='run.completed')[0].payload
        assert completion['decisionMetrics']['executionStopReason']=='no_progress'
        assert completion['decisionMetrics']['stopReason'] is None
        assert completion['decisionMetrics']['auditCalls']==1
        assert completion['decisionMetrics']['researchRounds']==3
        assert [schema for schema,_ in model.requests].count(AgentDecision)==3
        assert records(runtime,req.run_id,kind='decision.updated')[-1].payload['decision']['action']=='answer'
    else:
        assert saved.status=='FAILED' and not records(runtime,req.run_id,kind='message.delta')
        error=records(runtime,req.run_id,kind='run.failed')[0].payload['error']
        assert error['code']==('TIMEOUT' if mode=='audit_timeout' else 'ANSWER_VALIDATION')


@pytest.mark.asyncio
async def test_partial_synthesis_keeps_supported_cost_and_states_only_the_actual_remaining_gap():
    data=fixture();req=ExecuteRunRequest.model_validate(data['request'])
    source=next(item for item in data['evidence'] if item['id']=='E12')
    async def search(**kwargs):return [Evidence.model_validate(source)]
    planner=decision('execute',needs=[need('cost'),need('scope')],tools=[intent(key='cost',query='六周成本')])
    revision=dict(summary='成本已核实，推广范围仍缺依据',answer='六周含税成本139000元。[E1]\n\n尚待补充：推广范围依据。',
        claims=[dict(statement='六周成本139000元',basis='material',need_ids=['cost'],supports=[dict(evidence_id='E1',quote=source['content'])])],
        needs=[{'id':'cost','status':'covered','evidence_ids':['E1']}])
    runtime=runtime_for(ScriptedModel([planner]*3+[revision]),search)
    await runtime.execute(req)
    saved=runtime.repository.get(req.run_id)
    assert saved.status=='COMPLETED' and not saved.review_result['approved']
    assert saved.report['outcome']=='PARTIAL'
    assert '139000' in saved.report['sections'][0]['content']
    assert saved.report['limitations']==['scope']
    assert saved.report['limitations_in_body']


@pytest.mark.asyncio
async def test_round_limit_reserves_writing_and_audit_even_when_each_search_returns_new_chapters():
    data=fixture();req=ExecuteRunRequest.model_validate(data['request'])
    req.config.max_research_rounds=3
    all_sources=[*data['evidence'],data['additional']]
    queries=[]
    async def search(**kwargs):
        queries.append(kwargs['question'])
        batch=len(queries)
        return [Evidence.model_validate(item) for item in all_sources[(batch-1)*4:batch*4 if batch<3 else None]]
    planners=[decision('execute',needs=data['needs'],tools=[dict(tool='search_knowledge',purpose='补充不同章节',
        need_ids=['n1','n2','n3','n4','n5'],query=f'项目资料第{index}组')]) for index in range(1,4)]
    model=ScriptedModel([*planners,completed_revision(data)])
    runtime=runtime_for(model,search)
    await runtime.execute(req)
    saved=runtime.repository.get(req.run_id)
    assert saved.status=='COMPLETED' and saved.review_result['approved']
    assert len(queries)==3
    assert [schema for schema,_ in model.requests].count(AgentDecision)==3
    assert [schema for schema,_ in model.requests][-2:]==[AnswerRevision,AnswerAudit]
    assert records(runtime,req.run_id,kind='run.completed')[0].payload['decisionMetrics']['executionStopReason']=='budget'


@pytest.mark.asyncio
@pytest.mark.parametrize('recover',[True,False])
async def test_truncated_terminal_json_is_regenerated_once_with_compact_output_and_still_audited(recover):
    data=fixture();req=ExecuteRunRequest.model_validate(data['request'])
    async def search(**kwargs):return [Evidence.model_validate(item) for item in [*data['evidence'],data['additional']]]
    planner=decision('execute',needs=[{**item,'status':'missing','evidenceIds':[]} for item in data['needs']],
        tools=[intent(key='n1',query='试点资料')])
    error=ModelOutputLimitError('response truncated')
    model=ScriptedModel([planner]*3+[error,completed_revision(data) if recover else error])
    runtime=runtime_for(model,search)
    await runtime.execute(req)
    writers=[messages for schema,messages in model.requests if schema is AnswerRevision]
    assert len(writers)==2 and '上次完整JSON达到输出上限' in writers[-1][-1]['content']
    assert len([event for event in records(runtime,req.run_id,kind='node.updated') if event.payload.get('outputCompaction')])==1
    if recover:
        saved=runtime.repository.get(req.run_id)
        assert saved.status=='COMPLETED' and saved.review_result['approved']
        assert [schema for schema,_ in model.requests].count(AnswerAudit)==1
        assert records(runtime,req.run_id,kind='run.completed')[0].payload['decisionMetrics']['usageComplete'] is False
    else:
        assert runtime.repository.get(req.run_id).status=='FAILED'
        assert records(runtime,req.run_id,kind='run.failed')[0].payload['error']['code']=='MODEL_OUTPUT_LIMIT'
        assert not records(runtime,req.run_id,kind='message.delta')
