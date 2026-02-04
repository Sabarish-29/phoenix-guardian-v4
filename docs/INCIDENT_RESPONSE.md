# Incident Response Plan

## Overview

This document defines the incident response procedures for Phoenix Guardian security and privacy incidents. All security personnel must be familiar with these procedures.

**Plan Owner:** Security Officer  
**Effective Date:** February 2026  
**Last Drill:** [TBD]  
**Next Drill:** 90 days from effective date

---

## Incident Types

### Security Incidents

| Type | Description | Severity |
|------|-------------|----------|
| Unauthorized access | Access to PHI without authorization | HIGH |
| Data breach | PHI disclosed to unauthorized party | CRITICAL |
| Malware infection | System infected with malicious software | HIGH |
| Honeytoken access | Honeytoken record accessed | HIGH |
| Brute force attack | Multiple failed login attempts | MODERATE |
| DoS/DDoS attack | Service availability impacted | MODERATE |
| Phishing | User credentials compromised | HIGH |
| Insider threat | Malicious insider activity | CRITICAL |

### Privacy Incidents

| Type | Description | Severity |
|------|-------------|----------|
| Accidental disclosure | PHI sent to wrong recipient | MODERATE |
| Unauthorized PHI access | Staff accessing records without need | MODERATE |
| Lost/stolen device | Device with PHI lost or stolen | HIGH |
| Misdirected communication | Fax/email to wrong recipient | LOW-MODERATE |
| Improper disposal | PHI not securely destroyed | MODERATE |

---

## Response Team

### Core Team

| Role | Responsibilities | Primary | Backup |
|------|-----------------|---------|--------|
| Incident Commander | Overall coordination | Security Officer | CTO |
| Technical Lead | Technical investigation | Senior Engineer | DevOps Lead |
| Communications | Stakeholder communication | CISO | Legal Counsel |
| Legal | Legal assessment, notifications | Legal Counsel | External Counsel |
| Privacy Officer | HIPAA compliance | Privacy Officer | Compliance Manager |

### Extended Team (as needed)

- HR (for employee-related incidents)
- PR/Communications (for public incidents)
- External forensics (for major breaches)
- Law enforcement liaison

---

## Response Workflow

### Phase 1: Detection (Ongoing)

**Detection Sources:**
- ✅ Automated monitoring via SentinelAgent
- ✅ Honeytoken triggers (immediate alert)
- ✅ Audit log analysis (AuditLogger)
- ✅ User reports (email/phone)
- ✅ External reports (third parties)
- ✅ Vulnerability scanning (scheduled)

**Initial Alert Routing:**
```
CRITICAL → Immediate page to Incident Commander + all core team
HIGH     → Page to Security Officer + Technical Lead
MODERATE → Email to Security Officer, response within 4 hours
LOW      → Ticket creation, response within 1 week
```

### Phase 2: Assessment (< 1 hour for CRITICAL/HIGH)

**Initial Assessment Checklist:**

1. **Verify the incident**
   - [ ] Is this a real security incident?
   - [ ] Is it currently active or historical?

2. **Classify severity**
   - [ ] What type of incident is this?
   - [ ] How many records potentially affected?
   - [ ] Is PHI involved?

3. **Assign Incident Commander**
   - [ ] IC confirmed and briefed
   - [ ] Incident ID assigned

4. **Activate Response Team**
   - [ ] Core team notified
   - [ ] Initial bridge/channel established

**Severity Classification Matrix:**

| Criteria | LOW | MODERATE | HIGH | CRITICAL |
|----------|-----|----------|------|----------|
| Records affected | <10 | 10-100 | 100-500 | >500 |
| PHI exposed | No | Possible | Yes | Confirmed |
| System impact | None | Limited | Significant | Severe |
| Active attack | No | No | Possibly | Yes |

### Phase 3: Containment (< 4 hours for HIGH/CRITICAL)

**Immediate Actions:**

- [ ] Isolate affected systems (if needed)
- [ ] Revoke compromised credentials
- [ ] Block suspicious IP addresses
- [ ] Disable affected accounts
- [ ] Preserve evidence (logs, screenshots)

**Containment Options:**

