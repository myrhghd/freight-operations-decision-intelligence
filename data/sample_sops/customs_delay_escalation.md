# Customs Delay Escalation SOP

## Purpose
This SOP defines how operations teams identify, triage, escalate, and resolve customs-related shipment delays for international and cross-border freight. The objective is to restore movement quickly, maintain customer trust, and create consistent case records for analytics and root-cause review.

## Scope
- Applies to all shipments with event signals such as `CUSTOMS_HOLD`, `DELAYED`, or manual broker alerts.
- Applies from first customs delay signal through case closure.
- Does not replace legal or trade-compliance policy; it operationalizes response handling.

## Severity Levels and Escalation Triggers
### Severity 1 (Low)
- Hold expected to clear within 12 hours.
- No temperature control, regulated goods, or customer-critical commitment.
- Escalate only within operations channel; no executive notification.

### Severity 2 (Medium)
- Hold duration exceeds 12 hours, or shipment is already past planned delivery date.
- Customer has requested proactive status updates.
- Escalate to regional customs specialist within 30 minutes.

### Severity 3 (High)
- Hold exceeds 24 hours, or missing/incorrect trade documentation blocks release.
- Includes higher-impact freight (medical supplies, line-down components, launch inventory).
- Escalate to customs lead and carrier account manager within 15 minutes.

### Severity 4 (Critical)
- Regulatory enforcement, potential seizure, compliance breach, or cascading network impact.
- Escalate to duty manager, compliance officer, and customer success lead immediately (within 10 minutes).

## Response Time Expectations (SLA)
- Initial case creation: within 10 minutes of first customs hold signal.
- First internal escalation: within 15 minutes for Severity 3-4, 30 minutes for Severity 2.
- First customer-facing update:
  - Severity 1-2: within 60 minutes
  - Severity 3-4: within 30 minutes
- Ongoing updates:
  - Severity 1: every 6 hours
  - Severity 2: every 4 hours
  - Severity 3: every 2 hours
  - Severity 4: hourly until release or alternative plan accepted

## Required Case Fields
Every customs-delay case must capture:
- `shipment_id`
- `customer_name` and `customer_tier`
- `origin_country`, `destination_country`, and border/port code
- `carrier_name` and broker contact
- `planned_delivery_date` and current ETA
- `delay_start_timestamp` and latest event timestamp
- `hold_reason_code` (if available)
- `missing_documents` list (if applicable)
- `severity`
- `owner` and `next_update_time`
- `recommended_action`

## Standard Escalation Workflow
1. Confirm delay signal accuracy using event log and carrier status feed.
2. Open incident ticket and populate required fields.
3. Contact broker/carrier for hold reason and release prerequisites.
4. Classify severity and assign case owner.
5. Notify customer with current status, reason (if known), and next update time.
6. If unresolved at SLA threshold, escalate to next tier and refresh ETA.
7. On release, confirm movement event and send closure update with root cause.

## Example Scenarios
### Scenario A: Missing Commercial Invoice
- Trigger: `CUSTOMS_HOLD` event with broker note "invoice mismatch".
- Action: Severity 3, escalate to customs lead within 15 minutes.
- Resolution: corrected invoice submitted, release in 8 hours.
- Customer update cadence: every 2 hours until release.

### Scenario B: Random Inspection
- Trigger: Border inspection queue notice, no document issue.
- Action: Severity 2 unless perishable/critical freight, then Severity 3.
- Resolution: hold cleared after 14 hours.
- Customer update cadence: every 4 hours.

## FAQ
### When should we escalate from Severity 2 to Severity 3?
Escalate when delay exceeds 24 hours, delivery commitment is at risk, or document issues require multi-party coordination.

### Can we close a case before final delivery?
Yes. Close the customs delay case after release and movement confirmation, but link it to the shipment until delivery.

### What if the carrier cannot provide a hold reason code?
Record `hold_reason_code = unknown`, capture source contact, and continue timed updates while escalating broker outreach.
