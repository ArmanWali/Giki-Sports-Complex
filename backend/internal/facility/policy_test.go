package facility_test

import (
	"testing"
	"time"

	"giki-sports-backend/internal/facility"
)

func TestStrategyPattern_StudentPolicy(t *testing.T) {
	policy := facility.NewStudentPolicy()
	if policy.Audience() != "students" {
		t.Fatalf("expected audience 'students', got '%s'", policy.Audience())
	}

	// 1. Student accessing student slot -> Allowed
	decision := policy.Evaluate(facility.AccessRequest{
		UserRole:       "student",
		FacilityStatus: "active",
		RequestTime:    time.Now(),
	})
	if !decision.Allowed {
		t.Fatalf("expected student to be allowed, got: %+v", decision)
	}

	// 2. Non-student (e.g. external or guest) accessing student slot -> Denied
	decision = policy.Evaluate(facility.AccessRequest{
		UserRole:       "guest",
		FacilityStatus: "active",
		RequestTime:    time.Now(),
	})
	if decision.Allowed {
		t.Fatalf("expected non-student to be denied student-only slot")
	}

	// 3. Admin override -> Allowed
	decision = policy.Evaluate(facility.AccessRequest{
		UserRole:       "sports_director",
		FacilityStatus: "active",
		RequestTime:    time.Now(),
	})
	if !decision.Allowed {
		t.Fatalf("expected admin override to be allowed")
	}

	// 4. Maintenance state overrides role -> Denied
	decision = policy.Evaluate(facility.AccessRequest{
		UserRole:       "student",
		FacilityStatus: "maintenance",
		RequestTime:    time.Now(),
	})
	if decision.Allowed {
		t.Fatalf("expected maintenance facility to deny student")
	}
}

func TestStrategyPattern_FacultyPolicy(t *testing.T) {
	policy := facility.NewFacultyPolicy()
	if policy.Audience() != "faculty" {
		t.Fatalf("expected audience 'faculty', got '%s'", policy.Audience())
	}

	// 1. Faculty accessing faculty priority window -> Allowed
	decision := policy.Evaluate(facility.AccessRequest{
		UserRole:       "faculty",
		FacilityStatus: "active",
		RequestTime:    time.Now(),
	})
	if !decision.Allowed {
		t.Fatalf("expected faculty to be allowed in priority window")
	}

	// 2. Student trying to book faculty priority window -> Denied
	decision = policy.Evaluate(facility.AccessRequest{
		UserRole:       "student",
		FacilityStatus: "active",
		RequestTime:    time.Now(),
	})
	if decision.Allowed {
		t.Fatalf("expected student to be denied in faculty priority window")
	}
}

func TestStrategyPattern_PolicyRegistryAndExtensibility(t *testing.T) {
	registry := facility.NewPolicyRegistry()

	// Evaluate student audience
	dec := registry.Evaluate("students", facility.AccessRequest{
		UserRole:       "student",
		FacilityStatus: "active",
	})
	if !dec.Allowed {
		t.Errorf("expected student strategy to allow student")
	}

	// Evaluate faculty audience with student user -> Denied
	dec = registry.Evaluate("faculty", facility.AccessRequest{
		UserRole:       "student",
		FacilityStatus: "active",
	})
	if dec.Allowed {
		t.Errorf("expected faculty strategy to deny student")
	}

	// Test OCP: register custom community policy at runtime without modifying registry class
	type AlumniPolicy struct{}
	alumni := &mockAlumniPolicy{}
	registry.Register(alumni)

	dec = registry.Evaluate("alumni", facility.AccessRequest{
		UserRole:       "alumni_member",
		FacilityStatus: "active",
	})
	if !dec.Allowed {
		t.Errorf("expected newly registered alumni strategy to be evaluated and allowed")
	}
}

type mockAlumniPolicy struct{}

func (m *mockAlumniPolicy) Audience() string {
	return "alumni"
}

func (m *mockAlumniPolicy) Evaluate(req facility.AccessRequest) facility.PolicyDecision {
	if req.UserRole == "alumni_member" {
		return facility.PolicyDecision{
			Allowed: true,
			Reason:  "Alumni club access granted",
			Policy:  m.Audience(),
		}
	}
	return facility.PolicyDecision{
		Allowed: false,
		Reason:  "Alumni only",
		Policy:  m.Audience(),
	}
}
