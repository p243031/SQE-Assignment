import pytest
from registration import Student, Course, registration_decision, check_credit_limit, prerequisites_satisfied

def test_wb_negative_dues_exception():
    """Target: Path 1 (ValueError for negative outstanding dues)."""
    student = Student(student_id="S1", outstanding_dues=-10)
    course = Course(code="CS101", credit_hours=3, capacity=30, enrolled=10)
    with pytest.raises(ValueError, match="Invalid dues"):
        registration_decision(student, course)

def test_wb_invalid_capacity_and_enrollment():
    """Target: Path 2 (ValueError for invalid capacity or malformed enrollment)."""
    student = Student(student_id="S1", outstanding_dues=0)
    
    # Capacity < 1 exception
    course_bad_cap = Course(code="CS101", credit_hours=3, capacity=0, enrolled=0)
    with pytest.raises(ValueError, match="Invalid capacity or enrollment"):
        registration_decision(student, course_bad_cap)
        
    # Enrolled > capacity exception
    course_bad_enr = Course(code="CS101", credit_hours=3, capacity=20, enrolled=25)
    with pytest.raises(ValueError, match="Invalid capacity or enrollment"):
        registration_decision(student, course_bad_enr)

def test_wb_dues_block():
    """Target: Path 3 (DUES_BLOCK branch when outstanding dues > 1000)."""
    student = Student(student_id="S1", outstanding_dues=1500)
    course = Course(code="CS101", credit_hours=3, capacity=30, enrolled=10)
    assert registration_decision(student, course) == "DUES_BLOCK"

def test_wb_already_registered():
    """Target: Path 4 (ALREADY_REGISTERED branch)."""
    student = Student(student_id="S1", registered_courses={"CS101"})
    course = Course(code="CS101", credit_hours=3, capacity=30, enrolled=10)
    assert registration_decision(student, course) == "ALREADY_REGISTERED"

def test_wb_prerequisites_missing():
    """Target: Path 5 (PREREQUISITES_MISSING branch)."""
    student = Student(student_id="S1", completed_courses={"MATH101"})
    course = Course(code="CS102", credit_hours=3, capacity=30, enrolled=10, prerequisites={"CS101"})
    assert registration_decision(student, course) == "PREREQUISITES_MISSING"

def test_wb_credit_limit():
    """Target: Path 6 (CREDIT_LIMIT branch using check_credit_limit)."""
    student = Student(student_id="S1", current_credits=16)
    course = Course(code="CS103", credit_hours=3, capacity=30, enrolled=10)
    assert registration_decision(student, course) == "CREDIT_LIMIT"

def test_wb_waitlisted():
    """Target: Path 7 (WAITLISTED branch when enrolled > capacity)."""
    student = Student(student_id="S1")
    course = Course(code="CS104", credit_hours=3, capacity=20, enrolled=21)
    assert registration_decision(student, course) == "WAITLISTED"

def test_wb_successful_registration():
    """Target: Path 8 (Standard REGISTERED branch)."""
    student = Student(student_id="S1", current_credits=5)
    course = Course(code="CS105", credit_hours=3, capacity=30, enrolled=10)
    assert registration_decision(student, course) == "REGISTERED"

def test_wb_helper_functions_direct():
    """Target: Direct structural execution of helper methods for 100% coverage."""
    with pytest.raises(ValueError):
        check_credit_limit(-1, 3)
    with pytest.raises(ValueError):
        check_credit_limit(5, 5)
        
    assert prerequisites_satisfied({"CS101"}, set()) is True