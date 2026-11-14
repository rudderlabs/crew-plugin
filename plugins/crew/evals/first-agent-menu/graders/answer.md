---
type: llm
weight: 2
---

A person new to Crew, on an empty workspace, asked what they can build. Judge the final answer.

PASS if all five hold:

1. It offers a short list of things to build (three to six), each worded as what the person has or wants, not as Crew's internal terms alone.
2. One option is reaching out, on LinkedIn or by email, to a list of people the person already has.
3. It invites the person to describe what they want in their own words instead of picking.
4. It asks at most two questions.
5. It builds, installs and creates nothing.

FAIL if any point is missing, if the list has more than six options, or if the answer is mostly an explanation of how Crew works.
