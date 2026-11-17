# Mathematical model — working draft

## Sets
- `H`: planning days
- `Q`: qualifications
- `S`: employees
- `J`: projects

## Parameters
- `Q_i^S`: qualifications possessed by employee `i`
- `V_i^S`: leave days of employee `i`
- `Q_j^J`: qualifications required by project `j`
- `n[j,k]`: required person-days for project `j`, qualification `k`
- `g[j]`: project gain
- `c[j]`: penalty per late day
- `d[j]`: deadline

## Core decision variables (course notation)
- `X[i,j,k,t]` binary: employee `i` works on project `j` using qualification `k` on day `t`
- `Y[j]` binary: project `j` is selected
- `E[j]` integer: completion day
- `L[j]` nonnegative integer: late days

## Candidate extensions
- `Z[i,j]` binary: employee `i` works on project `j` at least once
- `W[j]` binary: selected project `j` is late
- `U[j,t]` binary: project `j` finishes on day `t`
- `T` integer: portfolio makespan

## Professor baseline constraints
1. At most one assignment per employee/day.
2. No work on leave days.
3. Qualification compatibility.
4. Project qualification requirements / project selection.
5. Completion date must be no earlier than every assigned day.
6. Lateness lower bound.

## Proposed strengthening / extensions
- Replace the pair of project requirement inequalities by
  `sum_i,t X[i,j,k,t] = n[j,k] * Y[j]`.
  This prevents any work being assigned to a rejected project. Confirm this is the intended business rule.
- Link `Z[i,j]` to assignments in both directions, so it is 1 iff the employee works on that project.
- Use `U[j,t]` to force a selected project's completion date to be exactly its last assignment day.
- Linearize exact lateness with `W[j]` and a valid tight big-M.
- Add `T >= E[j]` if minimizing portfolio makespan.

## Objective candidates
- Maximize `sum_j (g[j] * Y[j] - c[j] * L[j])`.
- Minimize makespan `T` (if this is the agreed definition of execution time).
- Minimize `sum_i,j Z[i,j]`.
- Minimize `sum_j W[j]`.

## Decisions to confirm before coding
1. Is execution time portfolio makespan, sum of project completion days, or another measure?
2. Does the professor intend rejected projects to receive exactly zero work?
3. Is minimizing employee-project relationships the required workload criterion, or is workload balance also required?
4. Are deadlines within the planning horizon? What should happen to projects with deadlines beyond it?
5. Are all person-days interchangeable, or are there precedence / continuity requirements not represented in the data?

Do not code assumptions silently. Record the agreed choices in `docs/decisions.md`.
