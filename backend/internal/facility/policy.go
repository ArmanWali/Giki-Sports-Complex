package facility

import (
	"strings"
	"time"
)

// PolicyDecision represents the evaluated outcome of an eligibility strategy check.
type PolicyDecision struct {
	Allowed bool   `json:"allowed"`
	Reason  string `json:"reason"`
	Policy  string `json:"policy"`
}

// AccessRequest contains contextual parameters provided to an EligibilityPolicy.
type AccessRequest struct {
	UserRole           string    `json:"userRole"`           // "student", "faculty", "team_member", "sports_director", "super_admin"
	IsMembershipActive bool      `json:"isMembershipActive"` // whether user holds an active membership pass
	RequestTime        time.Time `json:"requestTime"`        // timestamp of the intended facility usage
	FacilityStatus     string    `json:"facilityStatus"`     // "active", "maintenance", "closed"
}

// EligibilityPolicy defines the behavioral Strategy pattern interface (SE-423 §6.2).
// Each concrete strategy encapsulates the eligibility and priority rules for a specific audience.
type EligibilityPolicy interface {
	Audience() string
	Evaluate(req AccessRequest) PolicyDecision
}

// StudentPolicy implements EligibilityPolicy for general student facility access.
type StudentPolicy struct{}

func NewStudentPolicy() *StudentPolicy {
	return &StudentPolicy{}
}

func (p *StudentPolicy) Audience() string {
	return "students"
}

func (p *StudentPolicy) Evaluate(req AccessRequest) PolicyDecision {
	if strings.ToLower(req.FacilityStatus) == "maintenance" || strings.ToLower(req.FacilityStatus) == "closed" {
		return PolicyDecision{
			Allowed: false,
			Reason:  "Facility is currently under maintenance or temporarily closed",
			Policy:  p.Audience(),
		}
	}

	role := strings.ToLower(req.UserRole)
	if role == "sports_director" || role == "super_admin" {
		return PolicyDecision{
			Allowed: true,
			Reason:  "Administrative override permitted",
			Policy:  p.Audience(),
		}
	}

	if role != "student" {
		return PolicyDecision{
			Allowed: false,
			Reason:  "Slot is reserved exclusively for students",
			Policy:  p.Audience(),
		}
	}

	return PolicyDecision{
		Allowed: true,
		Reason:  "Student access authorized for this window",
		Policy:  p.Audience(),
	}
}

// FacultyPolicy implements EligibilityPolicy for dedicated faculty priority windows.
type FacultyPolicy struct{}

func NewFacultyPolicy() *FacultyPolicy {
	return &FacultyPolicy{}
}

func (p *FacultyPolicy) Audience() string {
	return "faculty"
}

func (p *FacultyPolicy) Evaluate(req AccessRequest) PolicyDecision {
	if strings.ToLower(req.FacilityStatus) == "maintenance" || strings.ToLower(req.FacilityStatus) == "closed" {
		return PolicyDecision{
			Allowed: false,
			Reason:  "Facility is currently offline for maintenance",
			Policy:  p.Audience(),
		}
	}

	role := strings.ToLower(req.UserRole)
	if role == "faculty" || role == "sports_director" || role == "super_admin" {
		return PolicyDecision{
			Allowed: true,
			Reason:  "Faculty priority window access granted",
			Policy:  p.Audience(),
		}
	}

	return PolicyDecision{
		Allowed: false,
		Reason:  "Priority slot reserved exclusively for faculty members",
		Policy:  p.Audience(),
	}
}

// TeamPolicy implements EligibilityPolicy for varsity athletic squad training windows.
type TeamPolicy struct{}

func NewTeamPolicy() *TeamPolicy {
	return &TeamPolicy{}
}

func (p *TeamPolicy) Audience() string {
	return "team"
}

func (p *TeamPolicy) Evaluate(req AccessRequest) PolicyDecision {
	if strings.ToLower(req.FacilityStatus) == "maintenance" || strings.ToLower(req.FacilityStatus) == "closed" {
		return PolicyDecision{
			Allowed: false,
			Reason:  "Facility is unavailable during scheduled maintenance",
			Policy:  p.Audience(),
		}
	}

	role := strings.ToLower(req.UserRole)
	if role == "team_member" || role == "sports_director" || role == "super_admin" {
		return PolicyDecision{
			Allowed: true,
			Reason:  "Varsity team training reservation verified",
			Policy:  p.Audience(),
		}
	}

	return PolicyDecision{
		Allowed: false,
		Reason:  "Facility slot is exclusively reserved for GIKI varsity team training",
		Policy:  p.Audience(),
	}
}

// GeneralPolicy implements EligibilityPolicy for open campus recreation windows.
type GeneralPolicy struct{}

func NewGeneralPolicy() *GeneralPolicy {
	return &GeneralPolicy{}
}

func (p *GeneralPolicy) Audience() string {
	return "general"
}

func (p *GeneralPolicy) Evaluate(req AccessRequest) PolicyDecision {
	if strings.ToLower(req.FacilityStatus) == "maintenance" || strings.ToLower(req.FacilityStatus) == "closed" {
		return PolicyDecision{
			Allowed: false,
			Reason:  "Facility is currently offline",
			Policy:  p.Audience(),
		}
	}

	role := strings.ToLower(req.UserRole)
	if role == "" || role == "anonymous" {
		return PolicyDecision{
			Allowed: false,
			Reason:  "Authentication required for facility access",
			Policy:  p.Audience(),
		}
	}

	return PolicyDecision{
		Allowed: true,
		Reason:  "General university access permitted",
		Policy:  p.Audience(),
	}
}

// PolicyRegistry acts as the Strategy Context/Registry, selecting the appropriate Strategy at runtime.
type PolicyRegistry struct {
	strategies map[string]EligibilityPolicy
}

// NewPolicyRegistry instantiates a registry pre-loaded with default concrete policies.
func NewPolicyRegistry() *PolicyRegistry {
	r := &PolicyRegistry{
		strategies: make(map[string]EligibilityPolicy),
	}
	r.Register(NewStudentPolicy())
	r.Register(NewFacultyPolicy())
	r.Register(NewTeamPolicy())
	r.Register(NewGeneralPolicy())
	return r
}

// Register dynamically attaches a new EligibilityPolicy (Open-Closed Principle).
func (r *PolicyRegistry) Register(policy EligibilityPolicy) {
	if policy == nil {
		return
	}
	r.strategies[strings.ToLower(policy.Audience())] = policy
}

// Evaluate resolves the registered Strategy for the given audience and evaluates access.
func (r *PolicyRegistry) Evaluate(audience string, req AccessRequest) PolicyDecision {
	key := strings.ToLower(strings.TrimSpace(audience))
	if key == "" {
		key = "general"
	}

	strategy, exists := r.strategies[key]
	if !exists {
		// Fallback to GeneralPolicy if unknown audience tag
		strategy = r.strategies["general"]
	}

	return strategy.Evaluate(req)
}
