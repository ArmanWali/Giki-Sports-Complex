"""
generate_se423_m2_pdf.py - Compiles Milestone 2 Construction Report (SE-423) into an academic PDF.
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
        self.drawString(54, letter[1] - 36, "SE-423 Construction — Milestone 2 Report | GIKI Sports Complex")
        self.setStrokeColor(colors.HexColor("#E5E7EB"))
        self.setLineWidth(0.5)
        self.line(54, letter[1] - 42, letter[0] - 54, letter[1] - 42)
        
        # Footer
        text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(letter[0] - 54, 36, text)
        self.drawString(54, 36, "Team Banana: Arman Wali (Lead), Zohaib Malik, Abdullah Zia")
        self.line(54, 48, letter[0] - 54, 48)
        self.restoreState()

def build_pdf(filename="SE-423 — Software Construction and Development_Milestone_2.pdf"):
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()
    
    PRIMARY = colors.HexColor("#1E3A8A")   # Navy
    SECONDARY = colors.HexColor("#0D9488") # Teal
    TEXT = colors.HexColor("#1F2937")      # Gray-800
    MUTED = colors.HexColor("#4B5563")     # Gray-600
    BG_LIGHT = colors.HexColor("#F9FAFB")  # Gray-50
    BORDER = colors.HexColor("#E5E7EB")    # Gray-200

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=28,
        textColor=PRIMARY,
        spaceAfter=6
    )

    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=12,
        leading=16,
        textColor=SECONDARY,
        spaceAfter=15
    )

    h1_style = ParagraphStyle(
        'Heading1Custom',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=16,
        textColor=PRIMARY,
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'Heading2Custom',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=14,
        textColor=SECONDARY,
        spaceBefore=8,
        spaceAfter=4,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'BodyCustom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11.5,
        textColor=TEXT,
        spaceAfter=5
    )

    code_style = ParagraphStyle(
        'CodeSnippet',
        parent=styles['Code'],
        fontName='Courier',
        fontSize=7.2,
        leading=9.2,
        textColor=colors.HexColor("#1E293B"),
        backColor=BG_LIGHT,
        borderPadding=4,
        spaceAfter=4
    )

    cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=9.5,
        textColor=TEXT
    )

    cell_bold = ParagraphStyle(
        'TableCellBold',
        parent=cell_style,
        fontName='Helvetica-Bold',
        textColor=PRIMARY
    )

    story = []

    # ================= COVER / TITLE BLOCK =================
    story.append(Paragraph("Ghulam Ishaq Khan Institute of Engineering Sciences and Technology", subtitle_style))
    story.append(Paragraph("Milestone 2 Architecture & Construction Report", title_style))
    story.append(Paragraph("SE-423 — Software Construction and Development (Week 10 Deliverable — Weight: 35%)", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=PRIMARY, spaceAfter=10))

    meta_data = [
        [Paragraph("<b>Course Instructor:</b> Dr. Muaz Razzaq", cell_style),
         Paragraph("<b>Submission Date:</b> 22nd November 2026", cell_style)],
        [Paragraph("<b>SE-423 M2 Lead / Integrator:</b> Arman Wali (2023129)", cell_style),
         Paragraph("<b>Repository:</b> github.com/ArmanWali/Giki-Sports-Complex", cell_style)],
        [Paragraph("<b>Verification & CI Lead:</b> Zohaib Malik (2023787)", cell_style),
         Paragraph("<b>Backend Architecture:</b> Go 1.23+ Fiber / PostgreSQL 17 / pgxpool", cell_style)],
        [Paragraph("<b>SE-431 Lead / UI Lead:</b> Abdullah Zia (2023050)", cell_style),
         Paragraph("<b>Frontend Architecture:</b> React 19 / TypeScript / Tailwind CSS v4", cell_style)],
    ]
    t_meta = Table(meta_data, colWidths=[270, 234])
    t_meta.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), BG_LIGHT),
        ('BOX', (0,0), (-1,-1), 0.5, BORDER),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_meta)
    story.append(Spacer(1, 8))

    # ================= 1. WORKING CORE ARCHITECTURE =================
    story.append(Paragraph("1. Working Core Architecture & End-to-End Implementation", h1_style))
    story.append(Paragraph(
        "Per the SE-423 Milestone 2 Rubric (20% weight), the GIKI Sports Complex Management System has been fully constructed as an end-to-end modular monolith. The system comprises a high-performance Go Fiber REST API, a resilient PostgreSQL 17 persistence layer managed via 13 Goose migrations, and a typed React 19/Tailwind v4 web client.",
        body_style
    ))

    arch_data = [
        [Paragraph("Module", cell_bold), Paragraph("Domain Scope & Implementation", cell_bold), Paragraph("Primary Owner", cell_bold), Paragraph("Status", cell_bold)],
        [Paragraph("M1: Authentication & RBAC", cell_style), Paragraph("Argon2id password hashing, server-side sessions (30m idle, 8h absolute), secure HTTP cookies, RBAC matrix.", cell_style), Paragraph("Z. Malik", cell_style), Paragraph("ACTIVE / VERIFIED", cell_style)],
        [Paragraph("M2: Facilities & Scheduling", cell_style), Paragraph("Dynamic weekly schedule matrices, audience rule engine, facility status tracking, and Google Maps live badge.", cell_style), Paragraph("A. Wali", cell_style), Paragraph("ACTIVE / VERIFIED", cell_style)],
        [Paragraph("M3: Padel Court Booking", cell_style), Paragraph("5-minute hold state machine, checkout concurrency protection, ticket generation, and automated hold cleaner.", cell_style), Paragraph("Z. Malik", cell_style), Paragraph("ACTIVE / VERIFIED", cell_style)],
        [Paragraph("M4: Gym Memberships", cell_style), Paragraph("30-day validity intervals [T, T+30d), renewal boundary logic, New/Old gym plans, wallet-backed activation.", cell_style), Paragraph("A. Wali", cell_style), Paragraph("ACTIVE / VERIFIED", cell_style)],
        [Paragraph("M5: Digital Wallet & Payments", cell_style), Paragraph("Double-entry append-only ledger, derived balances (Credits - Debits), deadlock-free row locking, cashier top-ups.", cell_style), Paragraph("Z. Malik", cell_style), Paragraph("ACTIVE / VERIFIED", cell_style)],
        [Paragraph("M6: Announcements & Content", cell_style), Paragraph("Draft-to-published state machine, mandatory title/content validation, photo uploads, role-restricted publishing.", cell_style), Paragraph("A. Zia", cell_style), Paragraph("ACTIVE / VERIFIED", cell_style)],
        [Paragraph("M7: Event Coordination & Audit", cell_style), Paragraph("Administrative audit logs capturing actor, action, target, timestamp, and structured error outcomes.", cell_style), Paragraph("A. Zia", cell_style), Paragraph("ACTIVE / VERIFIED", cell_style)],
    ]
    t_arch = Table(arch_data, colWidths=[105, 265, 60, 74])
    t_arch.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), PRIMARY),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, BORDER),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, BG_LIGHT]),
    ]))
    story.append(t_arch)
    story.append(Spacer(1, 8))

    # ================= 2. DESIGN PATTERNS IMPLEMENTATION =================
    story.append(Paragraph("2. Design Patterns Implemented & Justified (Rubric: 20% Weight)", h1_style))
    story.append(Paragraph(
        "In strict compliance with SE-423 Section 6 and Section 3.1, exactly three design patterns are fully implemented in the running codebase, covering one Creational, one Behavioral, and one Structural pattern:",
        body_style
    ))

    # Pattern 1: Abstract Factory
    story.append(Paragraph("2.1 Abstract Factory Pattern (Creational) — Transactional Repository Factory", h2_style))
    story.append(Paragraph(
        "<b>Stated Problem:</b> During Padel checkout, a booking confirmation and wallet debit must succeed atomically. Creating repositories independently risks them using different connections or uncoordinated transactions, risking partial debits without booking confirmation.<br/>"
        "<b>Solution:</b> <code>TransactionRepositoryFactory</code> interface (implemented by <code>UnitOfWork</code> in <code>internal/padel/unit_of_work.go</code>) acts as an Abstract Factory. It opens a <code>pgx.Tx</code> and manufactures a compatible family of transaction-bound products (<code>Bookings()</code> and <code>Ledger()</code>) sharing the exact same underlying database transaction.<br/>"
        "<b>Rejected Alternative:</b> Passing raw <code>*sql.Tx</code> pointers across package boundaries was rejected because it leaks infrastructure persistence details into core business services.",
        body_style
    ))
    story.append(Paragraph(
        "type TransactionRepositoryFactory interface {\n"
        "    Bookings() BookingRepository\n"
        "    Ledger() LedgerRepository\n"
        "    Commit(ctx context.Context) error\n"
        "    Rollback(ctx context.Context) error\n"
        "}",
        code_style
    ))

    # Pattern 2: Strategy Pattern
    story.append(Paragraph("2.2 Strategy Pattern (Behavioral) — Dynamic Eligibility & Priority Engine", h2_style))
    story.append(Paragraph(
        "<b>Stated Problem:</b> Different campus demographics (students, faculty, varsity teams) have distinct booking priorities and schedule access rules. Hardcoding these rules into schedule queries violates the Open-Closed Principle (OCP) and causes brittle if-else chains.<br/>"
        "<b>Solution:</b> <code>EligibilityPolicy</code> interface in <code>internal/facility/policy.go</code> defines the Strategy. Concrete strategies (<code>StudentPolicy</code>, <code>FacultyPolicy</code>, <code>TeamPolicy</code>, <code>GeneralPolicy</code>) encapsulate access algorithms. <code>PolicyRegistry</code> resolves and executes the appropriate strategy dynamically at runtime.<br/>"
        "<b>Rejected Alternative:</b> A single god-method with conditional branching was rejected because adding new campus groups (e.g., Alumni, Summer Camp) would require modifying and re-testing the core scheduling engine.",
        body_style
    ))
    story.append(Paragraph(
        "type EligibilityPolicy interface {\n"
        "    Audience() string\n"
        "    Evaluate(req AccessRequest) PolicyDecision\n"
        "}\n"
        "// Implemented by StudentPolicy, FacultyPolicy, TeamPolicy, GeneralPolicy in internal/facility/policy.go",
        code_style
    ))

    # Pattern 3: Adapter Pattern
    story.append(Paragraph("2.3 Adapter Pattern (Structural) — JazzCash Payment Gateway Adapter", h2_style))
    story.append(Paragraph(
        "<b>Stated Problem:</b> The digital wallet requires top-ups via external providers like JazzCash. Providers communicate in proprietary formats (e.g., paisas as string, custom response codes '000', HMAC-SHA256 signatures). Directly coupling the ledger to vendor APIs violates Separation of Concerns.<br/>"
        "<b>Solution:</b> <code>PaymentGateway</code> interface in <code>internal/wallet/adapter.go</code> defines the target interface. <code>JazzCashAdapter</code> wraps proprietary JazzCash structures, validates HMAC signatures, converts paisas to integer PKR, and produces the normalized internal domain entity <code>VerifiedPayment</code>. <code>MockPaymentAdapter</code> provides hermetic offline testing.<br/>"
        "<b>Rejected Alternative:</b> Inlining HTTP webhook handling in <code>wallet.Service</code> was rejected because vendor API revisions would require editing core financial ledger logic.",
        body_style
    ))
    story.append(Paragraph(
        "type PaymentGateway interface {\n"
        "    ProviderName() string\n"
        "    InitiateTopUp(ctx context.Context, req TopUpRequest) (*InitiationResponse, error)\n"
        "    VerifyWebhook(ctx context.Context, rawPayload []byte, signature string) (*VerifiedPayment, error)\n"
        "}\n"
        "// Implemented by JazzCashAdapter (adapts pp_TxnRefNo, pp_Amount, pp_ResponseCode) and MockPaymentAdapter",
        code_style
    ))

    story.append(PageBreak())

    # ================= 3. DEFENSIVE CODING & EXCEPTION HANDLING =================
    story.append(Paragraph("3. Defensive Programming & Structured Error Handling (Rubric: 10% Weight)", h1_style))
    story.append(Paragraph(
        "The system enforces strict input validation at all untrusted boundaries and translates errors into structured, typed domain responses without exposing internal database structures or credentials:",
        body_style
    ))
    story.append(Paragraph(
        "• <b>Boundary Input Validation:</b> All DTOs implement comprehensive <code>Validate()</code> methods verifying string lengths, email regex, positive financial amounts, valid UUID formats, and bounded schedule time windows (06:00:00 to 24:00:00).<br/>"
        "• <b>Typed Domain Sentinel Errors:</b> Business packages declare immutable errors (<code>ErrInsufficientFunds</code>, <code>ErrHoldExpired</code>, <code>ErrSlotUnavailable</code>, <code>ErrInvalidSignature</code>, <code>ErrTicketAlreadyCheckedIn</code>).<br/>"
        "• <b>Structured HTTP Mapping:</b> Errors are translated to standard HTTP status codes (400 Bad Request, 401 Unauthorized, 403 Forbidden, 404 Not Found, 409 Conflict, 422 Unprocessable) with sanitized JSON error messages.<br/>"
        "• <b>Credential & Database Isolation:</b> Database connection errors are logged internally with stack traces but returned as generic 500 Internal Server Errors, completely preventing connection string or SQL leakages.",
        body_style
    ))

    # ================= 4. CONCURRENCY & THREAD-SAFETY =================
    story.append(Paragraph("4. Concurrency Architecture & Thread-Safety Strategy (Rubric: 15% Weight)", h1_style))
    story.append(Paragraph(
        "In accordance with SE-423 Minimum Requirement 4, two distinct concurrency mechanisms protect shared state and prevent race conditions:",
        body_style
    ))
    story.append(Paragraph(
        "• <b>Asynchronous Background Cleaner Goroutine (<code>padel/worker.go</code>):</b> <code>HoldCleanerWorker</code> runs on a resilient 30-second ticker in a background goroutine. It scans for expired holds (<code>hold_expires_at <= now()</code>) and automatically resets abandoned court slots back to <code>AVAILABLE</code>. It uses atomic state flags (<code>atomic.Bool</code>) for safe lifecycle control, context timeouts on batch transactions, and mutex guards to prevent overlapping sweep runs.<br/>"
        "• <b>Deadlock-Free Row-Level Locking (<code>wallet/service.go</code>):</b> To prevent race conditions and cyclic AB/BA deadlocks during concurrent multi-user checkouts, wallet account transfers sort sender and receiver UUIDs lexicographically before issuing <code>SELECT ... FOR UPDATE</code>. This guarantees consistent global lock acquisition order across all concurrent goroutines.",
        body_style
    ))

    # ================= 5. CODE QUALITY & SOLID ADHERENCE =================
    story.append(Paragraph("5. Code Quality & SOLID Principles Adherence (Rubric: 15% Weight)", h1_style))
    story.append(Paragraph(
        "The codebase demonstrates explicit adherence to all five SOLID design principles:",
        body_style
    ))

    solid_data = [
        [Paragraph("Principle", cell_bold), Paragraph("Concrete Application in Codebase", cell_bold)],
        [Paragraph("Single Responsibility (SRP)", cell_style), Paragraph("Handlers handle only HTTP parsing and response formatting; Services execute pure business logic; Repositories perform SQL queries. Neither layer leaks responsibilities.", cell_style)],
        [Paragraph("Open-Closed (OCP)", cell_style), Paragraph("New user audience rules are introduced via new EligibilityPolicy strategies without modifying the schedule engine. New gateways attach via PaymentGateway adapters.", cell_style)],
        [Paragraph("Liskov Substitution (LSP)", cell_style), Paragraph("MockPaymentAdapter and JazzCashAdapter can be substituted interchangeably for PaymentGateway without altering WalletService logic.", cell_style)],
        [Paragraph("Interface Segregation (ISP)", cell_style), Paragraph("Small, consumer-owned interfaces: BookingRepository and LedgerRepository are decoupled so consumers depend only on required methods.", cell_style)],
        [Paragraph("Dependency Inversion (DIP)", cell_style), Paragraph("High-level services depend upon abstract interfaces (e.g., PadelService depends on TransactionRepositoryFactory, not pgx.Tx).", cell_style)],
    ]
    t_solid = Table(solid_data, colWidths=[120, 384])
    t_solid.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), PRIMARY),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, BORDER),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, BG_LIGHT]),
    ]))
    story.append(t_solid)
    story.append(Spacer(1, 8))

    # ================= 6. TDD & CI BASELINE =================
    story.append(Paragraph("6. TDD Baseline & Continuous Integration (Rubric: 10% Weight)", h1_style))
    story.append(Paragraph(
        "• <b>Red-Green-Refactor Trail:</b> Preserved across 26 sequential commits on branch <code>main</code>. Unit tests were committed first (e.g., <code>c5cdf06 [RED]</code>) followed by implementation (e.g., <code>c670d0b [GREEN]</code>).<br/>"
        "• <b>Automated Test Suite:</b> 100% of unit tests pass across all packages (<code>auth</code>, <code>authentication</code>, <code>config</code>, <code>content</code>, <code>facility</code>, <code>membership</code>, <code>padel</code>, <code>session</code>, <code>user</code>, <code>wallet</code>).<br/>"
        "• <b>CI Pipeline:</b> <code>.github/workflows/ci.yml</code> triggers on every push and pull request, executing Go module verification, <code>go vet</code>, unit tests, and the TypeScript/Vite production build.",
        body_style
    ))

    # ================= 7. SCM TRACEABILITY & ATTRIBUTION =================
    story.append(Paragraph("7. SCM Contribution & Attribution Matrix (Rubric: 10% Weight)", h1_style))
    
    scm_data = [
        [Paragraph("Team Member", cell_bold), Paragraph("Role & Modules Owned", cell_bold), Paragraph("Commits", cell_bold), Paragraph("Oral Defense Focus", cell_bold)],
        [Paragraph("Arman Wali<br/>(2023129)", cell_style), Paragraph("SE-423 Lead / Integrator<br/>M2: Facilities, Scheduling, Strategy Pattern<br/>M4: Gym Memberships & Validity Math", cell_style), Paragraph("8 commits", cell_style), Paragraph("Strategy Pattern, 30-day membership validity math, database migrations, CI pipeline.", cell_style)],
        [Paragraph("Zohaib Malik<br/>(2023787)", cell_style), Paragraph("Verification & CI Coordinator<br/>M1: Auth & Argon2id, Session Expiry<br/>M3: Padel Booking & Concurrency Worker<br/>M5: Digital Wallet, Abstract Factory, Adapter", cell_style), Paragraph("8 commits", cell_style), Paragraph("Abstract Factory (UnitOfWork), JazzCash Adapter, Hold Cleaner Goroutine, sorted UUID row locking.", cell_style)],
        [Paragraph("Abdullah Zia<br/>(2023050)", cell_style), Paragraph("SE-431 SQA Lead / Frontend Lead<br/>M6: Announcements & Achievements Lifecycle<br/>M7: Audit Trail & Frontend Web App", cell_style), Paragraph("10 commits", cell_style), Paragraph("Draft state machine, React 19 UI modals, Fagan inspection documentation, SQA reports.", cell_style)],
    ]
    t_scm = Table(scm_data, colWidths=[100, 160, 55, 189])
    t_scm.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), PRIMARY),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, BORDER),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, BG_LIGHT]),
    ]))
    story.append(t_scm)
    story.append(Spacer(1, 8))

    # ================= 8. MANDATORY AI USAGE LOG =================
    story.append(Paragraph("8. Mandatory AI Usage Log (Section 9 Compliance)", h1_style))
    story.append(Paragraph(
        "In strict compliance with Section 9 (Academic Integrity & AI Use) of the Joint Project Guidelines, significant AI assistance is disclosed below. All generated material was verified, edited, and defended by team members:",
        body_style
    ))

    ai_data = [
        [Paragraph("Tool Used", cell_bold), Paragraph("Task / Purpose", cell_bold), Paragraph("Adopted Material", cell_bold), Paragraph("Modifications Made & Verification", cell_bold)],
        [Paragraph("Antigravity AI<br/>(Gemini 3.8 Flash)", cell_style), Paragraph("Generate boilerplate for Strategy and Adapter patterns", cell_style), Paragraph("Initial Go interfaces and struct declarations for EligibilityPolicy and PaymentGateway.", cell_style), Paragraph("Tailored access rules to GIKI faculty/student hours; added HMAC-SHA256 signature calculation; verified with 100% passing unit tests.", cell_style)],
        [Paragraph("Antigravity AI<br/>(Gemini 3.8 Flash)", cell_style), Paragraph("Format ReportLab PDF compilation script", cell_style), Paragraph("Table layout and canvas header/footer numbering structure.", cell_style), Paragraph("Replaced mock data with actual project metrics, LOC counts, and commit hashes. Verified exported PDF readability.", cell_style)],
    ]
    t_ai = Table(ai_data, colWidths=[90, 110, 130, 174])
    t_ai.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), PRIMARY),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, BORDER),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, BG_LIGHT]),
    ]))
    story.append(t_ai)

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"✓ Successfully generated {filename}")

if __name__ == '__main__':
    build_pdf()
