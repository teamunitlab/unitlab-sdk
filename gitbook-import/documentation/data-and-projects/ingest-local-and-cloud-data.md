---
description: "Upload local multimodal files or import approved cloud folders with controlled processing and validation."
icon: cloud-arrow-up
layout:
  width: wide
---

{% hint style="info" %}
**Who this guide is for:** Data operators, workspace administrators, project managers, and security owners. **You will:** Bring current source data into Data Space or a project without losing provenance, context, or failure visibility.
{% endhint %}

## Before you begin

- A Unitlab workspace and the role required for the operation.
- A representative pilot sample that includes normal and difficult cases.
- A named owner for the configuration, quality decision, or operational result.

## End-to-end flow

~~~mermaid
flowchart LR
  A["Source decision"]
  B["Preflight"]
  C["Transfer"]
  D["Processing"]
  E["Validation"]
  A --> B
  B --> C
  C --> D
  D --> E
~~~

## Procedure

{% stepper %}
{% step %}
### 1. Choose direct upload or an approved connected cloud storage
{% endstep %}
{% step %}
### 2. Confirm file-family support, source ownership, and destination folder or project
{% endstep %}
{% step %}
### 3. Upload files or browse and select the exact cloud prefix
{% endstep %}
{% step %}
### 4. Monitor transfer and server-side processing separately
{% endstep %}
{% step %}
### 5. Inspect recognized family, metadata, status, invalid items, and Batch Queue failures
{% endstep %}
{% step %}
### 6. Apply tags, metadata, or grouping only after ingestion is stable
{% endstep %}
{% step %}
### 7. Record the source scope and processing result
{% endstep %}
{% endstepper %}

## Product behavior and controls

Unitlab supports two primary ingestion paths: direct upload and connected cloud storage.

## Direct upload

Data can be uploaded into the Asset library or directly to a Project. The SDK supports directories containing a mix of:

- images;
- video;
- audio;
- text;
- PDF documents;
- DICOM;
- NIfTI;
- NRRD.

A project upload creates one Batch Queue. The SDK exposes processing counts for total, completed, processing, and failed items. Completion means no items remain in processing; it does not imply that every item succeeded, so individual failures still need to be checked.

Medical uploads include a finalization step that groups related files into the user-facing medical volume before the data enters the project workflow.

## Common recognized file families

Current file detection includes:

| Family | Common recognized extensions |
|---|---|
| Image | JPG, JPEG, PNG, GIF, WebP, BMP, ICO, SVG |
| Video | MP4, AVI, MOV, WebM, MKV, M4V, WMV, FLV |
| Audio | MP3, WAV, OGG, AAC, FLAC, M4A |
| Text | TXT |
| Medical | DCM, NII, NII.GZ, NRRD |
| Document | PDF |

The upload experience uses file detection to show previews and warnings, then confirms the saved family during ingestion. Unsupported files should appear as an explicit unsupported state rather than being forced into the wrong editor.

## Connected cloud storage

The current Add Cloud Storage dialog offers:

- Amazon S3;
- Google Cloud Storage;
- Azure Blob Storage;
- MinIO;
- DigitalOcean Spaces;
- Cloudflare R2;
- Wasabi;
- Backblaze B2;
- custom S3-compatible storage.

The exact credential fields vary by provider, but the current configuration model includes a display name, bucket or container, credentials, region where applicable, and an optional prefix or sub-path. A prefix can restrict Unitlab to a controlled part of a larger bucket.

The SDK can list safe storage metadata, browse a prefix, create a cloud-backed Unitlab folder, synchronize it, and import selected files or directory paths into a project. Cloud credentials are not returned by SDK list or browse operations.

## Cloud-folder user flow

Cloud folders are created from **New Folder ▾ → Add Cloud Folder**:

1. The user chooses a provider/integration.
2. The user selects an optional bucket sub-prefix and display name.
3. Unitlab creates a root folder representing that cloud location.
4. Opening it registers the first bucket level automatically if it has never been synchronized.
5. Immediate files appear as normal assets; child prefixes appear as child cloud folders.
6. The user can run **Sync** to refresh the current level.

Cloud folders reference customer storage; they do not copy the source bytes into Unitlab storage. Unitlab stores the object reference and a small preview where needed. Cloud folders display a provider badge, Synced state, and provider/resource path. Their contents are read-only mirrors for organization, so drag-move is disabled.

Cloud-folder Sync means “refresh this bucket prefix in Data Assets.” It is not project-to-dataset synchronization. A project receives cloud-backed content only through normal import/upload behavior or by attaching a frozen published dataset version.

## A safe cloud-connection pattern

For enterprise use, the connection should be treated as infrastructure, not as a convenient personal login:

1. Create a dedicated read-only or least-privilege identity for Unitlab.
2. Restrict it to the required bucket/container and prefix.
3. Avoid root or account-wide credentials.
4. Test with a small non-sensitive prefix.
5. Confirm that files, metadata, nested paths, and synchronization behave as expected.
6. Record the source system and connection owner.
7. Separate permission to manage cloud connections from permission to annotate data.

Workspace administrators can create, update, delete, test, and browse cloud connections from Workspace Settings. Connection administration requires cloud-storage permission and should remain separate from ordinary data browsing or annotation.

## Verify the result

- [ ] The visible result matches the project Instructions and active ontology.
- [ ] The workflow stage, assignee, and queue state are correct.
- [ ] A second user with the intended role can reproduce the result.
- [ ] Downstream dataset or release behavior remains correct.

## Failure modes and recovery

| Symptom | What to check |
|---|---|
| File transferred but is not usable | Check type detection, extension support, processing status, invalid state, and server-side Batch Queue data. |
| Cloud folder is empty or incomplete | Confirm storage identity, prefix, trailing slash for directories, provider permissions, and pagination. |
| Credentials or secrets appear in logs | Rotate the secret, remove it from logs or tickets, and move credential handling to an approved secret manager. |

## Operational record

For a material change, record the workspace, project, source or dataset version, ontology version, workflow stage, affected item or Batch Queue IDs, responsible owner, validation sample, result, and downstream release impact. Never include API keys, cloud credentials, signed download URLs, or regulated source data in tickets or logs.
