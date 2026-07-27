# Carrier Escalation Matrix

## Purpose
This matrix defines who to contact, when to escalate, and what information is required when carrier performance or shipment execution issues occur. It standardizes response behavior across operations, customer success, and account management teams.

## Scope
- Applies to all contracted carriers and subcontracted linehaul partners.
- Covers missed pickups, excessive dwell, in-transit delays, delivery failures, and status blackout events.
- Used for live issue response and post-incident accountability.

## Escalation Levels
### Level 0: Self-Serve Resolution
- Owner: Shipment coordinator.
- Trigger: data discrepancy, minor update lag, or non-critical scheduling adjustment.
- SLA: resolve within 60 minutes.

### Level 1: Carrier Dispatch
- Owner: Carrier dispatch contact.
- Trigger: missed milestone, no movement update > 4 hours, appointment risk.
- SLA: dispatch acknowledgement in 30 minutes.

### Level 2: Carrier Operations Supervisor
- Owner: Carrier operations supervisor.
- Trigger: unresolved Level 1 after 45 minutes, repeat missed milestones, or delay > 12 hours.
- SLA: corrective plan in 30 minutes from escalation.

### Level 3: Carrier Account Manager
- Owner: Carrier account manager and internal transport manager.
- Trigger: delay > 24 hours, high-value/critical customer impact, repeated lane underperformance.
- SLA: executive summary + action plan in 60 minutes.

### Level 4: Executive Escalation
- Owner: internal duty lead + carrier senior leadership.
- Trigger: service failure with contractual risk, safety concern, or multi-shipment cascading impact.
- SLA: immediate bridge call within 30 minutes.

## Escalation Timing Rules
1. Escalate one level if no response at SLA threshold.
2. Skip directly to Level 3 for strategic customer shipments with high business impact.
3. Initiate Level 4 immediately for safety incidents or potential legal exposure.
4. Keep previous owners informed; escalation adds ownership layers, not handoff abandonment.

## Required Fields for Every Escalation
- `shipment_id`
- `carrier_name`
- `route_id` and lane (origin-destination)
- `event_type` triggering escalation
- `planned_milestone_time` vs `actual_time`
- `delay_duration_hours`
- `customer_tier`
- `business_impact` summary
- `current_eta`
- `requested_carrier_action`
- `next_update_time`
- `case_owner`

## Contact Channel Guidance
- Level 0-1: TMS notes + dispatch email/chat.
- Level 2: direct phone plus written recap.
- Level 3: account channel with customer success copied.
- Level 4: bridge call + incident timeline document.

## Example Scenarios
### Scenario A: Missed Pickup with No Dispatch Response
- Trigger: pickup appointment missed by 90 minutes; no dispatch response.
- Action: escalate from Level 1 to Level 2 at 45-minute no-response mark.
- Expected output: supervisor confirms recovery pickup and revised ETA.

### Scenario B: Repeat Delay on the Same Lane
- Trigger: third late shipment in one week on same origin-destination route.
- Action: Level 3 escalation for root-cause and corrective lane plan.
- Expected output: temporary capacity shift and service improvement timeline.

### Scenario C: Temperature-Control Risk
- Trigger: reefer unit fault alert while in transit.
- Action: immediate Level 4 due to product integrity risk.
- Expected output: rapid intervention, product condition verification, and customer escalation note.

## FAQ
### Should we escalate if the carrier says "working on it"?
Yes, if no concrete corrective action and ETA are provided within the SLA window.

### How often should status be updated after Level 3?
At least every 60 minutes until the shipment is moving with a stable ETA.

### When is a case considered resolved?
When shipment milestones normalize, customer has been informed, and closure notes include root cause and prevention action.
