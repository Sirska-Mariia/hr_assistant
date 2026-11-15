You grade an HR assistant's answer. QUESTION, ANSWER, KEY FACTS (what a correct answer must state) and the
POLICY TEXT cited by the answer are given.

1. For each key fact, say whether the ANSWER states it correctly (true/false).
2. Count claims in the ANSWER that are NOT supported by the POLICY TEXT (unsupported_claims, integer).

Reply with JSON only: {{"facts_covered": [true, false, ...], "unsupported_claims": 0}}
The list must have exactly {n_facts} entries, in the order of the key facts.

QUESTION: {question}
KEY FACTS: {key_facts}
ANSWER: {answer}
POLICY TEXT: {policy}
