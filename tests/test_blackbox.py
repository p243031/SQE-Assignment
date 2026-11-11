"""Black-box tests for the Student Course Registration System.

Every expected value below is derived from REQUIREMENTS.md (the SRS), never from
the behaviour of registration.py.  A failing test therefore points at a
suspected defect; expected values must not be edited to make a test pass.

Technique traceability
----------------------
Each unique executable case (TC-xx) carries a ``covers`` mapping of
technique-level design IDs -> label:

    ECP-xx  equivalence class partitioning
    BVA-xx  boundary value analysis
    DT-xx   decision table rule / priority combination

Cases that were *exact* duplicates across the three technique suites (same
function, same input, same SRS-derived expected result) are executed once and
list every technique ID they satisfy.  Cases that merely produce the same
output from different inputs are NOT merged.  See docs/blackbox_test_design.xlsx
(sheet "Optimization") for the full before/after table.

Run:  python -m pytest tests/test_blackbox.py -v
"""
import copy
import re
from collections import namedtuple

import pytest

from registration import (
    Course,
    Student,
    check_credit_limit,
    prerequisites_satisfied,
    register_course,
    registration_decision,
    withdraw_course,
)

# --------------------------------------------------------------------------
# Fixture builders
# --------------------------------------------------------------------------
# Baseline = an eligible student: no dues, not registered, prerequisite met,
# 10 + 3 credits <= 18, seats available.  Each case overrides only what it needs.


def make_student(**over):
    base = dict(
        student_id="S001",
        completed_courses={"CS101"},
        current_credits=10,
        outstanding_dues=0,
        registered_courses=set(),
    )
    base.update(over)
    return Student(**copy.deepcopy(base))


def make_course(**over):
    base = dict(
        code="CS201",
        credit_hours=3,
        capacity=30,
        enrolled=10,
        prerequisites={"CS101"},
        waitlist=[],
    )
    base.update(over)
    return Course(**copy.deepcopy(base))


def snapshot(student, course):
    """Deep copy of all observable state, used for no-mutation checks."""
    return copy.deepcopy(vars(student)), copy.deepcopy(vars(course))


def assert_outcome(call, expected):
    """Assert a return value, or an exact ValueError message (pytest.raises)."""
    if isinstance(expected, Exception):
        with pytest.raises(type(expected), match=f"^{re.escape(str(expected))}$"):
            call()
    else:
        result = call()
        assert result == expected
        assert type(result) is type(expected)


# --------------------------------------------------------------------------
# Case tables (single source of truth, also read by the docs generator)
# --------------------------------------------------------------------------
Case = namedtuple("Case", "tc func req desc args expected covers")

BAD_CUR = ValueError("Invalid current credits")
BAD_CRS = ValueError("Invalid course credits")
BAD_DUES = ValueError("Invalid dues")
BAD_CAP = ValueError("Invalid capacity or enrollment")

