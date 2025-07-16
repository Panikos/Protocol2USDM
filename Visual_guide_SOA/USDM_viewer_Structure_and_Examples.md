# Recommended SoA Structure with USDM Entity Mapping

This document outlines a standardized, robust structure for a Schedule of Activities (SoA) table. It is designed to balance clarity for human readers with the logical organization required for digital systems like the Unified Study Definition Model (USDM). The structure is annotated with the specific USDM entities that correspond to each conceptual part of the table.

## Header Rows (Timeline Columns) -> Mapped to `Epoch`, `Encounter`, and `Timing` Entities

The columns of an SoA table represent the study timeline. In USDM, this is modeled using three core entities to capture the hierarchy of time.

| Header Row (Conceptual)        | USDM Entity     | USDM Attribute(s)                          | Purpose in USDM                                                                          |
| :----------------------------- | :-------------- | :----------------------------------------- | :--------------------------------------------------------------------------------------- |
| **1. Study Period / Epoch** | `StudyEpoch`    | `id`, `label`, `description`               | The highest-level container for a phase of the study (e.g., Screening, Treatment).       |
| **2. Visit Name / Timepoint** | `Encounter`     | `id`, `label`, `description`               | Represents a specific visit or timepoint within an `Epoch` (e.g., Day 1, Week 4).          |
| **3. Visit Window** | `Timing`        | `windowLabel`, `windowLower`, `windowUpper`| Defines the permissible time window for an encounter (e.g., "±2 Days").                  |

---

## Header Columns (Procedure Rows) -> Mapped to `Activity` Entity

The rows of an SoA table list the procedures to be performed. In USDM, these are modeled using the `Activity` entity. A hierarchical structure is achieved by designating some `Activity` objects as parents containing child activities.

| Header Column (Conceptual)   | USDM Entity / Structure     | USDM Attribute(s)            | Purpose in USDM                                                                                                  |
| :--------------------------- | :-------------------------- | :--------------------------- | :--------------------------------------------------------------------------------------------------------------- |
| **1. Category / System** | `Activity` (as a parent)    | `id`, `label`, `childIds`    | A parent `Activity` object serves as the category header. Its `childIds` array lists the specific procedures under it. |
| **2. Activity / Procedure** | `Activity` (as a child)     | `id`, `label`, `description` | Represents the specific, individual procedure to be performed (e.g., "12-lead ECG").                             |

---

### Example of Recommended SoA Structure with USDM Entities

This example illustrates how the conceptual table structure maps directly to the USDM entities.

| **`Activity` (parent)** | **`Activity` (child)** | **`StudyEpoch` -> `Encounter` -> `Timing`** |
| :--- | :--- | :--- |
| **Category / System** | **Activity / Procedure** | **Epoch: Screening**<br>**Encounter: Visit 1**<br>**Timing: Days -42 to -9** | **Epoch: Treatment**<br>**Encounter: Visit 2**<br>**Timing: Day 1** | **Epoch: Follow-up**<br>**Encounter: Visit 8**<br>**Timing: Day 54 ± 2 days** |
| **Eligibility & Administration** | Informed Consent | X | | |
| | Inclusion/Exclusion Criteria Check | X | X | |
| | ALXN1840 15 mg/day Administration | | X | |
| **Safety Assessments** | Physical Examination | X | | X |
| | Vital Signs Measurements | X | X | X |
| | 12-lead ECG (triplicate) | X | X | X |

> **Note on Mapping:** The "X" marks in the table are represented in the USDM by creating an **`activityTimepoints`** object. This object serves as the critical link that associates a specific `activityId` with a specific `plannedTimepointId` (which corresponds to an `Encounter`), effectively placing a procedure at a specific point on the study timeline.