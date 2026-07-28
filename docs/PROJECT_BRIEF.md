# Project Brief

## Business Context

Freight operations teams track shipments across many carriers, lanes, and
customers simultaneously. When a shipment is delayed or flagged with an
exception, the people responsible for resolving it need fast answers to
straightforward questions: where is this shipment, is it at risk, which
carriers or lanes are underperforming, and what is the standard procedure
for handling the disruption in front of them. Today those answers are
spread across shipment records, event logs, carrier performance data, and
written standard operating procedures (SOPs) that are not easy to search
quickly.

## Intended Users

- Freight and logistics operations coordinators handling day to day
  shipment monitoring and exception response.
- Carrier and customer account managers reviewing performance and risk.
- Anyone evaluating this project as a demonstration of applied data and
  retrieval techniques in a logistics context.

## Primary Business Question

> How can shipment, event, carrier, route, exception, and operating-procedure
> data help logistics teams identify shipment status, explain disruptions, and
> determine appropriate next actions?

## Project Objective

Provide a local, self contained tool that lets a user look up a shipment,
understand its status and history, see which shipments and lanes carry
elevated risk, and retrieve the relevant SOP guidance for a given type of
disruption. All of this is available from a single interface backed by a
single API.

## Core Use Cases

1. Look up a specific shipment's status, route, and delivery dates.
2. Review the event timeline for a specific shipment.
3. Review delay rate analytics broken down by carrier and lane.
4. Identify high risk shipments (delayed, flagged with an exception, or on
   a historically high delay lane).
5. Ask a natural language question and be routed to the right data view or
   to relevant SOP content.
6. Search SOP and FAQ documents directly for procedure guidance, such as
   customs delay escalation or weather delay policy.

## Business Value

- Brings shipment data and SOP guidance into a single place, reducing the
  need to check multiple sources during a disruption.
- Gives a consistent, queryable view of delay and risk patterns across
  carriers and lanes.
- Demonstrates a retrieval based approach to SOP lookup that operates
  independently of the shipment data model.

## Data Entities

- **Carriers**: carrier identity, type, on time rate, average transit days,
  risk score.
- **Customers**: customer identity, tier, industry, region.
- **Routes**: origin and destination, distance, lane type, historical delay
  rate.
- **Shipments**: status, mode, planned and actual dates, delay flag and
  days, exception flag, freight cost, and references to a carrier,
  customer, and route.
- **Shipment events**: timestamped status events per shipment, such as
  `CREATED`, `IN_TRANSIT`, `DELAYED`, and `DELIVERED`.
- **Exceptions**: exception type, severity, detection time, resolution
  status, and recommended action, linked to a shipment.
- **SOP and FAQ documents**: markdown standard operating procedures
  covering carrier escalation, customer notification, customs delay
  escalation, and weather delay handling.

## Success Criteria

- A user can retrieve any generated shipment's status and event history.
- A user can retrieve delay and risk analytics across carriers and lanes.
- A user can ask a question about an SOP and receive the relevant text and
  source document.
- The complete workflow, from data generation through the API and
  interface, runs locally in a clean environment. The only network
  requirement is a one time download of the embedding model.

## Scope

- Synthetic shipment, carrier, customer, route, event, and exception data.
- A FastAPI backend exposing shipment, analytics, and assistant endpoints.
- A DuckDB operational database built from the synthetic data.
- A Chroma vector store over a fixed set of sample SOP documents.
- A deterministic assistant router that does not generate text.
- A Neo4j graph that holds the same shipment, carrier, customer, route,
  event, and exception data as DuckDB, used for relationship analysis such
  as connected shipment context, peer shipments on the same carrier and
  route, and prior shipments with a matching exception.
- A Docker Compose stack that runs the complete application, including
  Neo4j, the API, and the interface, from a single command.
- A Streamlit interface covering shipment lookup, events, analytics, and
  the assistant.

## Out of Scope

- Real or production freight data.
- Any generative language model. SOP answers are retrieved directly rather
  than generated.
- Authentication, access control for multiple users, or deployment
  infrastructure.

## Assumptions and Limitations

- All data is synthetic and generated locally with a fixed random seed, so
  it reflects the rules of the generator rather than real freight patterns.
- Assistant routing is based on keywords and patterns rather than a model,
  so questions phrased outside its known patterns may be misrouted.
- The system is designed for local, single user use.
