"""Frozen, stateless prompt templates for the evaluation-ready runtime."""

import json
from hashlib import sha256

ROLE = "You are an evidence analyst in a controlled multi-agent research experiment."
PROMPT_ID = "evidence-analyst-m1c"
PROMPT_VERSION = "1.4.0"
DOCUMENT_RENDERING_VERSION = "citation-locators-v1"
COMMUNICATION_TASK_V1_2 = "Send all currently supported candidate claims to your neighbor."
COMMUNICATION_TASK = "Produce a fresh StructuredPayload containing all currently supported candidate claims for the next agent."
COMMUNICATION_OUTPUT_REMINDER = """Return the payload object itself, with exactly these four top-level keys:
payload_type, message_status, claims, summary. Do not add a recipient, route, parent,
question, explanation, or any other top-level key. The visible parent-message JSON is
read-only input, not an output template. Do not copy its metadata fields into your payload."""
EMPTY_DOCUMENT_REMINDER = """No documents were assigned to you for this initial read. You have no
evidence to report. Return exactly this JSON object:
{"payload_type":"structured","message_status":"no_new_information","claims":[],"summary":null}
Keep payload_type as "structured". Do not invent a claim, citation, or document."""
SYSTEM_PROMPT = """You are an evidence analyst in a controlled multi-agent research experiment.
Report only candidate factual claims supported by documents assigned to you or messages delivered to you.
Never produce a final answer to the question. Do not invent missing evidence or locators.
Return exactly one StructuredPayload JSON object, not Markdown, with keys payload_type,
message_status, claims, summary.
These are the only four permitted top-level keys. Return the payload object directly;
do not wrap it in another object or add routing, parent-message, or explanatory fields.
payload_type must be "structured". message_status must be either "content" or "no_new_information";
never output the literal text "content|no_new_information".
For "content", claims must be a nonempty array of objects. Each claim needs a nonempty claim_id and
claim_text. For "no_new_information", claims must be []. summary may be null.
source_refs, when present, MUST be an array of JSON OBJECTS, never strings, numbers, titles,
bracketed citations, or arrays of strings. Each source-ref object needs evidence_id, context_ref
(an object with sample_id and context_index), granularity, and reference_origin. For sentence
evidence, use granularity "sentence" and sentence_ids with visible sentence indexes. For an
unsegmented paragraph, use granularity "paragraph" and paragraph_idx 0. Copy the exact
context_ref from a visible assigned document. A document supplies a valid citation template;
when citing another labeled sentence, change its sentence_ids and evidence_id accordingly.
For claims based only on a received parent message, copy its complete source-ref objects and
use reference_origin "inherited_message". A content claim should have at least one valid
source-ref object. If you cannot specify a valid locator, omit that claim; if no claims remain,
return "no_new_information" with claims []. Never invent a citation or add unknown fields."""

SYSTEM_PROMPT_V1_2 = """You are an evidence analyst in a controlled multi-agent research experiment.
Report only candidate factual claims supported by documents assigned to you or messages delivered to you.
Never produce a final answer to the question. Do not invent missing evidence or locators.
Return exactly one StructuredPayload JSON object, not Markdown, with keys payload_type,
message_status, claims, summary.
payload_type must be "structured". message_status must be either "content" or "no_new_information";
never output the literal text "content|no_new_information".
For "content", claims must be a nonempty array of objects. Each claim needs a nonempty claim_id and
claim_text. For "no_new_information", claims must be []. summary may be null.
source_refs, when present, MUST be an array of JSON OBJECTS, never strings, numbers, titles,
bracketed citations, or arrays of strings. Each source-ref object needs evidence_id, context_ref
(an object with sample_id and context_index), granularity, and reference_origin. For sentence
evidence, use granularity "sentence" and sentence_ids with visible sentence indexes. For an
unsegmented paragraph, use granularity "paragraph" and paragraph_idx 0. Copy the exact
context_ref from a visible assigned document. A document supplies a valid citation template;
when citing another labeled sentence, change its sentence_ids and evidence_id accordingly.
For claims based only on a received parent message, copy its complete source-ref objects and
use reference_origin "inherited_message". A content claim should have at least one valid
source-ref object. If you cannot specify a valid locator, omit that claim; if no claims remain,
return "no_new_information" with claims []. Never invent a citation or add unknown fields."""


def system_prompt_for_version(version: str) -> str:
    if version == "1.2.0":
        return SYSTEM_PROMPT_V1_2
    if version in {"1.3.0", PROMPT_VERSION}:
        return SYSTEM_PROMPT
    raise ValueError(f"unsupported prompt replay version: {version}")


def content_hash() -> str:
    material = "\n\x1e\n".join((SYSTEM_PROMPT, DOCUMENT_RENDERING_VERSION,
                                  "Question: {question}\n\nAssigned documents:\n{documents}",
                                  "Question: {question}\n\nTask: {task}\n\nVisible parent messages (canonical JSON):\n{parents}\n\n{output_reminder}",
                                  COMMUNICATION_TASK, COMMUNICATION_OUTPUT_REMINDER,
                                  EMPTY_DOCUMENT_REMINDER))
    return sha256(material.encode("utf-8")).hexdigest()


def initial_user_content(question: str, rendered_documents: str,
                         prompt_version: str = PROMPT_VERSION) -> str:
    content = f"Question: {question}\n\nAssigned documents:\n{rendered_documents}"
    if prompt_version == PROMPT_VERSION and not rendered_documents:
        return f"{content}\n\n{EMPTY_DOCUMENT_REMINDER}"
    if prompt_version in {"1.2.0", "1.3.0"}:
        return content
    if prompt_version == PROMPT_VERSION:
        return content
    raise ValueError(f"unsupported prompt replay version: {prompt_version}")


def communication_user_content(question: str, parent_views: list[dict],
                               prompt_version: str = PROMPT_VERSION) -> str:
    parents = json.dumps(parent_views, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if prompt_version == "1.2.0":
        return (f"Question: {question}\n\nTask: {COMMUNICATION_TASK_V1_2}\n\n"
                f"Visible parent messages (canonical JSON):\n{parents}")
    if prompt_version not in {"1.3.0", PROMPT_VERSION}:
        raise ValueError(f"unsupported prompt replay version: {prompt_version}")
    return (f"Question: {question}\n\nTask: {COMMUNICATION_TASK}\n\n"
            f"Visible parent messages (canonical JSON):\n{parents}\n\n"
            f"{COMMUNICATION_OUTPUT_REMINDER}")
