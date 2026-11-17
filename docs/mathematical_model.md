
# Mathematical Model — CompuOpti

## 1. Sets

- H: planning days, indexed by t
- Q: qualifications, indexed by k
- S: employees, indexed by i
- J: projects, indexed by j

## 2. Parameters

- Q_i^S: qualifications possessed by employee i
- V_i^S: leave days of employee i
- Q_j^J: qualifications required by project j
- n[j,k]: required person-days for project j and qualification k
- g[j]: financial gain of project j
- c[j]: financial penalty per late day for project j
- d[j]: deadline of project j

## 3. Decision variables

- X[i,j,k,t] ∈ {0,1}: 1 if employee i works on project j using qualification k on day t.
- Y[j] ∈ {0,1}: 1 if project j is selected.
- E[j] ∈ Z: completion day of project j.
- L[j] ∈ Z≥0: number of late days of project j.
- Z[i,j] ∈ {0,1}: 1 if employee i works on project j at least once.
- W[j] ∈ {0,1}: 1 if project j is late.

All projects are mandatory, so Y[j] = 1 for every project.

## 4. Constraints

### C1. At most one assignment per employee per day

For every employee i and day t:

sum(j,k) X[i,j,k,t] ≤ 1

### C2. No work during leave

X[i,j,k,t] = 0 when t belongs to employee i's leave days.

### C3. Qualification compatibility

X[i,j,k,t] = 0 when employee i does not possess qualification k.

In the implementation, variables violating C2 or C3 are not created.

### C4. Required person-days

For every project j and required qualification k:

Y[j] × n[j,k] ≤ sum(i,t) X[i,j,k,t]

sum(i,t) X[i,j,k,t] ≤ n[j,k]

Since every project is mandatory, these inequalities enforce exactly the required number of person-days.

### C5. Mandatory projects

Y[j] = 1 for every project j.

### C6. Employee-project indicator

For every employee i, project j, and valid assignment:

X[i,j,k,t] ≤ Z[i,j]

Z[i,j] ≤ sum(k,t) X[i,j,k,t]

Together, these constraints make Z[i,j] equal to 1 if and only if employee i works on project j.

### C7. Project completion date

For every valid assignment:

E[j] ≥ t × X[i,j,k,t]

Also:

1 ≤ E[j] ≤ h

where h is the last planning day.

The completion date is made equal to the last assignment day by minimizing the sum of completion dates.

### C8. Lateness lower bound

For every project j:

L[j] ≥ E[j] - d[j]

L[j] ≥ 0

### C9. Exact lateness and late-project indicator

Define:

M[j] = max(0, h - d[j])

For every project j:

L[j] ≤ M[j] × W[j]

L[j] ≥ W[j]

L[j] ≤ E[j] - d[j] + M[j](1 - W[j])

These constraints link the late-project indicator W[j] to the number of late days L[j].

## 5. Objective functions

### O1. Maximize financial performance

Maximize:

f1 = sum(j) [g[j]Y[j] - c[j]L[j]]

Because all projects are mandatory, the total gain is constant. This objective therefore minimizes weighted late-day penalties.

### O2. Minimize total project completion days

Minimize:

f2 = sum(j) E[j]

### O3. Minimize employee-project relationships

Minimize:

f3 = sum(i,j) Z[i,j]

This objective reduces the number of different employee-project relationships.

### O4. Minimize the number of late projects

Minimize:

f4 = sum(j) W[j]

## 6. Multi-objective optimization

The four objectives are handled using the epsilon-constraint method.

One objective is optimized at a time while bounds are imposed on the other objectives. The resulting solutions are evaluated to construct the Pareto frontier.

## 7. Important modeling assumptions

- All projects must be completed.
- Every required qualification must receive exactly its required number of person-days.
- An employee can work on at most one project per day.
- Employees cannot work during their leave days.
- Only qualified employees can perform a required qualification.
- Project completion dates are integer planning days.
- Deadlines are expressed in the same day-index convention as the planning horizon.
- There are no precedence or continuity constraints in this formulation.
