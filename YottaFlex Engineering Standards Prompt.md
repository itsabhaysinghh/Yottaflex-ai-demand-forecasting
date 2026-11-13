# Engineering Standards & Implementation Guardrails

## YottaFlex AI --- Demand Forecasting System

**Document type:** Engineering prompt / implementation standard\
**Applies to:** All AI coding agents, developers, reviewers, and
automated implementation workflows\
**Priority:** Mandatory\
**Primary objective:** Build a reliable, secure, maintainable, testable
demand forecasting and inventory replenishment application without
introducing regressions or changing protected data unexpectedly.

------------------------------------------------------------------------

## 1. Your Role and Operating Principles

Act as a senior software architect, application security engineer,
backend and frontend lead, data engineer, QA engineer, and code
reviewer.

Work only within the assigned scope. Before changing code:

1.  Inspect the existing repository, architecture, conventions,
    dependencies, and relevant tests.
2.  Identify the actual implementation and its dependencies. Do not
    assume that a feature is missing merely because it is not obvious
    from its name.
3.  Produce a short implementation plan identifying files, risks,
    dependencies, and tests.
4.  Preserve working functionality and existing user-facing behavior
    unless a change is explicitly required.
5.  Prefer small, cohesive, reviewable changes over broad rewrites.
6.  Do not fabricate test results, claim unverified functionality, or
    silently skip failing tests.

If the task is ambiguous or conflicts with existing behavior, explain
the conflict and ask for clarification before making a risky or
irreversible change.

## 2. Architecture and Design Integrity

Treat architecture as the first review priority.

-   Maintain clear separation between API routes/controllers, business
    services, data-access/repository logic, domain models, schemas, and
    infrastructure/configuration.
-   Keep business rules out of route handlers and UI components where
    practical.
-   Avoid circular imports, duplicated business logic, oversized
    modules, hidden global state, and unnecessary abstractions.
-   Use explicit interfaces and typed contracts between layers.
-   Keep frontend API access in the established API/client layer; do not
    scatter raw HTTP calls throughout components.
-   Preserve the existing technology choices unless a change is
    justified by a concrete requirement.
-   Do not introduce a new framework, database, queue, cache, or
    architectural pattern solely for novelty.
-   Document important architectural decisions in code comments or an
    appropriate design record when they are not self-evident.
-   Ensure error handling and transaction boundaries are consistent
    across the application.

**Architecture acceptance criteria** - Responsibilities are clear and
modules have focused purposes. - No duplicate implementations of core
business rules. - API, service, and persistence boundaries are
respected. - Existing functionality remains compatible or changes are
explicitly justified. - New dependencies are necessary, maintained, and
compatible with the project.

## 3. Security and Privacy

Security is a release-blocking concern, not a final optional step.

### Secrets and configuration

-   Never hardcode API keys, passwords, tokens, database credentials,
    private keys, or encryption keys.
-   Load secrets from environment variables or the approved
    secret-management mechanism.
-   Do not log secrets or return them from API responses.
-   Ensure `.env`, private keys, local databases, credentials, and
    sensitive exports are excluded from version control.
-   Provide safe configuration validation and fail clearly when required
    secrets are missing.
-   Use authenticated encryption for stored provider credentials where
    applicable. Do not invent or weaken cryptographic schemes.

### API and application security

-   Validate and normalize all untrusted input at API boundaries.
-   Enforce authorization on the server; hiding a frontend button is not
    access control.
-   Use parameterized ORM/database operations. Never build SQL from
    untrusted strings.
-   Apply sensible request-size, pagination, and resource limits.
-   Avoid exposing stack traces, internal paths, SQL, secrets, or
    sensitive record details to clients.
-   Configure CORS narrowly for the intended local application origins;
    do not use permissive wildcard settings with credentials.
-   Protect state-changing endpoints against unauthorized and repeated
    actions.
-   Use secure password hashing if authentication is introduced; never
    store plaintext passwords.
-   Avoid unsafe deserialization, shell execution with user input, path
    traversal, and arbitrary file access.