# ---- check_credit_limit(current, new)  [FR-01, FR-02] ----------------------
CREDIT_CASES = [
    Case("TC-01", "check_credit_limit", "FR-01", "Total below 18", (10, 3), True,
         {"ECP-01": "Credits: total < 18 (valid)"}),
    Case("TC-02", "check_credit_limit", "FR-01", "Total above 18 (SRS scenario 2)", (16, 3), False,
         {"ECP-02": "Credits: total > 18 (valid inputs)"}),
    Case("TC-03", "check_credit_limit", "FR-02", "Current credits below range", (-5, 3), BAD_CUR,
         {"ECP-03": "Current credits < 0 (invalid)"}),
    Case("TC-04", "check_credit_limit", "FR-02", "Current credits above range", (25, 3), BAD_CUR,
         {"ECP-04": "Current credits > 18 (invalid)"}),
    Case("TC-05", "check_credit_limit", "FR-02", "Course credits below range", (10, -2), BAD_CRS,
         {"ECP-05": "Course credits < 1 (invalid)"}),
    Case("TC-06", "check_credit_limit", "FR-02", "Course credits above range", (10, 8), BAD_CRS,
         {"ECP-06": "Course credits > 4 (invalid)"}),
    Case("TC-07", "check_credit_limit", "FR-02", "Both invalid: current is checked first", (-1, 0), BAD_CUR,
         {"ECP-07": "Both arguments invalid -> current error first"}),
    Case("TC-08", "check_credit_limit", "FR-01", "Total exactly 18 (SRS scenario 1)", (15, 3), True,
         {"BVA-01": "Combined total = 18 (upper limit, allowed)"}),
    Case("TC-09", "check_credit_limit", "FR-01", "Total exactly 18 with max course credits", (14, 4), True,
         {"BVA-02": "Combined total = 18 via course credits 4"}),
    Case("TC-10", "check_credit_limit", "FR-01", "Total exactly 18 with min course credits", (17, 1), True,
         {"BVA-03": "Combined total = 18 via course credits 1"}),
    Case("TC-11", "check_credit_limit", "FR-01", "Total 19, just above limit", (15, 4), False,
         {"BVA-04": "Combined total = 19 (just outside)"}),
    Case("TC-12", "check_credit_limit", "FR-01", "Current 18 (max) + 1 credit = 19", (18, 1), False,
         {"BVA-05": "Current credits = 18 (upper boundary, valid input)"}),
    Case("TC-13", "check_credit_limit", "FR-02", "Current credits 19, just above range", (19, 1), BAD_CUR,
         {"BVA-06": "Current credits = 19 (just outside)"}),
    Case("TC-14", "check_credit_limit", "FR-01", "Current 0 (min) + 1 credit", (0, 1), True,
         {"BVA-07": "Current credits = 0 (lower boundary, valid)"}),
    Case("TC-15", "check_credit_limit", "FR-02", "Current credits -1, just below range", (-1, 1), BAD_CUR,
         {"BVA-08": "Current credits = -1 (just outside)"}),
    Case("TC-16", "check_credit_limit", "FR-01", "Course credits 1 (min)", (10, 1), True,
         {"BVA-09": "Course credits = 1 (lower boundary, valid)"}),
    Case("TC-17", "check_credit_limit", "FR-02", "Course credits 0, just below range", (10, 0), BAD_CRS,
         {"BVA-10": "Course credits = 0 (just outside)"}),
    Case("TC-18", "check_credit_limit", "FR-01", "Course credits 4 (max)", (10, 4), True,
         {"BVA-11": "Course credits = 4 (upper boundary, valid)"}),
    Case("TC-19", "check_credit_limit", "FR-02", "Course credits 5, just above range", (10, 5), BAD_CRS,
         {"BVA-12": "Course credits = 5 (just outside)"}),
]

# ---- prerequisites_satisfied(completed, required)  [FR-03, FR-06] ----------
PREREQ_CASES = [
    Case("TC-20", "prerequisites_satisfied", "FR-03", "No prerequisites required", (set(), set()), True,
         {"ECP-08": "Prereq: required set empty"}),
    Case("TC-21", "prerequisites_satisfied", "FR-03", "All prerequisites completed",
         ({"CS101", "MATH101"}, {"CS101", "MATH101"}), True,
         {"ECP-09": "Prereq: all required completed"}),
    Case("TC-22", "prerequisites_satisfied", "FR-03", "Only some prerequisites completed (SRS scenario 3)",
         ({"CS101"}, {"CS101", "MATH101"}), False,
         {"ECP-10": "Prereq: some required completed"}),
    Case("TC-23", "prerequisites_satisfied", "FR-03", "No prerequisite completed", (set(), {"CS101"}), False,
         {"ECP-11": "Prereq: none completed (empty record)"}),
    Case("TC-24", "prerequisites_satisfied", "FR-03", "Completed is a superset of required",
         ({"CS101", "MATH101", "PHY101"}, {"CS101"}), True,
         {"ECP-12": "Prereq: completed superset of required"}),
    Case("TC-25", "prerequisites_satisfied", "FR-03", "Completed non-empty but unrelated to required",
         ({"MATH101"}, {"CS101"}), False,
         {"ECP-13": "Prereq: completed non-empty, none relevant",
          "BVA-14": "Prereq: one prerequisite short of satisfied (size-1 required set)"}),
    Case("TC-26", "prerequisites_satisfied", "FR-06", "Single required prerequisite satisfied",
         ({"CS101"}, {"CS101"}), True,
         {"BVA-13": "Prereq: required set size = 1 (smallest non-empty)"}),
]

