# EquipED documentation

## Product and system

- [Product overview](../PRODUCT.md): users, scope, evidence, and human authority.
- [Requirements](../PRD.md): evaluation, access, reporting, and operating requirements.
- [Architecture](../ARCHITECTURE.md): application boundaries, data flow, and deployment model.
- [Design system](../DESIGN.md): interface, accessibility, and institutional export conventions.

## Using and operating EquipED

- [Evaluation](evaluation.md): module preparation, specialist reviews, results, and alignment.
- [Setup](setup.md): dependencies, configuration, and application commands.
- [Operations](operations.md): deployment, health, persistent storage, and recovery.
- [Training](training.md): reviewed data, notebook training, validation, and adapter publication.
- [Reviewed training packages](reviewed-training-packages.md): selecting frozen training sources.
- [Host sync](host-sync-setup.md): adapter delivery to the model host.

## Component guides

- [Evaluation harness](../libs/evaluation-harness/README.md)
- [Database metadata and migrations](../apps/server/db/README.md)
- [PostgreSQL backups](../infra/postgres/README.md)
- [Standalone training tools](../training/README.md)

Colab notebook templates under the repository’s `colab/` directory support the application training workflow.
They are executable resources and remain separate from the written guides.