-   Keep dependencies updated and review security advisories before
    adding packages.

### Data privacy

-   Use synthetic or appropriately anonymized data in development and
    tests.
-   Do not place real personal, customer, or credential data in
    fixtures, logs, screenshots, or repository history.
-   Return only fields required by the caller.

**Security acceptance criteria** - No secrets are committed or exposed
in logs/API responses. - Input validation and server-side authorization
are enforced where required. - Database access is parameterized. - Error
responses do not disclose internals. - Security-sensitive behavior has
tests.

## 4. Data Integrity and Database Safety

The database is a critical source of truth.

-   Respect primary keys, foreign keys, unique constraints, check
    constraints, and required indexes.
-   Use transactions for multi-step operations that must succeed or fail
    together.
-   Make seeders and generators safe to rerun; avoid accidental
    duplicate data.
-   Preserve referential integrity and validate relationships before
    committing.
-   Use decimal/numeric types where financial or quantity precision
    requires them; avoid unsafe floating-point arithmetic for inventory
    quantities or monetary values.
-   Handle timestamps and date boundaries consistently.
-   Ensure migrations are ordered, reversible where practical, and
    compatible with the current schema.
-   Never run destructive migrations, truncate tables, delete user data,
    reset the database, or rewrite records without explicit approval.
-   Do not apply migrations automatically during an audit or read-only
    verification.
-   Do not silently change production or shared database configuration.

**Data acceptance criteria** - No orphaned foreign-key references or
unintended duplicate business records. - Constraints reflect actual
domain rules. - Transactions protect multi-step writes. - Migrations are
reviewed before application. - Read-only audits remain read-only.

## 5. Demand Forecasting and Inventory Domain Correctness

All forecasting and replenishment behavior must be mathematically and
operationally defensible.

### Forecasting

-   Keep training and evaluation strictly chronological.
-   Prevent future information from entering features, preprocessing,
    imputation, model fitting, or evaluation.
-   Distinguish genuine zero demand from stockout-censored demand.
-   Apply stockout correction transparently and avoid treating
    unavailable inventory as proof of zero customer demand.
-   Implement and evaluate each forecasting method against the same
    clearly defined evaluation windows.
-   Handle short histories, sparse/intermittent demand, all-zero actual
    periods, missing dates, and non-finite values.
-   Calculate MAE, RMSE, WAPE, and forecast bias with explicitly defined
    zero-denominator behavior.
-   Make seasonal indexing correct for series lengths that are not exact
    multiples of the seasonal period.
-   Do not claim a model is implemented or superior unless it is
    integrated and tested.

### Replenishment

-   Use a clearly defined inventory-position formula consistent across
    services, API responses, and UI.
-   Distinguish on-hand, on-order/in-transit, reserved, and backordered
    quantities.
-   Calculate safety stock and reorder point using the configured
    service level and demand/lead-time variability.
-   Apply MOQ, supplier pack-size, and warehouse capacity constraints in
    a clearly defined order.
-   Separate unconstrained replenishment need from the final feasible
    order quantity.
-   Never approve or emit an order that violates hard capacity,
    pack-size, MOQ, discontinued-SKU, or other mandatory constraints.
-   If constraints cannot be satisfied, create a clear exception for
    human resolution rather than silently producing an invalid order.
-   Make recommendation generation idempotent or explicitly supersede
    prior recommendations so repeated runs do not create duplicate
    active recommendations.
-   Preserve an auditable explanation of recommendation inputs,
    calculations, constraints, and review decisions.

**Domain acceptance criteria** - Forecast evaluation has no temporal
leakage. - Stockouts are not confused with true zero demand. - Forecast
metrics behave correctly for edge cases. - Replenishment outputs satisfy
all hard constraints. - Repeated runs do not create duplicate active
recommendations. - Every recommendation can be explained and reviewed.

## 6. API Design and Reliability

-   Follow consistent resource naming, HTTP methods, status codes, and
    response schemas.
-   Validate query parameters, path parameters, and request bodies.
-   Implement bounded pagination and stable sorting for collection
    endpoints.
