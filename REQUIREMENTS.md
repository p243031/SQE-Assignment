# Student Course Registration System — Software Requirements Specification

**Course:** SE3002 Software Quality Engineering  
**Artifact:** Assignment 2 — System under test  
**Version:** 1.0

## 1. Purpose and scope

This small, in-memory system manages registration decisions, course enrollment, waiting lists, and withdrawals. It does not implement a database, web interface, payments, authentication, or automatic movement from waiting lists into available seats.

The requirements in this document are **authoritative for expected test results**. Students must derive black-box tests from these requirements before consulting source-code branches for white-box testing.

## 2. Input and data model

- `Student.student_id`: non-empty identifier; the supplied fixture uses valid identifiers.
- `Student.completed_courses`: set of course codes already passed.
- `Student.current_credits`: integer from **0 through 18**, inclusive.
- `Student.outstanding_dues`: nonnegative integer in rupees; any **positive** balance blocks new registrations.
- `Student.registered_courses`: set of currently registered course codes.
- `Course.code`: non-empty course code; supplied fixtures use valid codes.
- `Course.credit_hours`: integer **1 through 4**, inclusive.
- `Course.capacity`: positive integer (at least 1).
- `Course.enrolled`: integer from **0 through capacity**, inclusive.
- `Course.prerequisites`: set of course codes required before registration.
- `Course.waitlist`: list of student IDs awaiting a seat.

Assume string identifiers and collection types are correct. Test numeric validation only where explicitly stated below. No persistence or concurrency guarantees are required.

## 3. Functional requirements

| ID | Requirement |
|---|---|
| FR-01 | `check_credit_limit(current_credits, new_credits)` returns `True` when `current_credits + new_credits <= 18`, and `False` otherwise, for valid arguments. A total of **exactly 18** is allowed. |
| FR-02 | `check_credit_limit` raises `ValueError("Invalid current credits")` if `current_credits` is outside 0–18, and `ValueError("Invalid course credits")` if `new_credits` is outside 1–4. Inputs are checked in that order. |
| FR-03 | `prerequisites_satisfied(completed, required)` returns `True` only if **every** course in `required` appears in `completed`. If `required` is empty, it returns `True`. |
| FR-04 | Registration is blocked with `DUES_BLOCK` if a student owes **any amount greater than Rs. 0**. |
| FR-05 | Registration returns `ALREADY_REGISTERED` when the student is already registered in the target course. |
| FR-06 | Registration returns `PREREQUISITES_MISSING` if one or more required prerequisites have not been completed. |
| FR-07 | Registration returns `CREDIT_LIMIT` if adding the course would exceed 18 credits. |
| FR-08 | When `enrolled == capacity`, an otherwise eligible student receives `WAITLISTED`; when `enrolled < capacity`, the outcome is `REGISTERED`. |
| FR-09 | Conditions are evaluated in this priority order: dues, already registered, prerequisites, credit limit, availability. Only the **first applicable outcome** is returned. |
| FR-10 | `registration_decision(student, course)` returns a status string **without mutating** either object. |
| FR-11 | `register_course` applies the decision. For `REGISTERED`, add course code to `registered_courses`, increase credits by the course credit hours, and increment `enrolled` by one. |
| FR-12 | For `WAITLISTED`, `register_course` appends the student ID to the waitlist **only if absent**, without changing credits, registered courses, or enrollment. Other unsuccessful outcomes make no state changes. |
| FR-13 | `withdraw_course` returns `True` when the student is enrolled in the course; it removes the course from `registered_courses`, subtracts its credit hours, and **decrements `enrolled` by one**. |
| FR-14 | `withdraw_course` returns `False` when the student is not registered in the course and leaves both objects unchanged. |
| FR-15 | `registration_decision` raises `ValueError("Invalid dues")` for negative dues and `ValueError("Invalid capacity or enrollment")` for capacity below 1 or enrolled outside 0–capacity. Validate dues first. |

## 4. Decision statuses

`REGISTERED`, `WAITLISTED`, `DUES_BLOCK`, `ALREADY_REGISTERED`, `PREREQUISITES_MISSING`, `CREDIT_LIMIT`.

## 5. Suggested black-box testing dimensions

- **ECP:** dues (0 / positive / negative), prerequisites (none / all / some / none completed), already-registered status, seats available/full, course credits valid/invalid.
- **BVA:** current credits 0 and 18; new course credits 1 and 4; combined-credit limit of 18; seats around `capacity`; dues at 0 versus 1.
- **Decision tables:** priority interaction among dues, existing registration, prerequisites, credit limit, seat availability.
- **State changes:** registration and withdrawal, including failed operations that must not modify state.

## 6. Example acceptance scenarios

1. A student with 15 credits registering for a 3-credit course remains eligible: total is 18.
2. A student with 16 credits registering for a 3-credit course is rejected for credit limit.
3. A course requiring both `CS101` and `MATH101` must reject a student who completed only `CS101`.
4. Outstanding dues of Rs. 1 prevent registration.
5. If a course has capacity 30 and enrolled 30, an otherwise eligible student joins the waiting list.
6. Withdrawing an enrolled student reduces both student credits and course enrollment.

## 7. Test execution guidance

Python 3.10+ recommended. The module uses only Python's standard library. Install `pytest` and `pytest-cov` separately to execute student-authored tests. No official tests or defect disclosures are included with the student starter package.