# ---- registration_decision(student, course)  [FR-04..FR-09, FR-15] ---------
# args = (student overrides, course overrides)
# Prerequisite-priority combinations use completed_courses=set() and the dues
# combinations use dues=10000 so that a priority check is not masked by an
# unrelated threshold/"any"-vs-"all" defect: the representative input is still
# inside the SRS equivalence class.
BIG_DUES = 10000
FULL = dict(capacity=30, enrolled=30)
OVER = dict(current_credits=16)  # 16 + 3 = 19 > 18
NO_PRE = dict(completed_courses=set())  # required {CS101} not completed
REG = dict(registered_courses={"CS201"})

DECISION_CASES = [
    Case("TC-30", "registration_decision", "FR-04", "Baseline eligible student", ({}, {}), "REGISTERED",
         {"ECP-14": "Dues = 0 (valid)", "ECP-15": "Course not already registered",
          "BVA-15": "Dues = 0 (lower boundary, allowed)",
          "DT-06": "R6: no dues, not registered, prereqs OK, credit OK, seats available"}),
    Case("TC-31", "registration_decision", "FR-08", "Seats available (40 capacity, 24 enrolled)",
         ({}, dict(capacity=40, enrolled=24)), "REGISTERED",
         {"ECP-16": "Availability: enrolled < capacity"}),
    Case("TC-32", "registration_decision", "FR-04", "Large positive dues, otherwise eligible",
         (dict(outstanding_dues=BIG_DUES), {}), "DUES_BLOCK",
         {"ECP-17": "Dues > 0 (valid, blocks)", "DT-01": "R1: dues > 0 (other conditions clear)"}),
    Case("TC-33", "registration_decision", "FR-04", "Dues of Rs. 1 (SRS scenario 4)",
         (dict(outstanding_dues=1), {}), "DUES_BLOCK",
         {"BVA-16": "Dues = 1 (just above 0)"}),
    Case("TC-34", "registration_decision", "FR-15", "Negative dues", (dict(outstanding_dues=-10), {}), BAD_DUES,
         {"ECP-18": "Dues < 0 (invalid)", "DT-E1": "Invalid dues -> ValueError (other fields valid)"}),
    Case("TC-35", "registration_decision", "FR-15", "Dues of -1, just below 0", (dict(outstanding_dues=-1), {}), BAD_DUES,
         {"BVA-17": "Dues = -1 (just outside)"}),
    Case("TC-36", "registration_decision", "FR-05", "Already registered in target course",
         (REG, {}), "ALREADY_REGISTERED",
         {"ECP-19": "Already registered = yes", "DT-02": "R2: registered (dues clear)"}),
    Case("TC-37", "registration_decision", "FR-06", "Prerequisite missing: some completed",
         (dict(completed_courses={"CS101"}), dict(prerequisites={"CS101", "MATH101"})), "PREREQUISITES_MISSING",
         {"ECP-20": "Prereq: some completed (via decision)", "DT-03": "R3: prerequisites missing (higher rules clear)"}),
    Case("TC-38", "registration_decision", "FR-06", "Prerequisite missing: none completed",
         (NO_PRE, {}), "PREREQUISITES_MISSING",
         {"ECP-21": "Prereq: none completed (via decision)"}),
    Case("TC-39", "registration_decision", "FR-07", "16 + 3 credits exceeds 18 (SRS scenario 2)",
         (OVER, {}), "CREDIT_LIMIT",
         {"ECP-22": "Credit limit exceeded", "DT-04": "R4: credit limit exceeded (higher rules clear)"}),
    Case("TC-40", "registration_decision", "FR-08", "Capacity 30, enrolled 30 (SRS scenario 5)",
         ({}, FULL), "WAITLISTED",
         {"ECP-23": "Availability: enrolled = capacity", "BVA-18": "Enrolled = capacity (boundary, full)",
          "DT-05": "R5: seats full (all higher rules clear)"}),
    Case("TC-41", "registration_decision", "FR-08", "Enrolled = capacity - 1", ({}, dict(capacity=30, enrolled=29)),
         "REGISTERED", {"BVA-19": "Enrolled = capacity - 1 (last seat)"}),
    Case("TC-42", "registration_decision", "FR-15", "Enrolled = capacity + 1", ({}, dict(capacity=30, enrolled=31)),
         BAD_CAP, {"BVA-20": "Enrolled = capacity + 1 (just outside)"}),
    Case("TC-43", "registration_decision", "FR-15", "Enrolled greater than capacity (10 vs 11)",
         ({}, dict(capacity=10, enrolled=11)), BAD_CAP,
         {"ECP-24": "Enrollment > capacity (invalid)", "DT-E3": "Invalid enrollment > capacity -> ValueError"}),
    Case("TC-44", "registration_decision", "FR-15", "Capacity 0", ({}, dict(capacity=0, enrolled=0)), BAD_CAP,
         {"ECP-25": "Capacity < 1 (invalid)", "BVA-21": "Capacity = 0 (just below minimum 1)",
          "DT-E2": "Invalid capacity -> ValueError"}),
    Case("TC-45", "registration_decision", "FR-15", "Enrolled = -1", ({}, dict(capacity=30, enrolled=-1)), BAD_CAP,
         {"BVA-22": "Enrolled = -1 (just below 0)"}),
    Case("TC-46", "registration_decision", "FR-08", "Enrolled = 0", ({}, dict(capacity=30, enrolled=0)), "REGISTERED",
         {"BVA-23": "Enrolled = 0 (lower boundary, valid)"}),
    Case("TC-47", "registration_decision", "FR-08", "Minimum capacity 1, empty", ({}, dict(capacity=1, enrolled=0)),
         "REGISTERED", {"BVA-24": "Capacity = 1, enrolled = 0 (min capacity, seat free)"}),
    Case("TC-48", "registration_decision", "FR-08", "Minimum capacity 1, full", ({}, dict(capacity=1, enrolled=1)),
         "WAITLISTED", {"BVA-25": "Capacity = 1, enrolled = 1 (min capacity, full)"}),
    Case("TC-49", "registration_decision", "FR-07", "15 + 3 = 18 credits allowed (SRS scenario 1)",
         (dict(current_credits=15), {}), "REGISTERED",
         {"BVA-26": "Combined credits = 18 via registration"}),
    Case("TC-50", "registration_decision", "FR-07", "Current 18 + 1 credit = 19",
         (dict(current_credits=18), dict(credit_hours=1)), "CREDIT_LIMIT",
         {"BVA-27": "Combined credits = 19 via registration (current at max)"}),
    # ---- priority combinations (FR-09) ----
    Case("TC-51", "registration_decision", "FR-09", "Dues + registered + prereq missing + over limit + full",
         (dict(outstanding_dues=BIG_DUES, **REG, **NO_PRE, **OVER), FULL), "DUES_BLOCK",
         {"DT-07": "P1: dues beat ALL lower conditions"}),
    Case("TC-52", "registration_decision", "FR-09", "Dues + already registered",
         (dict(outstanding_dues=BIG_DUES, **REG), {}), "DUES_BLOCK",
         {"DT-08": "P2: dues vs already registered"}),
    Case("TC-53", "registration_decision", "FR-09", "Dues + prerequisite missing",
         (dict(outstanding_dues=BIG_DUES, **NO_PRE), {}), "DUES_BLOCK",
         {"DT-09": "P3: dues vs missing prerequisite"}),
    Case("TC-54", "registration_decision", "FR-09", "Registered + prereq missing + over limit + full",
         (dict(**REG, **NO_PRE, **OVER), FULL), "ALREADY_REGISTERED",
         {"DT-10": "P4: already registered beats all lower conditions"}),
    Case("TC-55", "registration_decision", "FR-09", "Registered + prerequisite missing",
         (dict(**REG, **NO_PRE), {}), "ALREADY_REGISTERED",
         {"DT-11": "P5: already registered vs missing prerequisite"}),
    Case("TC-56", "registration_decision", "FR-09", "Prereq missing + over limit + full",
         (dict(**NO_PRE, **OVER), FULL), "PREREQUISITES_MISSING",
         {"DT-12": "P6: missing prerequisite beats credit limit and full"}),
    Case("TC-57", "registration_decision", "FR-09", "Prerequisite missing + over limit",
         (dict(**NO_PRE, **OVER), {}), "PREREQUISITES_MISSING",
         {"DT-13": "P7: missing prerequisite vs credit limit"}),
    Case("TC-58", "registration_decision", "FR-09", "Over limit + course full",
         (OVER, FULL), "CREDIT_LIMIT",
         {"DT-14": "P8: credit limit vs full course"}),
    Case("TC-59", "registration_decision", "FR-15", "Dues -1 and capacity 0: dues validated first",
         (dict(outstanding_dues=-1), dict(capacity=0, enrolled=0)), BAD_DUES,
         {"DT-E4": "Validation order: invalid dues before invalid capacity"}),
]

