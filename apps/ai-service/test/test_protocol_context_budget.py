import json
from pathlib import Path

import pytest

from agents.context_budget import STATE_PREFIX
from agents.decision_engine import AgentExecutionError, DecisionEngine
from agents.decisions import AgentDecision, AnswerAudit, AnswerRevision
from agents.runtime import _estimate_tokens
from models.schemas import Evidence, ExecuteRunRequest, ModelGenerationConfig
from test_semantic_agent import ScriptedModel, decision, intent, need, records, request, runtime_for


def fixture():
    return json.loads((Path(__file__).parent/'fixtures/research_audit_run11.json').read_text(encoding='utf-8'))


def state_from(messages):
    assert messages[-1]['content'].startswith(STATE_PREFIX)
    return json.loads(messages[-1]['content'][len(STATE_PREFIX):])


def long_report(data):
    by_id = {e['id']:e['content'] for e in data['evidence']}
    body = (
        '# 星桥六周试点验收报告\n\n'
        '本报告仅用于虚构系统验收场景。资料截止日为2026-10-16，模拟测量不代表现实业务结果。[E5][E6]\n\n'
        '## 指标与计算\n\n'
        '| 指标 | 模拟测量与计算 | 判定范围 |\n|---|---|---|\n'
        '| 样本 | 300条去重问题 | 样本量满足300条门槛 |\n'
        '| 准确率 | 276/300=92% | 达到90%门槛 |\n'
        '| 可定位覆盖 | 288/300=96% | 达到95%门槛 |\n'
        '| 检索耗时降低 | (120-66)/120=45% | 达到40%门槛；不能解释为完整业务处理时长 |\n'
        '| 严重错误率 | 3/300=1% | 低于2%；分母为全部300条问题 |\n'
        '| 周活跃 | 15/20=75% | 仅限2026-10-05至2026-10-11观察周 |\n'
        '| 六周成本 | 36000+48000+24000+19000+12000=139000元 | 含税人民币全量合计，低于150000元 |\n\n'
        '以上测量与统计门槛见原文。[E1][E2][E4][E7]\n\n'
        '周期按用户给定的2026-08-31至2026-10-11、首尾计入计算为42天即6周。'
        '这只是输入条件的日期计算；本轮片段没有提供实际起止执行记录，周期验收仍未核验。[U1]\n\n'
        '## 范围、风险与行动\n\n'
        '不能仅凭量化指标达标批准对外上线。A01权限撤销传播回归、A02值班与故障处置演练、'
        'A03新增50条独立样本回归均待处理；截止日期分别为2026-10-20、2026-10-21、2026-10-22。'
        '新增样本不能与已测300条重复，不能把后续计划写成已经完成。[E8][E9]\n\n'
        '后续先补充周期执行记录，再由相应责任角色完成三项行动并提交证据。'
        '本报告没有推断生产QPS、SLA、长期ROI或未来生产成本，也没有批准正式推广。'
        '139000元已经覆盖六周20人试点，不再乘以人数或月份；预算剩余150000-139000=11000元。[E7][E8]\n\n'
        '## 核验原文附录\n\n'
    )
    body += '\n\n'.join(f"### {e['id']} {e['source_name']}\n\n{e['content']}\n\n[{e['id']}]" for e in data['evidence'])
    claims = [dict(statement={
        'E1':'验收门槛与统计口径按XQ-02。', 'E2':'样本300、正确276、覆盖288、严重错误3，平均检索120秒降至66秒。',
        'E4':'指定观察周15/20人活跃，即75%。', 'E7':'六周含税全量成本139000元，预算剩余11000元。',
        'E8':'指标达标不能代替推广前置条件，也不能推测生产QPS或SLA。', 'E9':'A01、A02、A03均待处理。',
    }[key], basis='material', need_ids=['n2'] if key in {'E8','E9'} else ['n3'] if key=='E7' else ['n1'],
        supports=[dict(evidence_id=key,quote=by_id[key])]) for key in ('E1','E2','E4','E7','E8','E9')]
    return decision(resolved_goal='核对星桥试点指标、推广限制与行动', summary='在资料范围内核对，周期仍缺执行证明，三项推广前置行动未关闭。',
        answer=body, claims=claims, needs=data['needs'])