| Action | When to Use | Owner |
|--------|-------------|-------|
| Account lockout | Compromised credentials | Security |
| IP block | Attack source identified | DevOps |
| System isolation | Malware infection | DevOps |
| Service shutdown | Active data exfiltration | IC (approval required) |
| Network segment isolation | Lateral movement | Network team |

**Evidence Preservation:**

- Export relevant logs immediately
- Take screenshots of active threats
- Document timeline of events
- Preserve affected systems for forensics
- Chain of custody documentation

### Phase 4: Investigation (< 24 hours to initial findings)

**Investigation Goals:**
1. Determine root cause
2. Identify scope of impact
3. Determine if PHI was breached
4. Identify affected individuals
5. Document evidence for legal/regulatory

**Investigation Checklist:**

- [ ] Review audit logs (AuditLogger.generate_audit_report())
- [ ] Analyze security incidents (SecurityIncident table)
- [ ] Review access patterns
- [ ] Interview affected users
- [ ] Examine system logs
- [ ] Check for persistence mechanisms
- [ ] Determine data exfiltration (if any)

**Breach Determination Criteria (HIPAA):**

A breach has occurred if:
1. PHI was acquired, accessed, used, or disclosed
2. In a manner not permitted under HIPAA
3. AND it compromises the security or privacy of the PHI

**Exception (Low Probability of Compromise):**
- Unintentional acquisition by workforce member acting in good faith
- Inadvertent disclosure to authorized person
- Recipient unable to retain the information

### Phase 5: Remediation (Variable timeline)

**Remediation Actions:**

| Issue | Remediation | Owner | Timeline |
|-------|-------------|-------|----------|
| Vulnerabilities | Patch/update | DevOps | 24-72 hours |
| Compromised accounts | Reset, MFA enable | Security | Immediate |
| Malware | Clean/rebuild systems | DevOps | 24-48 hours |
| Policy gaps | Update policies | Security Officer | 1 week |
| Training gaps | Additional training | HR | 2 weeks |

**Verification:**
- [ ] Vulnerability patched and verified
- [ ] No persistence mechanisms remain
- [ ] Monitoring enhanced for similar attacks
- [ ] Access controls reviewed and tightened

### Phase 6: Notification (Per HIPAA Requirements)

**Breach Notification Requirements (45 CFR 164.400-414):**

| Notification To | Timeline | Threshold |
|-----------------|----------|-----------|
| Affected individuals | Within 60 days | Any breach |
| HHS Secretary | Within 60 days | >500 affected |
| HHS Secretary | Annual report | <500 affected |
| Media | Within 60 days | >500 in state/jurisdiction |

**Notification Content (Required Elements):**

1. Description of what happened
2. Types of PHI involved
3. Steps individuals should take
4. What we are doing to investigate
5. What we are doing to mitigate harm
6. Contact information

**Notification Templates:** [Link to templates folder]

### Phase 7: Documentation (< 7 days)

**Incident Report Contents:**

```
INCIDENT REPORT

Incident ID: [Auto-generated UUID]
Date/Time Detected: [Timestamp]
Date/Time Contained: [Timestamp]
Date/Time Resolved: [Timestamp]

Classification:
- Severity: [Critical/High/Moderate/Low]
- Type: [Security/Privacy/Technical]
- PHI Involved: [Yes/No/Unknown]

Summary:
[Brief description of what happened]

Impact Assessment:
- Records affected: [Number]
- Systems affected: [List]
- Users affected: [List]
- Data exposed: [Types]

Root Cause Analysis:
[Detailed technical analysis]

Timeline:
[Chronological event log]

Remediation:
[Actions taken to resolve]

Prevention:
[Future controls to prevent recurrence]

Lessons Learned:
[Key takeaways]

Attachments:
[Evidence, logs, screenshots]
```

---

## Communication Templates

### Internal Alert (CRITICAL)

```
🚨 SECURITY INCIDENT - CRITICAL

Incident ID: [ID]
Time: [Timestamp]
Type: [Type]
Summary: [Brief description]

IMMEDIATE ACTIONS REQUIRED:
1. Join incident bridge: [Link/number]
2. Do not discuss outside secure channels
3. Preserve any evidence

Incident Commander: [Name]
```

