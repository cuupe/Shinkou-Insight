import re

from models.schemas import Evidence

CITATION_PATTERN = re.compile(r"\[(E\d+)]")


def validate_citations(
    answer: str,
    evidences: list[Evidence],
) -> list[str]:

    valid_ids = {evidence.id for evidence in evidences}

    referenced_ids = set(CITATION_PATTERN.findall(answer))

    errors: list[str] = []

    for evidence_id in referenced_ids:

        if evidence_id not in valid_ids:

            errors.append(f"引用不存在: {evidence_id}")

    return errors