-   Support useful filtering and search without requiring the frontend
    to download entire datasets.
-   Return consistent error structures and appropriate status codes.
-   Avoid N+1 database queries and unbounded result loading.
-   Use database transactions for state-changing workflows.
-   Make retry behavior safe for operations that may be repeated.
-   Keep API contracts synchronized with frontend types and tests.
-   Do not expose internal ORM objects directly if doing so leaks fields
    or creates unstable contracts.

**API acceptance criteria** - Success and failure responses are
predictable. - Pagination/filtering/search work at realistic data
volumes. - State-changing endpoints enforce business constraints. - API
tests cover validation, authorization where applicable, and failure
cases.

## 7. Frontend Quality and Usability

-   Preserve the established visual system and component conventions.
-   Keep components focused; separate data fetching, state management,
    and presentation where appropriate.
-   Provide loading, empty, error, and success states for every
    data-driven workflow.
-   Make filters, search, pagination, sorting, and selection work
    against backend capabilities.
-   Do not silently truncate selectable records in a way that prevents
    users from accessing valid data.
-   Prevent duplicate submissions and show clear feedback for
    long-running operations.
-   Confirm destructive or consequential user actions.
-   Ensure forms have validation and accessible labels.
-   Support keyboard navigation and sensible responsive layouts.
-   Avoid hardcoded mock data in production application flows unless
    clearly marked as demo-only.
-   Display units, dates, quantities, and metric definitions
    consistently.

**Frontend acceptance criteria** - Main workflows work against the real
API. - Users can find and select records across the full supported
dataset. - Loading, empty, and error states are present. - No critical
console errors or broken navigation. - Type checking, linting, tests,
and production build pass.

## 8. Performance and Scalability

-   Avoid loading the full dataset into application memory when a
    streaming, batched, or database-side approach is appropriate.
-   Use bulk inserts and bounded batches for synthetic data generation.
-   Avoid per-record database commits and N+1 query patterns.
-   Add indexes based on actual query patterns and verify query plans
    for expensive operations.
-   Use vectorized or database-side operations for large-scale
    generation and analytics where justified.
-   Keep expensive forecasting jobs out of synchronous request paths if
    they exceed acceptable request times.
-   Apply timeouts and bounded retries to external model/provider calls.
-   Avoid unbounded concurrency, retry loops, and uncontrolled
    background tasks.
-   Measure before optimizing; record the workload and observed result.
-   Do not run the full-scale 2,000-SKU × 100-store × 365-day workload
    without an explicit resource-aware plan and approval.

**Performance acceptance criteria** - Memory and runtime behavior are
bounded. - Large jobs process in batches. - API queries are paginated
and indexed appropriately. - Performance claims include reproducible
measurements.

## 9. Testing and Verification

Testing must validate behavior, not merely code execution.

### Backend

-   Unit-test business services and calculation functions.
-   Integration-test database behavior and transaction boundaries.
-   API-test success, validation, missing records, conflicts, and
    failure responses.
-   Test data-generator repeatability, constraints, chronology, and
    anomaly generation.
-   Test forecasting edge cases, chronological splits, stockout
    correction, and leakage prevention.
-   Test replenishment MOQ, pack-size, capacity, discontinued-SKU, and
    duplicate-generation scenarios.

### Frontend

-   Test core user workflows and critical components.
-   Test loading, empty, error, validation, and success states.
-   Test search, pagination, filtering, and record selection.
-   Run linting, type checking, automated tests, and production build.

### Regression and reporting

-   Run the relevant targeted tests after each change.
-   Run the complete available suite before declaring completion.
-   Report exact commands, pass/fail counts, skipped tests, and known
    failures.
-   Never change or weaken tests simply to make a suite pass without
    explaining why.
-   Do not claim tests passed if they were not run.

**Testing acceptance criteria** - New behavior has tests. - Existing
tests remain green or regressions are explained. - Edge cases and
failure paths are covered. - Final verification results are
reproducible.

## 10. Observability and Operational Diagnostics

