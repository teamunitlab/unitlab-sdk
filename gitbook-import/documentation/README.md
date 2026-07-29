---
description: Operate Unitlab as an enterprise multimodal data-production system from source ingestion through verified delivery.
icon: book
layout:
  width: wide
---

Unitlab Documentation is organized as a flat, task-first operator manual. Nothing in the sidebar must be expanded to discover the core workflow. Each guide begins with prerequisites and an outcome, provides an ordered procedure, documents current product behavior, and ends with verification and recovery.

## Recommended learning path

1. Read **Platform overview and navigation** and **Core object model**.
2. Complete the **Production quickstart** with a representative cohort.
3. Follow the data and project guides to prepare reusable, contextual work.
4. Train annotators and reviewers on the Workbench and their modality guide.
5. Govern semantics and routing through Ontologies, Workflows, Queues, and Quality Operations.
6. Validate one Release in the downstream consumer.
7. Approve scale through the **Production-readiness review**.

~~~mermaid
flowchart LR
  A["Ingest"] --> B["Curate & group"]
  B --> C["Version dataset"]
  C --> D["Configure project"]
  D --> E["Annotate"]
  E --> F["Review & resolve"]
  F --> G["Release & validate"]
~~~

{% hint style="warning" %}
Unitlab configuration is connected. Changes to source membership, grouping, ontology, workflow, roles, models, or export mapping can affect active work and downstream data. Validate material changes on a controlled sample and retain the decision record.
{% endhint %}