ALL_CASES = CREDIT_CASES + PREREQ_CASES + DECISION_CASES


def _ids(cases):
    return [c.tc for c in cases]


# --------------------------------------------------------------------------
# A4 - function-level tests (ECP / BVA / decision-table derived)
# --------------------------------------------------------------------------
@pytest.mark.parametrize("case", CREDIT_CASES, ids=_ids(CREDIT_CASES))
def test_check_credit_limit(case):
    assert_outcome(lambda: check_credit_limit(*case.args), case.expected)


@pytest.mark.parametrize("case", PREREQ_CASES, ids=_ids(PREREQ_CASES))
def test_prerequisites_satisfied(case):
    completed, required = case.args
    assert_outcome(lambda: prerequisites_satisfied(set(completed), set(required)), case.expected)


@pytest.mark.parametrize("case", DECISION_CASES, ids=_ids(DECISION_CASES))
def test_registration_decision(case):
    s_over, c_over = case.args
    student, course = make_student(**s_over), make_course(**c_over)
    assert_outcome(lambda: registration_decision(student, course), case.expected)


@pytest.mark.parametrize("case", DECISION_CASES, ids=_ids(DECISION_CASES))
def test_registration_decision_does_not_mutate(case):
    """FR-10: the decision function never changes the student or the course."""
    s_over, c_over = case.args
    student, course = make_student(**s_over), make_course(**c_over)
    before = snapshot(student, course)
    try:
        registration_decision(student, course)
    except ValueError:
        pass
    assert snapshot(student, course) == before


