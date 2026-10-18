export type ReportEditorFields = {
  title: string;
  lead: string;
  summary: string;
  content: string;
  recommendation: string;
  recommendationDetail: string;
};

function text(value: unknown) {
  return typeof value === "string" ? value : "";
}

export function reportTextFields(report: Record<string, unknown>) {
  const fields = {
    lead: text(report.lead),
    summary: text(report.summary),
    recommendation: text(report.recommendation),
    recommendationDetail: text(report.recommendationDetail),
  };
  // The stored Markdown is independent of the short summary. Preserve it
  // exactly so metadata edits cannot silently rebuild or truncate the body.
  const body = [report.content, report.markdownContent]
    .map(text).find(value => value.trim());
  return {
    ...fields,
    content: body ?? [...new Set(Object.values(fields).map(value => value.trim()).filter(Boolean))].join("\n\n"),
  };
}

export function reportUpdatePayload(form: ReportEditorFields) {
  return {
    title: form.title.trim(),
    lead: form.lead.trim(),
    summary: form.summary.trim(),
    content: form.content,
    recommendation: form.recommendation.trim(),
    recommendationDetail: form.recommendationDetail.trim(),
  };
}
