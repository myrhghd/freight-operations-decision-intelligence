# Customer Notification Policy

## Purpose
This policy defines how and when customers are notified about shipment risks, delays, and exceptions. It aims to deliver timely, accurate, and actionable updates while maintaining a consistent communication standard across customer tiers.

## Scope
- Applies to all outbound customer-facing shipment communications.
- Covers proactive notices, incident alerts, ETA changes, and closure confirmations.
- Includes email, portal message, and account-team handoff notes.

## Notification Principles
1. Be timely: communicate known risk early rather than waiting for perfect certainty.
2. Be specific: provide shipment identifiers, impact, and next update time.
3. Be actionable: include what teams are doing and what customer action (if any) is needed.
4. Be consistent: follow tier-based cadence and escalation rules.

## Customer Tier Response Expectations
### Strategic Tier
- Initial exception notice: within 30 minutes.
- ETA change notice: within 30 minutes of confirmed change.
- Follow-up cadence: every 2 hours for open critical issues.

### Enterprise Tier
- Initial exception notice: within 60 minutes.
- ETA change notice: within 60 minutes.
- Follow-up cadence: every 4 hours for open high-impact issues.

### Growth and Standard Tiers
- Initial exception notice: within 2 hours.
- ETA change notice: within 2 hours.
- Follow-up cadence: every 8 hours unless severe impact.

## Required Fields in Customer Notifications
Every notification must include:
- `shipment_id`
- `shipment_status`
- `origin_city` and `destination_city`
- `planned_delivery_date`
- `updated_eta` (if available)
- `issue_type` (weather, customs, carrier delay, facility issue, etc.)
- `impact_summary` (what changed and expected delay)
- `current_action` (what operations/carrier is doing)
- `next_update_time`
- `support_contact`

## Escalation Rules for Communications
1. Escalate communication channel to account manager when:
   - delay exceeds 24 hours, or
   - customer is strategic tier, or
   - repeated ETA changes occur (2+ revisions in 12 hours).
2. Add leadership visibility for critical customer-impact events:
   - production line risk
   - regulated or sensitive goods
   - contractual penalty exposure.
3. Send closure notification within 60 minutes of delivery or issue resolution.

## Standard Message Structure
1. Subject: `Shipment Update: <shipment_id> - <issue_type>`
2. What happened: one-sentence event summary.
3. Impact: expected delay or service effect.
4. Current action: operational mitigation underway.
5. Next update: exact timestamp and contact path.

## Example Scenarios
### Scenario A: Delay with Known Recovery ETA
- Event: linehaul delay caused by hub congestion.
- Customer message: includes revised ETA (+10 hours), mitigation action, and next update in 4 hours.
- Tier handling: strategic customer gets 2-hour updates until delivered.

### Scenario B: Exception Without Confirmed ETA
- Event: customs hold pending broker response.
- Customer message: state ETA is pending, provide known hold reason, and commit to next update within SLA.
- Follow-up: update immediately when ETA becomes available.

### Scenario C: Delivery Completed After Delay
- Event: shipment delivered 1 day late.
- Closure message: confirm delivery timestamp, summarize root cause, and prevention step.

## FAQ
### Should we notify customers for low-confidence risks?
Yes, when potential impact could alter delivery expectations. Mark updates as precautionary and include confirmation timeline.

### What if information changes quickly?
Send corrected updates promptly. Include "update to prior message" language and a fresh next update time.

### Can notifications be skipped if delay is small?
No for strategic/enterprise tiers. For growth/standard tiers, minor delays under 2 hours may be batched unless customer requires real-time alerts.
