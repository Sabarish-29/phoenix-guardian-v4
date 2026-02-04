# Security Policies

## Overview

This document defines security policies for Phoenix Guardian, a HIPAA-compliant healthcare AI platform. All personnel with system access must comply with these policies.

**Effective Date:** February 2026  
**Review Cycle:** Annually  
**Owner:** Security Officer

---

## Access Control Policy

### User Authentication

| Requirement | Policy | Implementation |
|-------------|--------|----------------|
| Unique credentials | No shared accounts | Email-based user IDs |
| Password complexity | 8+ chars, mixed case, numbers | Enforced at registration |
| Password storage | Secure hash | bcrypt (cost factor 12) |
| Password expiration | 90 days | Enforced by system |
| Password history | Cannot reuse last 5 | Stored hash comparison |
| Failed login lockout | 5 attempts = 15 min lockout | Auto-lockout with alert |
| Session timeout | 15 minutes inactivity | JWT expiration |

### Authorization Levels

| Role | Permissions | Use Case |
|------|-------------|----------|
| **Patient** | View own records only | Patient portal access |
| **Nurse** | View/update assigned patients | Bedside documentation |
| **Physician** | Full clinical access | Clinical decision making |
| **Admin** | System configuration + user management | IT administration |
| **Security Officer** | Audit access + incident management | Security oversight |

### Minimum Necessary Principle

- Users receive only permissions required for job function
- Access reviewed quarterly
- Elevated privileges require supervisor approval
- Temporary access expires automatically

---

## Data Protection Policy

### Encryption

| Data State | Encryption | Algorithm |
|------------|------------|-----------|
| At Rest | Required | Fernet (AES-256) |
| In Transit | Required | TLS 1.3 minimum |
| Backups | Required | AES-256-GCM |
| Mobile | Required | Full disk encryption |

### PII/PHI Fields Requiring Encryption

- Social Security Number (SSN)
- Phone number
- Email address
- Physical address
- Date of birth
- Medical record number
- Diagnosis codes
- Medication lists
- Lab results
- Insurance information

### Data Retention

| Data Type | Retention Period | Deletion Method |
|-----------|-----------------|-----------------|
| Active patient records | Indefinite | N/A |
| Inactive patient records | 7 years minimum | Secure overwrite |
| Audit logs | 7 years | Archive, then secure delete |
| Security incidents | 7 years | Archive, then secure delete |
| Session data | 24 hours | Auto-purge |
| Temporary files | 1 hour | Auto-purge |

### Secure Deletion

- Standard: DoD 5220.22-M (3-pass overwrite)
- Sensitive: NIST 800-88 (cryptographic erase)
- Certificate of destruction required
- Logged in disposal manifest

---

## Incident Response Policy

### Detection Methods

| Method | Description | Owner |
|--------|-------------|-------|
| Automated monitoring | SentinelAgent 24/7 | System |
| Audit log analysis | Daily review | Security team |
| Honeytoken triggers | Immediate alert | System |
| User reports | Reported issues | All users |
| Vulnerability scanning | Weekly automated | DevOps |

### Incident Classification

| Severity | Definition | Examples |
|----------|------------|----------|
| **Critical** | PHI breach >500 records, system compromise | Data exfiltration, ransomware |
| **High** | Unauthorized access, honeytoken trigger | Insider threat, brute force |
| **Moderate** | Failed security control, policy violation | Excessive access, weak password |
| **Low** | Minor violation, informational | After-hours access, failed login |

### Response Procedure

1. **Identify:** Classify severity (Low/Mod/High/Critical)
2. **Contain:** Isolate affected systems
3. **Investigate:** Root cause analysis
4. **Remediate:** Fix vulnerability
5. **Report:** Document in security_incidents table
6. **Review:** Post-incident analysis

### Response Times

| Severity | Initial Response | Resolution Target |
|----------|-----------------|-------------------|
| Critical | < 1 hour | 24 hours |
| High | < 4 hours | 72 hours |
| Moderate | < 24 hours | 1 week |
| Low | < 1 week | 30 days |

---

## Acceptable Use Policy

### Permitted Uses

✅ Clinical documentation  
✅ Patient care activities  
✅ Authorized research (with IRB approval)  
✅ Quality improvement  
✅ System administration (authorized personnel)  
✅ Security monitoring (security team)

### Prohibited Uses