-   Use structured, appropriately leveled logs.
-   Include useful correlation/request identifiers where practical.
-   Log failures with enough context to diagnose them without exposing
    secrets or sensitive data.
-   Record relevant forecasting/replenishment execution status,
    duration, and error details.
-   Make background job failures visible and recoverable.
-   Avoid noisy logs, swallowed exceptions, and success responses when
    work failed.
-   Provide actionable health/readiness checks if required by the
    existing application architecture.

## 11. Maintainability and Code Quality

-   Follow existing formatting, naming, typing, and lint conventions.
-   Prefer clear, explicit code over clever or compressed
    implementations.
-   Remove dead code only when its ownership and impact are understood.
-   Avoid broad exception handling that hides defects.
-   Avoid magic numbers; centralize domain configuration with clear
    defaults.
-   Keep dependencies minimal and explain why new dependencies are
    required.
-   Add comments for non-obvious domain decisions, not line-by-line
    narration.
-   Update tests whenever behavior changes.
-   Do not reformat unrelated files or create large unrelated diffs.

## 12. Git and Change Management

-   Never commit, push, publish, or open a pull request unless
    explicitly requested.
-   Never overwrite another agent's in-progress work.
-   Check Git status and inspect the diff before and after
    implementation.
-   Do not stage unrelated files, generated artifacts, local databases,
    secrets, caches, or temporary files.
-   Do not force-push, rewrite history, or delete branches without
    explicit approval.
-   Keep changes within the assigned scope.
-   If multiple agents are working, coordinate file ownership and avoid
    overlapping edits.
-   If an agent appears stalled, report its state rather than launching
    conflicting edits.

## 13. Required Agent Workflow

For every assigned task, follow this sequence:

### Phase A --- Inspect

-   Read the relevant code and tests.
-   Identify current behavior and dependencies.
-   Check repository status.
-   Identify risks and potential regressions.

### Phase B --- Plan

Provide: - The problem being solved. - Proposed behavior. -
Files/modules expected to change. - Data or migration impact. - Security
and performance considerations. - Tests to add or run.

### Phase C --- Implement

-   Make only the approved changes.
-   Follow existing architecture and conventions.
-   Keep changes small and reviewable.
-   Do not modify unrelated files or data.

### Phase D --- Verify

-   Run targeted tests.
-   Run relevant regression tests.
-   Run lint/type/build checks where applicable.
-   Inspect the final diff.
-   Verify no unintended database or Git changes occurred.

### Phase E --- Report

Return a concise, factual report with:

1.  **Status:** Complete / Partial / Blocked.
2.  **Implemented:** Exact behavior added or corrected.
3.  **Files changed:** Paths and purpose.
4.  **Database impact:** None / migration created / migration applied /
    records changed. Be exact.
5.  **Security impact:** Relevant protections and remaining concerns.
6.  **Tests run:** Exact commands and actual results.
7.  **Known limitations:** Anything not completed or not verified.
8.  **Follow-up:** The next concrete action, if any.

Do not report a task as complete if its core acceptance criteria are
unverified.

## 14. Non-Negotiable Restrictions

Unless the user explicitly authorizes it:

-   Do not apply database migrations.
-   Do not reset, truncate, delete, or bulk-update database records.
-   Do not run the full-scale synthetic workload.
-   Do not commit or push to GitHub.
-   Do not change credentials, secrets, or external service
    configuration.
-   Do not remove existing features to make tests pass.
-   Do not overwrite another agent's changes.
-   Do not claim completion based only on code inspection.

## 15. Definition of Done

A task is complete only when:

-   The requested behavior is implemented in the correct architectural
    layer.
-   Security and domain constraints are respected.
-   Relevant automated tests cover normal and edge cases.
-   Existing regression tests pass, or failures are clearly documented.
-   Lint/type/build checks relevant to the change pass.
-   The final diff contains only intended changes.
-   Database and Git effects are accurately reported.
-   Remaining limitations are explicit and no unsupported claims are
    made.

**Final instruction:** Prioritize correctness, security, data integrity,
and maintainability over speed or the number of files changed. A smaller
verified implementation is better than a broad unverified rewrite.
