# Weather Delay Policy

## Purpose
This policy establishes a standard process for detecting, classifying, and managing weather-related shipment disruptions. It ensures teams make consistent risk decisions, communicate quickly, and maintain audit-ready incident records.

## Scope
- Applies to all domestic and cross-border ground shipments.
- Covers delays caused by snow, ice, flooding, hurricanes, high winds, wildfires, and severe thunderstorms.
- Includes both forecast-based proactive actions and live disruption response.

## Weather Risk Classification
### Risk Level A (Monitor)
- Minor weather advisories near route corridor.
- No expected lane closures or major terminal impact.
- Action: monitor and notify internal operations only.

### Risk Level B (Elevated)
- Credible forecast of operational slowdown within 24 hours.
- Potential hub congestion or partial lane disruption.
- Action: pre-alert carrier contacts and customer success.

### Risk Level C (High)
- Confirmed severe weather warning impacting active route or destination metro.
- Known service degradation from carrier or terminal.
- Action: escalate to regional operations manager and trigger customer advisory.

### Risk Level D (Critical)
- Active route closure, evacuation zone, declared emergency, or network-wide disruption.
- High probability of multi-day delays.
- Action: immediate escalation to duty manager and contingency planning team.

## Response Time Expectations (SLA)
- Risk review for active shipments:
  - Level A-B: within 2 hours of alert
  - Level C-D: within 30 minutes of alert
- Initial customer communication:
  - Level B: within 2 hours
  - Level C: within 1 hour
  - Level D: within 30 minutes
- ETA refresh cadence:
  - Level B: every 8 hours
  - Level C: every 4 hours
  - Level D: every 2 hours

## Required Incident Fields
Each weather-delay record must include:
- `shipment_id`
- `route_id` and lane description
- `carrier_name`
- `weather_event_type` (e.g., snowstorm, flood, wildfire)
- `risk_level`
- `alert_source` and timestamp
- `planned_delivery_date` and revised ETA
- `facility_or_region_impact`
- `customer_notification_status`
- `next_update_time`
- `owner`

## Escalation Rules
1. Escalate to Level C when forecast confidence exceeds 70% for severe impact on shipment path.
2. Escalate to Level D when:
   - route closure is confirmed, or
   - consecutive ETA slips exceed 24 hours, or
   - shipment is critical inventory with downstream service commitments.
3. De-escalate only after carrier confirms movement recovery and ETA stabilizes.

## Operational Playbook
1. Identify impacted shipments by route geography and planned transit window.
2. Tag affected shipments with temporary weather-risk flag.
3. Confirm carrier service bulletin and available reroute options.
4. Decide action:
   - hold and monitor,
   - reroute to alternate lane,
   - reschedule delivery window.
5. Send structured update to customer with risk level, expected impact, and next check-in.
6. Update incident every SLA interval until delivery or full stabilization.

## Example Scenarios
### Scenario A: Snowband Across Midwest Corridor
- Condition: heavy snow warning with expected interstate speed restrictions.
- Classification: Level C.
- Action: update ETA +12 hours, notify customers within 1 hour, reassess every 4 hours.

### Scenario B: Coastal Hurricane Landfall
- Condition: destination terminal closed and local emergency declared.
- Classification: Level D.
- Action: reroute where feasible, pause affected final-mile deliveries, send updates every 2 hours.

## FAQ
### When should we reroute instead of waiting?
Reroute when projected benefit is at least 12 hours and alternative route risk is lower than current lane risk.

### How do we handle uncertain forecasts?
Use Level B with proactive monitoring and carrier pre-alerts, then escalate only on higher-confidence or confirmed impact signals.

### What closes a weather incident?
Incident closes after shipment delivery or after network conditions normalize and ETA no longer drifts for one full update cycle.
