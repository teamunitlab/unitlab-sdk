---
description: "Control authentication, workspace onboarding, membership, built-in and custom roles, and least-privilege governance."
icon: user-lock
layout:
  width: wide
---

{% hint style="info" %}
**Who this guide is for:** Workspace owners, managers, security administrators, and program owners. **You will:** Give each human and service identity only the access required for its current responsibility.
{% endhint %}

## Before you begin

- A Unitlab workspace and the role required for the operation.
- A representative pilot sample that includes normal and difficult cases.
- A named owner for the configuration, quality decision, or operational result.

## End-to-end flow

~~~mermaid
flowchart LR
  A["Identity"]
  B["Workspace role"]
  C["Project assignment"]
  D["Permission verification"]
  E["Periodic review"]
  A --> B
  B --> C
  C --> D
  D --> E
~~~

## Procedure

{% stepper %}
{% step %}
### 1. Create or identify the organization-owned workspace and accountable owners
{% endstep %}
{% step %}
### 2. Invite the minimum required members
{% endstep %}
{% step %}
### 3. Assign Owner, Manager, Member, Annotator, Reviewer, or a reviewed custom role
{% endstep %}
{% step %}
### 4. Inspect Workspace, Projects, Annotation & Review, and Models & Data permission groups
{% endstep %}
{% step %}
### 5. Verify project-level assignments and workflow-stage availability
{% endstep %}
{% step %}
### 6. Review privileged memberships and service identities on a schedule
{% endstep %}
{% step %}
### 7. Before offboarding, reassign tasks, review duties, issues, integrations, and keys
{% endstep %}
{% step %}
### 8. Remove access and record the completed review
{% endstep %}
{% endstepper %}

## Product behavior and controls

## Authentication and account recovery

Unitlab supports email/password sign-up and sign-in, Google authentication, email verification, invitation-token access, password reset, and TOTP two-factor authentication.

Two-factor authentication includes QR/secret setup, verification, ten single-use backup codes shown once, login challenge, disable, and backup-code regeneration. When 2FA is enabled, password change, password-reset completion, account deletion, and workspace destruction require an appropriate second factor.

If a user refreshes during the temporary 2FA login challenge, the challenge is cleared and the user returns to login rather than leaving reusable sensitive state in the browser.

## First-workspace onboarding

1. The user authenticates.
2. If no workspace exists, Unitlab opens the workspace wizard.
3. The user selects a purpose: Work, Education, or Personal.
4. The user enters a workspace name.
5. The user can optionally invite teammates.
6. Unitlab creates the workspace, makes the user Owner, provisions the free subscription, and creates the initial workspace API key.
7. The application switches into the new workspace and guides the user toward projects.

Guided quick-start actions include creating a project, creating or cloning a release, inviting members, integrating a model, configuring reviewer or custom-model projects, trying batch/crop auto-annotation or Magic Touch, and opening project/member statistics.

## Workspace switching and settings

The workspace area includes:

- workspace list and switcher;
- general settings for name, purpose, and logo;
- account security and 2FA;
- billing and pricing portal;
- usage and quota visibility;
- members and member statistics;
- Roles & Permissions editor;
- API keys;
- cloud storage connections;
- user profile.

Usage can report datasource, image, video, medical, token, audio-duration, AI-inference, and member consumption. The interface warns when a downgraded plan would be exceeded.

Workspace destruction is intentionally different from leaving a workspace. It is Owner-only, requires the exact workspace name, and requires a second factor when the Owner has 2FA.

## Members

Member management supports search, filtering, invitations, role changes, member actions, analytics, and Active, Pending, Disabled, and Rejected states. Pending invitations can be resent.

## Built-in and custom roles

Built-in roles include:

- Owner;
- Manager;
- Member;
- Annotator;
- Reviewer.

Administrators can also create custom roles for workspace-specific access patterns.

Roles can be configured to permit assignment as an Annotator or Reviewer.

Workspace role and project position are different:

- **Workspace role** controls tenant-wide capabilities.
- **Project position** determines eligibility for annotator or reviewer workflow stages.

Owner, Manager, and custom roles use the administrative branch by default. Member, Annotator, and Reviewer are assignment-scoped and see only the stage queues and work items for which they are eligible.

## Permission groups

Granular permissions include:

**Workspace**

- manage workspace settings;
- manage billing;
- manage API keys;
- manage cloud storage;
- manage members.

**Projects and schemas**

- manage projects;
- manage ontologies;
- assign project members;
- manage releases;
- view ontology;
- view instructions;
- manage instructions.

**Annotation and review**

- view labeling interface;
- create labels;
- comment;
- view statistics.

**Models and data**

- manage data;
- manage AI models;
- manage workflows;
- manage augmentation.

## Governance pattern

Separate high-impact administration from production work. An annotator rarely needs permission to manage API keys, cloud storage, releases, or ontologies. A reviewer should be able to make review decisions without necessarily changing the schema. External contributors should receive a minimal custom role and access only to the projects they need.

## Verify the result

- [ ] The visible result matches the project Instructions and active ontology.
- [ ] The workflow stage, assignee, and queue state are correct.
- [ ] A second user with the intended role can reproduce the result.
- [ ] Downstream dataset or release behavior remains correct.

## Failure modes and recovery

| Symptom | What to check |
|---|---|
| The expected action is unavailable | Check the active workflow stage, user role, selected item, and whether the required resource is Live or still processing. |
| The result appears incomplete | Inspect filters, source membership, Data Group membership, invalid state, and Batch Queue failures before repeating the operation. |
| A change affects existing work | Stop the rollout, identify affected items and versions, validate a recovery path on a sample, and document the change owner. |

## Operational record

For a material change, record the workspace, project, source or dataset version, ontology version, workflow stage, affected item or Batch Queue IDs, responsible owner, validation sample, result, and downstream release impact. Never include API keys, cloud credentials, signed download URLs, or regulated source data in tickets or logs.

## Product view

![Workspace roles and permissions provide the least-privilege control surface for human and service identities.](../.gitbook/assets/roles-permissions.png)

*Workspace roles and permissions provide the least-privilege control surface for human and service identities.*

