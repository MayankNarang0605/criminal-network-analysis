// Run with: neo4j-admin database import full --nodes=Person=nodes_person.csv \
//   --nodes=Vehicle=nodes_vehicle.csv --nodes=Organization=nodes_organization.csv \
//   --nodes=Location=nodes_location.csv --nodes=Case=nodes_case.csv \
//   --relationships=CALLS=relationships_calls.csv
// Or, for an already-running DB, use LOAD CSV, e.g.:
LOAD CSV WITH HEADERS FROM 'file:///nodes_person.csv' AS row
MERGE (p:Person {person_id: row.`person_id:ID(Person)`}) SET p.full_name = row.full_name, p.city = row.city;

LOAD CSV WITH HEADERS FROM 'file:///relationships_calls.csv' AS row
MATCH (a:Person {person_id: row.`:START_ID(Person)`}), (b:Person {person_id: row.`:END_ID(Person)`})
MERGE (a)-[r:CALLS]->(b) SET r.confidence = toFloat(row.confidence), r.source_record = row.source_record;
