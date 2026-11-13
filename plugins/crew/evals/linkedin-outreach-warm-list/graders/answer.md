---
type: llm
weight: 2
---

The user has a CSV of warm LinkedIn contacts and asked what a lead-generation Agent would look like, without building or installing anything. Judge the final answer on these six points.

PASS if all six hold:

1. It works from the user's CSV. It does not propose finding or searching for leads, and does not ask for treg or jq.
2. It says each person needs a LinkedIn profile URL in the file, which their CSV lacks, and how to get one for their own first-degree connections (LinkedIn's data export of connections), or asks the user for the URLs.
3. It says a second-degree contact is reached with a connection request first, before any message.
4. It says the "why I picked them", priority, notes or mutual-connection columns stay out of what is sent, because anything sent can end up in a message.
5. It says the user connects their own LinkedIn account in the Crew app, with no HeyReach account or API key of their own needed, and does not claim the workspace's LinkedIn feature is off.
6. It says each Live message can wait for the user's approval before it is sent.

FAIL if any point is missing, or if the answer created or installed anything.