# --------------------------------------------------------------------------
# A4 - state-change tests: register_course / withdraw_course (FR-11..FR-14)
# --------------------------------------------------------------------------
def test_ST01_register_success_updates_state():
    """FR-11: REGISTERED adds code, adds credits, increments enrolled by one."""
    student, course = make_student(current_credits=10), make_course(credit_hours=3, enrolled=10)
    assert register_course(student, course) == "REGISTERED"
    assert student.registered_courses == {"CS201"}
    assert student.current_credits == 13
    assert course.enrolled == 11
    assert course.waitlist == []


def test_ST02_register_to_exactly_18_credits():
    """SRS scenario 1: 15 + 3 = 18 is allowed and the state reflects it."""
    student, course = make_student(current_credits=15), make_course(credit_hours=3)
    assert register_course(student, course) == "REGISTERED"
    assert student.current_credits == 18
    assert "CS201" in student.registered_courses


def test_ST03_waitlisted_only_joins_waitlist():
    """FR-12: WAITLISTED appends the ID; credits, courses and enrolled unchanged."""
    student, course = make_student(), make_course(**FULL)
    assert register_course(student, course) == "WAITLISTED"
    assert course.waitlist == ["S001"]
    assert student.registered_courses == set()
    assert student.current_credits == 10
    assert course.enrolled == 30


def test_ST04_waitlist_has_no_duplicates():
    """FR-12: the student ID is appended only if absent."""
    student, course = make_student(), make_course(**FULL)
    register_course(student, course)
    assert register_course(student, course) == "WAITLISTED"
    assert course.waitlist == ["S001"]


def test_ST05_waitlist_keeps_existing_entries_in_order():
    student, course = make_student(), make_course(waitlist=["S900"], **FULL)
    register_course(student, course)
    assert course.waitlist == ["S900", "S001"]


