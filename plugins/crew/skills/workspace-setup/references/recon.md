# Recon: grounding setup in real customer data

Before writing any workspace artifact, find out what data the workspace actually has. This changes what you build — real source names, real volumes, and real destinations are far better inputs than a plausible guess.

## Contents

- [Sequence](#sequence)
- [Interpreting what comes back](#interpreting-what-comes-back)
- [Debugging event flow](#debugging-event-flow)
- [What recon can't tell you](#what-recon-cant-tell-you)

## Sequence

Use the RudderStack MCP at `https://mcp.rudderstack.com/mcp`, which the `rudder-core` plugin connects (the plugin README says how to install it); it signs in as you, to your own workspaces. The tool names below are its own; where your client lists them differently, trust its list. Each step feeds the next.

1. **Pick the workspace.** If your account has more than one, call `user_details` to list them and confirm with the user which one carries production traffic: expect production, dev and sandbox workspaces, and a workspace created in the last few days is likely a new test one. Point the calls at it: pass its id as `workspace_id` when the tools take one, otherwise call `user_switch_workspace` first. **Confirm which you're looking at before drawing conclusions.**
2. **List sources** (`list_sources`) — the real inventory. Source _names_ are informative on their own: they reveal the upstream systems, the integration style, and often the producer (a name like `<system>_<object>_changes_<cloud>` implies a job pushing changes from that system).
3. **Pull event metrics per source** (`get_source_event_metrics`) — real event names with counts over a window. This is the ground truth for the event catalog.
4. **Pull event properties** for interesting events (`get_source_event_properties`) — the field-level schema, when available.
5. **Sample live events** (`get_live_events`) if the shape is still unclear. It hashes every property value, so it confirms event names and property keys, not values or types.
6. **List destinations** (`list_destinations`) — including whether a Crew webhook destination exists yet, what it's connected to, and whether a transformation is attached. `get_destination_event_metrics` and `get_destinations_errors` give a destination's delivered and failed counts, for [debugging event flow](#debugging-event-flow).

## Interpreting what comes back

**Raw webhook sources usually land as one opaque event.** A source ingesting from an external producer commonly shows a single generic event name with no property schema, because the real structure is inside an untyped payload. High volume on one generic event name means the structure exists but isn't exposed to metrics.

Consequence: the field names you write into the catalog are **designed, not discovered**. That's fine — say so, and convert the load-bearing assumption into a question for the customer ("you track X as Y, correct?"). The trigger definition depends on the answer.

**Empty results are frequently timing, not absence.** A source with meaningful daily volume can easily return zero over a five-minute window. Before concluding something is broken, widen the window — check an hour and a day alongside the short window. Compare the shapes.

**Volume distribution reveals producer cadence.** Compare counts across nested windows (5 min / 1 hr / 24 hr). Steady arrival means roughly proportional counts. Clustered arrival — a burst then nothing — means the upstream producer is on a schedule, polling or batching on an interval.

This matters because it determines whether real-time decisioning is achievable, and _the cadence is usually set upstream of RudderStack_. Webhook sources ingest whatever is POSTed to them, in real time, with no poll schedule. A destination with batching disabled forwards per-event. If arrival is bursty with both of those true, the burstiness belongs to the producer — a polling job rather than a change-stream. Whoever owns that job decides how real-time the Agent can be: name them.

## Debugging event flow

When events "aren't arriving," check each hop separately. The break is almost never where it first appears.

| Hop                     | What to check                             | What it means                                                                                                     |
| ----------------------- | ----------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| Producer → source       | Source event metrics over several windows | Zero over a long window = upstream isn't sending. Zero over a short window only = normal burstiness.              |
| Source → destination    | Destination delivered vs failed counts    | Delivered with zero failures = the pipe works, the service accepted it. Failures = check config, especially auth. |
| Destination → decisions | Agent status and trigger match            | The most common silent failure — see below.                                                                       |

**Delivery success does not mean the agent acted.** Two very common reasons a healthy pipe still produces zero decisions:

- **The agent isn't active.** A draft agent doesn't evaluate incoming events. Events land and sit there. Zero decisions is the correct, expected behavior — not a bug.
- **The trigger doesn't match the incoming event name.** If events arrive as a generic raw name and the agent triggers on a semantic name, nothing will ever fire. Something must do the mapping — a transformation on the destination, or transformation at the producer.

Check both before investigating anything deeper.

**Auth config worth flagging even when delivery succeeds:** a destination configured for bearer/API-key auth with an empty credential may still return success if the receiving service doesn't enforce it yet. It will break the moment enforcement is turned on. Flag it as a go-live task rather than a current failure — being precise about _when_ something becomes a problem is more useful than calling it broken now.

## What recon can't tell you

Be explicit about the boundary:

- **Payload internals of opaque sources** — inferred, not known.
- **Business semantics** — which stage value means "booked," whether an object maps to the concept the use case cares about. Ask.
- **Consent and compliance state** — usually not in event metrics, and load-bearing for any outbound action.
- **Who owns which system** — the person who wants the Agent is often not the person who can grant access to its data or channels. Surface this early; it is a common reason setup stalls.