@pytest.mark.asyncio
async def test_run11_sized_report_reaches_audit_and_is_saved_without_losing_verification_material():
    data = fixture()
    final = long_report(data)
    # Same configured model window and source set as the reported failure; the
    # draft is representative because failed unaudited responses are not stored.
    assert len(json.dumps(final,ensure_ascii=False)) > 6671
    async def search(**kwargs):
        return [Evidence.model_validate(item) for item in data['evidence']]
    initial_needs = [{**item,'status':'missing','evidenceIds':[]} for item in data['needs']]
    model = ScriptedModel([
        decision('execute',needs=initial_needs,tools=[dict(tool='search_knowledge',purpose='核对验收资料',
            need_ids=['n1','n2','n3'],query='星桥试点验收资料')]),final,
    ])
    runtime = runtime_for(model,search)
    req = ExecuteRunRequest.model_validate(data['request'])
    await runtime.execute(req)
    saved = runtime.repository.get(req.run_id)
    assert saved.status == 'COMPLETED'
    assert not records(runtime,req.run_id,kind='run.failed')
    audits = [messages for schema,messages in model.requests if schema is AnswerAudit]
    assert len(audits) == 1
    state = state_from(audits[0])
    assert state['answer'] == final['answer']
    assert state['claims'] == [claim.model_dump() for claim in AgentDecision.model_validate(final).claims]
    originals = {e['id']:e['content'] for e in data['evidence']}
    assert all(e['content'] == originals[e['id']] for e in state['evidence'])
    assert '周期验收仍未核验' in saved.report['sections'][0]['content']
    metrics = records(runtime,req.run_id,kind='run.completed')[0].payload['decisionMetrics']['contextBudgets'][-1]
    assert metrics['inputTokenEstimate'] <= metrics['inputTokenLimit'] < metrics['modelContextWindow']-metrics['outputTokenReserve']
    assert metrics['modelContextWindow'] == 128000 and metrics['outputTokenReserve'] == 4096
    assert _estimate_tokens(json.dumps(state,ensure_ascii=False)) > 7370


@pytest.mark.asyncio
@pytest.mark.parametrize('phase',['audit','writing'])
async def test_referenced_tail_after_6000_chars_and_conflicting_qualifier_survive_review_budgeting(phase):
    tail = '费用139000元只覆盖六周试点；生产推广成本未提供。'
    original = '这是模拟资料的完整背景。' * 1000 + '\n' + tail
    runtime = runtime_for(ScriptedModel([]))
    req = request().model_copy(update={'agent_message_id':None})
    engine = DecisionEngine(runtime,req,await runtime.accept(req),[])
    engine.evidence['E1'] = Evidence(id='E1',chunk_id=1,content=original,source_name='完整成本.md')
    engine.stage = 'answer_audit' if phase == 'audit' else 'answer'
    claims = [dict(statement=tail,supports=[dict(evidence_id='E1',quote=tail)])]
    if phase == 'audit':
        payload = {**engine.snapshot(),'answer':tail,'claims':claims}
    else:
        engine.apply_decision(AgentDecision.model_validate(decision(answer='待撰写',
            needs=[need(status='covered',evidence_ids=['E1'])])))
        engine.tool_facts['C1'] = '139000'
        payload = engine.snapshot()
    messages = engine.bounded_messages('核对原文中的适用范围，不得忽略尾部限制。',payload,
        schema=AnswerAudit if phase == 'audit' else None)
    state = state_from(messages)
    assert len(original) > 6000
    assert state['evidence'][0]['content'] == original
    if phase == 'audit':
        assert state['claims'] == claims and state['answer'] == tail
    assert engine.context_metrics[-1]['expandedForRequiredData']