@pytest.mark.parametrize(
    "s_over, c_over, expected",
    [
        (dict(outstanding_dues=BIG_DUES), {}, "DUES_BLOCK"),
        (dict(outstanding_dues=1), {}, "DUES_BLOCK"),
        (REG, {}, "ALREADY_REGISTERED"),
        (NO_PRE, {}, "PREREQUISITES_MISSING"),
        (dict(completed_courses={"CS101"}), dict(prerequisites={"CS101", "MATH101"}), "PREREQUISITES_MISSING"),
        (OVER, {}, "CREDIT_LIMIT"),
    ],
    ids=["ST06-dues", "ST06-dues-rs1", "ST06-registered", "ST06-prereq-none", "ST06-prereq-some", "ST06-credit"],
)
def test_ST06_unsuccessful_registration_changes_nothing(s_over, c_over, expected):
    """FR-12: every unsuccessful outcome other than WAITLISTED is a no-op."""
    student, course = make_student(**s_over), make_course(**c_over)
    before = snapshot(student, course)
    assert register_course(student, course) == expected
    assert snapshot(student, course) == before


@pytest.mark.parametrize(
    "s_over, c_over, message",
    [
        (dict(outstanding_dues=-1), {}, "Invalid dues"),
        ({}, dict(capacity=0, enrolled=0), "Invalid capacity or enrollment"),
        ({}, dict(capacity=5, enrolled=6), "Invalid capacity or enrollment"),
    ],
    ids=["ST07-dues", "ST07-capacity", "ST07-enrolled"],
)
def test_ST07_invalid_data_raises_and_changes_nothing(s_over, c_over, message):
    student, course = make_student(**s_over), make_course(**c_over)
    before = snapshot(student, course)
    with pytest.raises(ValueError, match=f"^{re.escape(message)}$"):
        register_course(student, course)
    assert snapshot(student, course) == before


def test_ST08_register_last_seat_then_next_student_is_waitlisted():
    course = make_course(capacity=1, enrolled=0)
    first, second = make_student(student_id="S001"), make_student(student_id="S002")
    assert register_course(first, course) == "REGISTERED"
    assert course.enrolled == 1
    assert register_course(second, course) == "WAITLISTED"
    assert course.waitlist == ["S002"]
    assert course.enrolled == 1


def test_ST09_second_registration_in_same_course_is_rejected_without_change():
    student, course = make_student(), make_course()
    assert register_course(student, course) == "REGISTERED"
    before = snapshot(student, course)
    assert register_course(student, course) == "ALREADY_REGISTERED"
    assert snapshot(student, course) == before


def test_ST10_withdraw_enrolled_student_updates_state():
    """FR-13 / SRS scenario 6: course removed, credits subtracted, enrolled -1."""
    student = make_student(current_credits=13, registered_courses={"CS201"})
    course = make_course(credit_hours=3, enrolled=11)
    assert withdraw_course(student, course) is True
    assert student.registered_courses == set()
    assert student.current_credits == 10
    assert course.enrolled == 10


def test_ST11_withdraw_not_registered_returns_false_and_changes_nothing():
    """FR-14."""
    student, course = make_student(), make_course()
    before = snapshot(student, course)
    assert withdraw_course(student, course) is False
    assert snapshot(student, course) == before


def test_ST12_withdraw_only_affects_target_course():
    student = make_student(current_credits=14, registered_courses={"CS201", "MATH101"})
    course = make_course(credit_hours=3, enrolled=5)
    assert withdraw_course(student, course) is True
    assert student.registered_courses == {"MATH101"}
    assert student.current_credits == 11
    assert course.enrolled == 4


def test_ST13_register_then_withdraw_restores_original_state():
    student, course = make_student(), make_course()
    before = snapshot(student, course)
    assert register_course(student, course) == "REGISTERED"
    assert withdraw_course(student, course) is True
    assert snapshot(student, course) == before


def test_ST14_withdraw_twice_second_call_is_noop():
    student = make_student(current_credits=13, registered_courses={"CS201"})
    course = make_course(enrolled=11)
    assert withdraw_course(student, course) is True
    before = snapshot(student, course)
    assert withdraw_course(student, course) is False
    assert snapshot(student, course) == before


def test_ST15_withdraw_frees_seat_for_later_registration():
    """FR-13 + FR-08: after a withdrawal the freed seat is really available."""
    course = make_course(capacity=1, enrolled=1)
    holder = make_student(student_id="S001", current_credits=3, registered_courses={"CS201"})
    newcomer = make_student(student_id="S002")
    assert withdraw_course(holder, course) is True
    assert register_course(newcomer, course) == "REGISTERED"
    assert course.enrolled == 1