### Management Briefing

```
SECURITY INCIDENT BRIEFING

Status: [Active/Contained/Resolved]
Severity: [Level]
Summary: [2-3 sentences]

Impact:
- [Key impact points]

Actions Taken:
- [Key actions]

Next Steps:
- [Upcoming actions]

ETA to Resolution: [Estimate]
```

---

## Playbooks by Incident Type

### Honeytoken Access Playbook

1. **Alert received:** SecurityIncident logged automatically
2. **Verify:** Check security_incidents table for details
3. **Investigate user:** Review all access by user in last 24 hours
4. **Interview:** Contact user to determine intent
5. **Classification:**
   - Legitimate mistake → Training, close as false positive
   - Suspicious behavior → Escalate to HIGH severity
   - Confirmed malicious → Escalate to CRITICAL, involve HR/Legal
6. **Document:** Complete incident report

### Brute Force Attack Playbook

1. **Alert received:** Multiple failed logins from same IP
2. **Block IP:** Add to blocklist
3. **Check targets:** Were any accounts compromised?
4. **Reset passwords:** For targeted accounts (if many attempts)
5. **Analyze:** Is this part of coordinated attack?
6. **Monitor:** Enhanced monitoring for 48 hours
7. **Document:** Log incident and actions

### Data Breach Playbook

1. **Contain:** Stop active exfiltration
2. **Assess:** Determine scope and data types
3. **Legal consult:** Engage legal counsel immediately
4. **Evidence:** Preserve all logs and artifacts
5. **Notify leadership:** Brief executives
6. **Prepare notifications:** Draft individual notices
7. **Regulatory notification:** File with HHS if required
8. **Remediate:** Fix root cause
9. **Document:** Comprehensive incident report

---

## Escalation Contacts

### Internal Contacts

| Role | Name | Phone | Email | Escalation Time |
|------|------|-------|-------|-----------------|
| Security Officer | [TBD] | [TBD] | security@phoenixguardian.example | Immediate |
| CTO | [TBD] | [TBD] | cto@phoenixguardian.example | 15 min |
| CEO | [TBD] | [TBD] | ceo@phoenixguardian.example | 30 min (CRITICAL) |
| Legal Counsel | [TBD] | [TBD] | legal@phoenixguardian.example | 1 hour |

### External Resources

| Resource | Contact | When to Engage |
|----------|---------|----------------|
| FBI Cyber Division | (855) 292-3937 | Confirmed attack, significant breach |
| HHS Breach Portal | https://ocrportal.hhs.gov/ | HIPAA breach notification |
| Forensics Firm | [TBD] | Major breach requiring forensics |
| Legal Firm | [TBD] | Legal guidance needed |
| PR Firm | [TBD] | Public disclosure needed |

---

## Post-Incident Activities

### Lessons Learned Meeting

- Schedule within 1 week of resolution
- All response team members attend
- Document what went well
- Document what could improve
- Assign action items

### Process Improvements

- Update playbooks based on lessons
- Enhance detection capabilities
- Update training materials
- Improve tooling

### Metrics Tracking

| Metric | Target |
|--------|--------|
| Mean Time to Detect (MTTD) | < 1 hour |
| Mean Time to Contain (MTTC) | < 4 hours |
| Mean Time to Resolve (MTTR) | < 24 hours |
| Post-incident review completion | 100% |

---

## Regular Drills

### Drill Schedule

| Drill Type | Frequency | Next Scheduled |
|------------|-----------|----------------|
| Tabletop exercise | Quarterly | [TBD + 90 days] |
| Technical drill | Semi-annually | [TBD + 180 days] |
| Full exercise | Annually | [TBD + 365 days] |

### Drill Scenarios

1. Honeytoken triggered by staff member
2. Ransomware infection on workstation
3. Brute force attack on admin accounts
4. Phishing compromise of physician credentials
5. Insider data exfiltration
6. Third-party vendor breach

---

**Document Version:** 1.0  
**Approved By:** [Security Officer]  
**Effective:** February 2026  
**Review:** Quarterly or after any major incident
