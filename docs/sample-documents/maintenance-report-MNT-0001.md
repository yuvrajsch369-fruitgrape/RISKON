# Rex Industrial Manufacturing — Maintenance Record

**Maintenance Record ID:** MNT-0001
**Equipment:** EQ-0005 — Air Compressor (Ingersoll Rand, model PX-431, serial SN160734)
**Facility:** Rex Central Plant (FAC-002)
**Maintenance Type:** Preventive
**Scheduled Date:** April 7, 2026
**Actual Date Performed:** May 11, 2026 (**34 days delayed**)
**Performed By:** Barbara Lopez, Maintenance Technician
**Status:** Delayed

## Description
Scheduled preventive maintenance on Air Compressor delayed due to backlog/parts availability.

*(This record is also EQ-0005's most recent maintenance event — `equipment.last_maintenance_date` for
EQ-0005 is derived from this table rather than stored independently, so the equipment record and this
maintenance log cannot drift apart.)*

## Follow-On Event
An Equipment Failure incident (**INC-0014**) occurred on this same equipment (EQ-0005) approximately two
weeks after this delayed maintenance was finally performed. See `maintenance_records.related_incident_id`
= INC-0014.

This is one of three linked delay→failure pairs in the dataset (the other two: a second Air Compressor
delay cycle on EQ-0005 in mid-2025, and a Conveyor System delay on EQ-0006 at Rex South Plant) — each
follows the same shape: a preventive maintenance cycle slips by roughly a month, and an equipment failure
follows on the *same unit* within 6-15 days of the deferred work finally being completed. No single one of
these three events would necessarily stand out on its own; the pattern is only visible by joining
`maintenance_records.status='Delayed'` against `incidents.incident_type='Equipment Failure'` on matching
`equipment_id` within a short time window.

---
*Fictional record for the RISKON prototype.*
