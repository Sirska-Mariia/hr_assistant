You decide how well the HR policy excerpts below cover the employee's question.
Each excerpt line starts with a citation id like [leave.md §3.2].

coverage:
- "full": the excerpts contain what the employee needs for a useful, practical answer. General procedures count
  (for example "submit a ticket in the portal"). Do not require names of people, e-mail addresses or exact wording.
- "partial": the excerpts answer only part of the question (a multi-part question where one part is not covered, or
  the policy says something exists but not the detail asked, e.g. a buddy is assigned but the person is not named).
- "none": the topic is not covered, or the excerpts are only loosely related.

Rules: do not use outside knowledge and do not guess what the company "probably" does.
supporting_sections: citation ids of the lines you would use (empty if "none").

Reply with JSON only: {{"coverage": "full|partial|none", "supporting_sections": ["leave.md §3.2"], "reason": "<max 15 words>"}}

Question: {question}

Excerpts:
{excerpts}
