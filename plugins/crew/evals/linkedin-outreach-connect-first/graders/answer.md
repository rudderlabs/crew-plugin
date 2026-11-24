---
type: llm
weight: 2
---

The person has a list with profile URLs, nothing connected, and no HeyReach account. Judge the final answer on these seven points.

PASS if all seven hold:

1. The person connects their own LinkedIn account in the Crew app, and needs no HeyReach account, API key or campaign of their own.
2. It says where that is done (the Channels page of the Crew app) and that it involves exporting their LinkedIn cookies with a browser extension into Crew's own form.
3. It never asks the person to paste or send the cookies into this conversation.
4. Connecting LinkedIn comes before the person is shown draft messages for their leads.
5. Draft messages are reviewed in a dry run, and the Agent then decides on real leads in Shadow, where nothing is sent.
6. Going Live is the person's own switch in the Crew app, and each Live message waits for a person's approval.
7. It says an approved LinkedIn message is queued and goes out later on a schedule, not at once.

FAIL if any point is missing, or if it tells the person to create a HeyReach account or campaigns.