@pytest.mark.asyncio
async def test_history_and_uncited_previews_cannot_evict_answer_claims_or_exact_user_input():
    raw_user = '已确认输入条件。' * 900 + '最终人数为17人。'
    runtime = runtime_for(ScriptedModel([]))
    req = request().model_copy(update={'goal':raw_user})
    history = [{'role':'assistant','content':'较早的参考解释。'*2500} for _ in range(20)]
    engine = DecisionEngine(runtime,req,await runtime.accept(req),history)
    engine.evidence['E1'] = Evidence(id='E1',chunk_id=1,content='无关材料。'*15000,source_name='其他.md')
    payload = {**engine.snapshot(),'draftAnswer':'给定人数17，仍需核对实际执行。',
        'claims':[dict(statement='给定人数17人',supports=[dict(evidence_id='U1',quote='最终人数为17人。')])]}
    before = json.dumps(payload,ensure_ascii=False)
    state = state_from(engine.bounded_messages('只修正草稿。',payload,schema=AnswerRevision))
    assert state['draftAnswer'] == payload['draftAnswer'] and state['claims'] == payload['claims']
    assert state['trustedUserSources'][-1]['content'] == raw_user
    assert state['evidence'][0]['content_truncated'] and len(state['evidence'][0]['content']) < 1000
    assert json.dumps(payload,ensure_ascii=False) == before
    assert engine.context_metrics[-1]['retainedHistoryMessages'] < len(history)


@pytest.mark.asyncio
async def test_genuinely_small_window_fails_at_audit_without_truncating_or_calling_model():
    model = ScriptedModel([])
    runtime = runtime_for(model)
    req = request(generation=ModelGenerationConfig(context_window=4096,max_tokens=1024))
    engine = DecisionEngine(runtime,req,await runtime.accept(req),[])
    answer = '必须完整核对的事实。' * 1200
    draft = AgentDecision.model_validate(decision(answer=answer))
    issues = await engine.audit(draft)
    assert issues and not model.requests
    assert engine.audit_error['code'] == 'CONTEXT_BUDGET'
    assert engine.audit_error['stage'] == 'answer_audit'
    assert '4096' in engine.audit_error['message'] and '可用输入预算' in engine.audit_error['message']
    assert draft.answer == answer
    assert records(runtime,kind='node.failed')[-1].payload['callId'] == 'test:audit:1'
    assert not records(runtime,kind='message.delta')


@pytest.mark.asyncio
async def test_large_instruction_and_schema_are_counted_even_when_state_is_short():
    runtime = runtime_for(ScriptedModel([]))
    req = request(generation=ModelGenerationConfig(context_window=6000,max_tokens=1024))
    engine = DecisionEngine(runtime,req,await runtime.accept(req),[])
    engine.stage = 'answer_revision'
    with pytest.raises(AgentExecutionError) as caught:
        engine.bounded_messages('必须逐项检查。'*1200,{'goal':'短问题','draftAnswer':'短答复'},schema=AnswerRevision)
    assert caught.value.details['code'] == 'CONTEXT_BUDGET' and caught.value.details['stage'] == 'answer_revision'
    assert '6000' in caught.value.details['message']


@pytest.mark.asyncio
async def test_multimodal_history_cannot_bypass_whole_request_budget():
    runtime = runtime_for(ScriptedModel([]))
    req = request(generation=ModelGenerationConfig(context_window=8000,max_tokens=1024))
    history = [{'role':'user','content':[{'type':'text','text':'图像条件。'*10000}]}]
    engine = DecisionEngine(runtime,req,await runtime.accept(req),history)
    with pytest.raises(AgentExecutionError) as caught:
        engine.bounded_messages('核对输入。',{'goal':'图中的问题'},schema=None)
    assert caught.value.details['code'] == 'CONTEXT_BUDGET' and not runtime.model.requests