❌ Unauthorized PHI access (curiosity browsing)  
❌ Sharing credentials with anyone  
❌ Circumventing security controls  
❌ Using system for personal gain  
❌ Installing unauthorized software  
❌ Connecting unauthorized devices  
❌ Accessing records of family/friends (without clinical need)  
❌ Exporting PHI without authorization  
❌ Disabling security features

### Sanctions

| Violation Level | Sanction | Example |
|-----------------|----------|---------|
| First minor | Written warning + retraining | Weak password, minor policy violation |
| Second minor | Access suspension (1-7 days) | Repeated minor violations |
| Major | Immediate termination | Unauthorized PHI access, data theft |
| Criminal | Termination + legal action | Deliberate data breach, fraud |

---

## Change Management Policy

### Production Changes

All production changes must follow this process:

1. **Document change request** (ticket/PR)
2. **Security impact assessment** (for security-relevant changes)
3. **Testing in staging environment**
4. **Code review approval**
5. **Security officer approval** (for security changes)
6. **Scheduled maintenance window**
7. **Rollback plan prepared**
8. **Post-deployment verification**

### Change Categories

| Category | Approval Required | Examples |
|----------|-------------------|----------|
| Standard | Dev lead | Bug fixes, UI updates |
| Normal | Dev lead + Security | New features, integrations |
| Emergency | Security officer | Security patches |
| Major | Full team | Architecture changes |

### Emergency Changes

- Security officer approval (verbal OK, documented after)
- Document in incident report
- Retroactive change request within 24 hours
- Post-incident review required

---

## Network Security Policy

### Network Segmentation

| Zone | Access Level | Purpose |
|------|-------------|---------|
| Public | Internet | Load balancer, CDN |
| DMZ | Limited | API gateway, web servers |
| Application | Internal | Application servers |
| Data | Restricted | Database servers |
| Management | Highly restricted | Admin access, monitoring |

### Firewall Rules

- Default deny all inbound
- Explicit allow for required services
- Logging enabled on all rules
- Quarterly rule review

### VPN Requirements

- Required for all remote access
- Multi-factor authentication
- Split tunneling disabled
- Session timeout: 8 hours

---

## Mobile Device Policy

### Approved Devices

- Company-managed devices only
- Personal devices: No PHI access permitted

### Security Requirements

| Requirement | Standard |
|-------------|----------|
| Full disk encryption | Required |
| Screen lock | 5 minutes |
| Remote wipe capability | Required |
| OS updates | Within 14 days |
| Approved MDM | Required |

### Lost/Stolen Device Procedure

1. Report immediately to IT
2. Remote wipe initiated within 1 hour
3. Access tokens revoked
4. Security incident logged
5. Device replaced

---

## Third-Party Access Policy

### Vendor Requirements

| Requirement | Description |
|-------------|-------------|
| Business Associate Agreement | Required before PHI access |
| Security assessment | Annual review |
| Background checks | Required for individuals |
| Access logging | All access tracked |
| Minimum access | Only required access granted |

### Cloud Provider Requirements

- SOC 2 Type II certification
- HIPAA BAA executed
- Data residency: US only
- Encryption in transit and at rest
- Incident notification: < 24 hours

---

## Training Requirements

### Initial Training

| Training | Audience | Timing |
|----------|----------|--------|
| HIPAA Privacy | All users | Before access |
| HIPAA Security | All users | Before access |
| Security Awareness | All users | Before access |
| Role-specific | By role | Before access |

### Ongoing Training

| Training | Frequency | Format |
|----------|-----------|--------|
| Security reminders | Quarterly | Email |
| Phishing tests | Quarterly | Simulated |
| Annual refresher | Annually | Online course |
| Incident-based | As needed | Targeted |

---

## Policy Compliance

### Monitoring

- Access logs reviewed weekly
- Security incidents reviewed daily
- Policy exceptions tracked
- Compliance metrics reported monthly

### Exceptions

- Must be documented and approved
- Compensating controls required
- Time-limited (max 90 days)
- Security officer approval

### Audit

- Internal audits: Quarterly
- External audits: Annually
- Findings tracked to resolution
- Corrective actions documented

---

## Contact Information

**Security Officer:** [Name]  
**Email:** security@phoenixguardian.example  
**Phone:** [Number]  
**After-Hours:** [Emergency Contact]

**IT Help Desk:** [Email/Phone]  
**Report Security Issues:** security@phoenixguardian.example

---

**Document Version:** 1.0  
**Approved By:** [Security Officer]  
**Effective:** February 2026  
**Review:** Annually
