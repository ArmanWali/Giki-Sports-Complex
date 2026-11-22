"""
generate_m2_pdf.py - Compiles Milestone 2 SQA Report into an academic PDF.
"""
import sys, os
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            super().showPage()
        super().save()

    def draw_page_number(self, page_count):
        if self._pageNumber == 1:
            return  # Skip cover page
        self.saveState()
        self.setFont("Helvetica", 9)
        self.setFillColor(colors.HexColor("#4B5563"))
        
        # Header
        self.drawString(54, letter[1] - 36, "SE-431 SQA — Milestone 2 Report | GIKI Sports Complex")
        self.setStrokeColor(colors.HexColor("#E5E7EB"))
        self.setLineWidth(0.5)
        self.line(54, letter[1] - 42, letter[0] - 54, letter[1] - 42)
        
        # Footer
        text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(letter[0] - 54, 36, text)
        self.drawString(54, 36, "Team Banana: Abdullah Zia, Arman Wali, Zohaib Malik")
        self.line(54, 48, letter[0] - 54, 48)
        self.restoreState()

def build_pdf(filename="SE-431 — Software Quality Assurance_Milestone_2.pdf"):
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()
    
    # Custom Palette
    PRIMARY = colors.HexColor("#1E3A8A")  # Navy
    SECONDARY = colors.HexColor("#0D9488") # Teal
    TEXT = colors.HexColor("#1F2937")     # Gray-800
    MUTED = colors.HexColor("#4B5563")    # Gray-600
    BG_LIGHT = colors.HexColor("#F9FAFB") # Gray-50
    BORDER = colors.HexColor("#E5E7EB")   # Gray-200

    title_style = ParagraphStyle(
        'CoverTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=30,
        textColor=PRIMARY,
        alignment=1, # Center
        spaceAfter=15
    )
    
    subtitle_style = ParagraphStyle(
        'CoverSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=13,
        leading=18,
        textColor=MUTED,
        alignment=1,
        spaceAfter=25
    )
    
    h1_style = ParagraphStyle(
        'SectionH1',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=20,
        textColor=PRIMARY,
        spaceBefore=14,
        spaceAfter=8,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'SectionH2',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=SECONDARY,
        spaceBefore=10,
        spaceAfter=6,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'BodyDark',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13.5,
        textColor=TEXT,
        spaceAfter=6
    )

    table_cell = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=TEXT
    )

    table_header = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.white
    )

    story = []

    # ================= COVER PAGE =================
    story.append(Spacer(1, 40))
    story.append(Paragraph("Ghulam Ishaq Khan Institute of Engineering Sciences and Technology", subtitle_style))
    story.append(Spacer(1, 20))
    story.append(Paragraph("Milestone 2 Report", title_style))
    story.append(Paragraph("GIKI Sports Complex Management System", subtitle_style))
    story.append(Spacer(1, 15))
    story.append(HRFlowable(width="60%", thickness=2, color=PRIMARY, spaceAfter=25))
    
    story.append(Paragraph("<b>Course:</b> SE-431 — Software Quality Assurance (Week 10)", body_style))
    story.append(Paragraph("<b>Instructor:</b> Dr. Muaz Razzaq", body_style))
    story.append(Paragraph("<b>SE-431 M2 Lead / Integrator:</b> Abdullah Zia (2023050)", body_style))
    story.append(Paragraph("<b>SE-423 M2 Lead / Integrator:</b> Arman Wali (2023129)", body_style))
    story.append(Spacer(1, 15))
    
    team_data = [
        [Paragraph("<b>Student Name</b>", table_header), Paragraph("<b>Reg No.</b>", table_header), Paragraph("<b>Email</b>", table_header), Paragraph("<b>Primary M2 Role</b>", table_header)],
        [Paragraph("Abdullah Zia", table_cell), Paragraph("2023050", table_cell), Paragraph("u2023050@giki.edu.pk", table_cell), Paragraph("SE-431 M2 Lead & Black-Box Test Design", table_cell)],
        [Paragraph("Arman Wali", table_cell), Paragraph("2023129", table_cell), Paragraph("u2023129@giki.edu.pk", table_cell), Paragraph("SE-423 M2 Lead, Fagan Moderator & Defect Tracker", table_cell)],
        [Paragraph("Zohaib Malik", table_cell), Paragraph("2023787", table_cell), Paragraph("u2023787@giki.edu.pk", table_cell), Paragraph("Verification Lead, Static Analysis (QR-14) & Author", table_cell)],
    ]
    t_team = Table(team_data, colWidths=[110, 65, 145, 184])
    t_team.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PRIMARY),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER),
    ]))
    story.append(t_team)
    
    story.append(Spacer(1, 25))
    story.append(Paragraph("<b>Repository:</b> https://github.com/ArmanWali/Giki-Sports-Complex.git", body_style))
    story.append(Paragraph("<b>Date of Submission:</b> 22nd November 2026", body_style))
    story.append(Paragraph("<b>Milestone Weight:</b> 35% of Total Course Grade", body_style))
    story.append(PageBreak())

    # ================= SECTION 1: FAGAN INSPECTION =================
    story.append(Paragraph("1. Formal Fagan-Style Code Inspection Report & CAPA", h1_style))
    story.append(Paragraph(
        "Per the SE-431 M2 Rubric (20% weight), a formal inspection was conducted on core transactional checkout "
        "and ledger code (<code>padel/service.go</code> and <code>wallet/service.go</code>). The inspection met "
        "the standard Fagan threshold with 318 LOC evaluated in a 90-minute session (212 LOC/hour).", body_style
    ))
    story.append(Paragraph("<b>1.1 Inspection Roles & Independent Review</b>", h2_style))
    story.append(Paragraph(
        "To fulfill Project Guidelines Section 3.2, the team included an independent inspector from an external paired team:<br/>"
        "• <b>Moderator:</b> Arman Wali (2023129) — Process governance & verification sign-off<br/>"
        "• <b>Author:</b> Zohaib Malik (2023787) — Target code author & rework implementation<br/>"
        "• <b>Reader:</b> Abdullah Zia (2023050) — Line-by-line semantic walkthrough<br/>"
        "• <b>External Inspector:</b> Danish Ahmad (2023172 — Team 'Campus Facility Booking System') — Independent cross-team review", body_style
    ))
    
    story.append(Paragraph("<b>1.2 Inspection Defect Log & CAPA Register</b>", h2_style))
    defects_data = [
        [Paragraph("<b>ID</b>", table_header), Paragraph("<b>Severity / File</b>", table_header), Paragraph("<b>Defect Description</b>", table_header), Paragraph("<b>Corrective Action (CAPA)</b>", table_header), Paragraph("<b>Status</b>", table_header)],
        [Paragraph("DEF-01", table_cell), Paragraph("Critical<br/>padel/service.go:372", table_cell), Paragraph("<b>Pre-Lock Concurrency Window:</b> Idempotency check prior to row lock allowed concurrent duplicate requests to pass.", table_cell), Paragraph("Implemented <b>Double-Checked Idempotency Locking</b> with second post-lock check. Added 50-contender test.", table_cell), Paragraph("CLOSED", table_cell)],
        [Paragraph("DEF-02", table_cell), Paragraph("Major<br/>padel/service.go:435", table_cell), Paragraph("<b>Clock Drift on Hold Expiry:</b> Nanosecond timestamps rejected valid holds 2ms before database truncation.", table_cell), Paragraph("Normalized comparisons to UTC truncated to seconds (<code>time.Now().UTC().Truncate(time.Second)</code>).", table_cell), Paragraph("CLOSED", table_cell)],
        [Paragraph("DEF-03", table_cell), Paragraph("Major<br/>padel/checkout.go:88", table_cell), Paragraph("<b>Unbounded Retry Loop:</b> Check-in code generator risked infinite loop on random alphanumeric collisions.", table_cell), Paragraph("Capped generation to 10 attempts; returns explicit <code>ErrCodeGenerationFailed</code> on exhaustion.", table_cell), Paragraph("CLOSED", table_cell)],
        [Paragraph("DEF-04", table_cell), Paragraph("Minor<br/>wallet/service.go:124", table_cell), Paragraph("<b>Unchecked Deferred Rollback:</b> Deferred rollback discarded error without audit trace.", table_cell), Paragraph("Added conditional check: ignores <code>ErrTxClosed</code>, logs real unexpected rollback failures.", table_cell), Paragraph("CLOSED", table_cell)],
        [Paragraph("DEF-05", table_cell), Paragraph("Minor<br/>padel/unit_of_work.go", table_cell), Paragraph("<b>Missing Factory Godoc:</b> Unclear transaction lifetime on <code>TransactionRepositoryFactory</code>.", table_cell), Paragraph("Documented Abstract Factory lifecycle and shared transaction contract.", table_cell), Paragraph("CLOSED", table_cell)]
    ]
    t_def = Table(defects_data, colWidths=[40, 95, 150, 165, 54])
    t_def.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PRIMARY),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER),
    ]))
    story.append(t_def)
    story.append(Spacer(1, 10))

    # ================= SECTION 2: STATIC ANALYSIS & SCM =================
    story.append(Paragraph("2. Static Analysis Report & SCM Baseline", h1_style))
    story.append(Paragraph(
        "Per SE-431 Rubric (15% Static Analysis, 10% SCM), real static analysis suites (<code>go vet</code>, "
        "<code>tsc -b</code>) were run with findings triaged into Fixed, Deferred, or Justified False Positives (QR-14).", body_style
    ))
    
    sa_data = [
        [Paragraph("<b>ID</b>", table_header), Paragraph("<b>Component</b>", table_header), Paragraph("<b>Severity</b>", table_header), Paragraph("<b>Defect / Warning Summary</b>", table_header), Paragraph("<b>Triage Status & Disposition</b>", table_header)],
        [Paragraph("SA-01", table_cell), Paragraph("FacilityCard.tsx", table_cell), Paragraph("Critical", table_cell), Paragraph("Undefined icon index access caused React client crashes.", table_cell), Paragraph("<b>FIXED:</b> Enforced strict <code>FacilityIconName</code> union and fallback.", table_cell)],
        [Paragraph("SA-02", table_cell), Paragraph("wallet/service.go", table_cell), Paragraph("High", table_cell), Paragraph("Unordered row locks risked cyclic AB/BA deadlocks.", table_cell), Paragraph("<b>FIXED:</b> Implemented deterministic UUID sorting before locking.", table_cell)],
        [Paragraph("SA-03", table_cell), Paragraph("migrations/00002", table_cell), Paragraph("Medium", table_cell), Paragraph("Redundant location column diverged from UI model.", table_cell), Paragraph("<b>FIXED:</b> Applied migration 00011 to drop location column.", table_cell)],
        [Paragraph("SA-04", table_cell), Paragraph("padel/checkout.go", table_cell), Paragraph("High", table_cell), Paragraph("Replay of checkout without unique key caused double debits.", table_cell), Paragraph("<b>FIXED:</b> Added idempotency database constraints in 00007.", table_cell)],
        [Paragraph("SA-05", table_cell), Paragraph("auth/hasher", table_cell), Paragraph("Low", table_cell), Paragraph("Argon2id startup computation creates brief CPU spike.", table_cell), Paragraph("<b>JUSTIFIED FALSE POSITIVE:</b> OWASP timing attack defense.", table_cell)],
        [Paragraph("SA-06", table_cell), Paragraph("frontend bundle", table_cell), Paragraph("Low", table_cell), Paragraph("Minified vendor JS chunk exceeds 500 kB (509 kB).", table_cell), Paragraph("<b>DEFERRED:</b> Campus LAN load <1.2s; dynamic imports in M3.", table_cell)]
    ]
    t_sa = Table(sa_data, colWidths=[40, 85, 55, 170, 154])
    t_sa.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PRIMARY),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER),
    ]))
    story.append(t_sa)
    story.append(Spacer(1, 10))

    # ================= SECTION 3: IEEE 1012 V&V PLAN =================
    story.append(Paragraph("3. IEEE Std 1012-2016 V&V Plan", h1_style))
    story.append(Paragraph(
        "<b>Verification</b> confirms conformance to development standards (code reviews, unit tests, static analysis), "
        "while <b>Validation</b> confirms end-to-end satisfaction of user objectives (checkout flow, balance integrity, "
        "usability). The Financial Ledger is assigned <b>SIL 3 (High Integrity)</b>.", body_style
    ))
    
    vv_data = [
        [Paragraph("<b>Lifecycle Phase</b>", table_header), Paragraph("<b>V&V Activity</b>", table_header), Paragraph("<b>Type</b>", table_header), Paragraph("<b>Target Req</b>", table_header), Paragraph("<b>Owner & Method</b>", table_header), Paragraph("<b>Evidence</b>", table_header)],
        [Paragraph("Implementation", table_cell), Paragraph("Static Code Vetting", table_cell), Paragraph("Verification", table_cell), Paragraph("QR-14", table_cell), Paragraph("Zohaib Malik / go vet, tsc", table_cell), Paragraph("0 Errors detected", table_cell)],
        [Paragraph("Implementation", table_cell), Paragraph("Fagan Code Inspection", table_cell), Paragraph("Verification", table_cell), Paragraph("SIL 3 (All)", table_cell), Paragraph("Arman Wali / Peer meeting", table_cell), Paragraph("5 DEF closed (docs/m2-fagan)", table_cell)],
        [Paragraph("Implementation", table_cell), Paragraph("Controlled-Clock Unit Tests", table_cell), Paragraph("Verification", table_cell), Paragraph("QR-06, QR-13", table_cell), Paragraph("Arman / Zohaib / Go tests", table_cell), Paragraph("100% passing unit suite", table_cell)],
        [Paragraph("Integration", table_cell), Paragraph("50-Contender Stress Test", table_cell), Paragraph("Validation", table_cell), Paragraph("QR-01, QR-04", table_cell), Paragraph("Zohaib Malik / pgxpool", table_cell), Paragraph("Single booking confirmed", table_cell)],
        [Paragraph("System", table_cell), Paragraph("Double-Entry Ledger Audit", table_cell), Paragraph("Validation", table_cell), Paragraph("QR-03", table_cell), Paragraph("Zohaib Malik / SQL sum", table_cell), Paragraph("Sum(Credits)-Sum(Debits)==Bal", table_cell)],
        [Paragraph("Acceptance", table_cell), Paragraph("3-Minute Booking Usability", table_cell), Paragraph("Validation", table_cell), Paragraph("QR-08", table_cell), Paragraph("Abdullah Zia / User trial", table_cell), Paragraph("Padel booking wizard", table_cell)]
    ]
    t_vv = Table(vv_data, colWidths=[70, 110, 60, 50, 105, 109])
    t_vv.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PRIMARY),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER),
    ]))
    story.append(t_vv)
    story.append(PageBreak())

    # ================= SECTION 4: BLACK-BOX TEST DESIGN =================
    story.append(Paragraph("4. Black-Box Test Design: Equivalence Partitioning & Boundary Value Analysis", h1_style))
    story.append(Paragraph(
        "Formal black-box test designs were constructed for all core inputs (SE-431 Rubric 15% weight). "
        "Equivalence partitions (VEC/IEC) and boundary edge values ($B-1, B, B+1$) are directly mapped to automated suites.", body_style
    ))
    
    bva_data = [
        [Paragraph("<b>Test Case ID</b>", table_header), Paragraph("<b>Subsystem & Parameter</b>", table_header), Paragraph("<b>Boundary Values Tested</b>", table_header), Paragraph("<b>Expected System Behavior</b>", table_header), Paragraph("<b>Linked Req / Suite</b>", table_header)],
        [Paragraph("BVA-SESS-01..03", table_cell), Paragraph("Auth: 30-min Idle Timeout", table_cell), Paragraph("1799s (Valid), 1800s (Boundary Expired), 1801s (Expired)", table_cell), Paragraph("HTTP 200 at 1799s; HTTP 401 at >=1800s with session deletion", table_cell), Paragraph("QR-13 / TestSession_Constants", table_cell)],
        [Paragraph("BVA-PADEL-01..03", table_cell), Paragraph("Padel: 5-minute Hold Window", table_cell), Paragraph("299s (HELD), 300s (Boundary Expired), 301s (AVAILABLE)", table_cell), Paragraph("Checkout succeeds at 299s; rejected at >=300s; slot released", table_cell), Paragraph("QR-01, FR-03 / TestSlot_Effective", table_cell)],
        [Paragraph("BVA-GYM-01..04", table_cell), Paragraph("Gym: 30-day Pass Validity", table_cell), Paragraph("T_start, T_start+30d - 1s (Valid), T_start+30d (Expired)", table_cell), Paragraph("Strict half-open interval [T, T+30d); invalid at exact expiration instant", table_cell), Paragraph("QR-06 / TestPassValidity_QR06", table_cell)],
        [Paragraph("BVA-GYM-05..06", table_cell), Paragraph("Gym: Pass Renewal Timing", table_cell), Paragraph("T_renew < T_exp (Early) vs T_renew > T_exp (Lapsed)", table_cell), Paragraph("Early adds 30d to old expiry; lapsed adds 30d from renewal time", table_cell), Paragraph("QR-06 / TestEarlyRenewal_QR06", table_cell)],
        [Paragraph("BVA-WAL-01..05", table_cell), Paragraph("Wallet: Balances & Debits", table_cell), Paragraph("Amount: 0 PKR (Reject), 1 PKR (Accept); Debit: B-1, B, B+1", table_cell), Paragraph("Zero/negative debits rejected; debit <= balance succeeds; debit > bal rolls back", table_cell), Paragraph("QR-03 / TestPostTransaction_Input", table_cell)]
    ]
    t_bva = Table(bva_data, colWidths=[80, 105, 120, 125, 74])
    t_bva.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PRIMARY),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER),
    ]))
    story.append(t_bva)
    story.append(Spacer(1, 10))

    # ================= SECTION 5: WHITE-BOX TEST DESIGN =================
    story.append(Paragraph("5. White-Box Test Design: Control Flow Graphs & Basis Path Testing", h1_style))
    story.append(Paragraph(
        "Control Flow Graphs (CFG) were drafted and Cyclomatic Complexity $V(G)$ calculated across complex modules "
        "using Graph Theory ($E - N + 2$), Predicate Nodes ($P + 1$), and Planar Regions (SE-431 Rubric 15% weight).", body_style
    ))
    
    cfg_data = [
        [Paragraph("<b>Target Procedure / File</b>", table_header), Paragraph("<b>Nodes / Edges</b>", table_header), Paragraph("<b>Complexity V(G)</b>", table_header), Paragraph("<b>Basis Path Set & Logic Verified</b>", table_header), Paragraph("<b>Coverage Result</b>", table_header)],
        [Paragraph("<code>CalculateRenewalTermWithDuration</code><br/>membership/validity.go", table_cell), Paragraph("8 Nodes<br/>11 Edges", table_cell), Paragraph("<b>V(G) = 4</b><br/>(P=3, R=4)", table_cell), Paragraph("Path 1: duration<=0 fallback<br/>Path 2: first purchase (nil expiry)<br/>Path 3: lapsed pass renewal<br/>Path 4: early contiguous renewal", table_cell), Paragraph("<b>100%</b><br/>(4/4 Basis Paths Passed)", table_cell)],
        [Paragraph("<code>PostTransactionWithResult</code><br/>wallet/service.go", table_cell), Paragraph("10 Nodes<br/>18 Edges", table_cell), Paragraph("<b>V(G) = 10</b><br/>(P=9, R=10)", table_cell), Paragraph("Paths 1-4: Defensive UUID, amount, and string validations<br/>Paths 5-6: Idempotent replay hit vs conflict<br/>Path 7: Insufficient funds rollback<br/>Path 8: Deterministic lock & atomic commit", table_cell), Paragraph("<b>100%</b><br/>(8/8 Basis Paths Passed)", table_cell)],
        [Paragraph("<code>HoldCleanerWorker.loop</code><br/>padel/worker.go", table_cell), Paragraph("6 Nodes<br/>8 Edges", table_cell), Paragraph("<b>V(G) = 4</b><br/>(P=3, R=4)", table_cell), Paragraph("Path 1: Graceful stop signal termination<br/>Path 2: Bounded sweep with released holds<br/>Path 3: Sweep error handling & retry loop", table_cell), Paragraph("<b>100%</b><br/>(3/3 Basis Paths Passed)", table_cell)]
    ]
    t_cfg = Table(cfg_data, colWidths=[120, 65, 75, 175, 69])
    t_cfg.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PRIMARY),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER),
    ]))
    story.append(t_cfg)
    story.append(Spacer(1, 10))

    # ================= SECTION 6: RISK REGISTER & SCM SUMMARY =================
    story.append(Paragraph("6. Risk Governance & SCM Quality-Gate Evidence", h1_style))
    story.append(Paragraph(
        "All 12 risks initiated in Milestone 1 were re-evaluated post-M2. The 18-commit repository history "
        "provides verifiable proof of individual contributions and quality gates.", body_style
    ))
    
    risk_summary = [
        [Paragraph("<b>Risk ID & Description</b>", table_header), Paragraph("<b>Initial Score</b>", table_header), Paragraph("<b>M2 Concrete Architectural Control</b>", table_header), Paragraph("<b>Residual Score & Status</b>", table_header)],
        [Paragraph("R-01: Padel Double Bookings", table_cell), Paragraph("9 (High)", table_cell), Paragraph("Row lock on <code>LockSlotForBooking</code> + unique active booking index.", table_cell), Paragraph("<b>2 (Low) — CONTROLLED</b>", table_cell)],
        [Paragraph("R-02: Partial Checkout Inconsistency", table_cell), Paragraph("6 (High)", table_cell), Paragraph("PostgreSQL transaction bounds debit and booking atomically in UnitOfWork.", table_cell), Paragraph("<b>2 (Low) — CONTROLLED</b>", table_cell)],
        [Paragraph("R-03: Missing Role Checks", table_cell), Paragraph("6 (High)", table_cell), Paragraph("<code>RequireAnyRole</code> middleware & trusted Origin validation on all mutative routes.", table_cell), Paragraph("<b>2 (Low) — CONTROLLED</b>", table_cell)],
        [Paragraph("R-04: Unclear Facility Eligibility", table_cell), Paragraph("6 (High)", table_cell), Paragraph("Strategy pattern (<code>EligibilityPolicy</code>) decouples student/faculty rules.", table_cell), Paragraph("<b>2 (Low) — CONTROLLED</b>", table_cell)],
        [Paragraph("R-07: Integration Overload across 7 Modules", table_cell), Paragraph("9 (High)", table_cell), Paragraph("Modular monolith architecture; clean TDD Red-Green commit pairs.", table_cell), Paragraph("<b>2 (Low) — CONTROLLED</b>", table_cell)]
    ]
    t_risk = Table(risk_summary, colWidths=[110, 60, 224, 110])
    t_risk.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PRIMARY),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER),
    ]))
    story.append(t_risk)
    story.append(Spacer(1, 10))

    story.append(Paragraph("<b>Individual Contribution Summary (18 Commits on main):</b><br/>"
                           "• <b>Arman Wali (6 Commits):</b> Infrastructure, Migrations, Facilities Engine (Strategy Pattern), Gym Memberships, Main Server.<br/>"
                           "• <b>Zohaib Malik (8 Commits):</b> Argon2id Auth, Digital Wallet Ledger (Adapter Pattern), Padel Booking (Abstract Factory & Concurrency), Static Analysis Report (QR-14).<br/>"
                           "• <b>Abdullah Zia (5 Commits):</b> Announcements State Machine, Audit Trails, React 19 Frontend Client, Black-Box Test Design, IEEE 1012 V&V Plan.", body_style))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"✓ PDF successfully generated: {filename}")

if __name__ == "__main__":
    build_pdf()
