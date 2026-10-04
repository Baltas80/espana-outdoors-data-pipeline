# Data licensing and provenance

## Scope

This repository contains software for processing external geographic datasets. The Apache-2.0 license applies to the repository's original code and documentation unless stated otherwise.

It does **not** grant rights over external GPX, KML, map, route, POI, imagery, or other datasets processed by the pipeline.

## Rules

1. Keep the source URL or provider for every imported dataset.
2. Record the dataset's original license and attribution requirements.
3. Do not redistribute source files unless their license permits it.
4. Preserve required attribution and notices in generated outputs.
5. When license status is unknown, mark the source as `REVIEW_REQUIRED` and do not publish it.
6. Keep provenance separate from the application code.

## Recommended source record

```text
source_id
provider
source_name
source_url
retrieved_at
original_license
license_url
attribution_required
redistribution_allowed
commercial_use_allowed
modification_allowed
share_alike_required
notes
status
```

## Status values

- `VERIFIED` — licensing terms have been checked.
- `REVIEW_REQUIRED` — terms are incomplete or unclear.
- `RESTRICTED` — redistribution or intended use is not permitted.
- `APPROVED_FOR_PROCESSING` — processing is permitted, subject to the recorded terms.
- `APPROVED_FOR_PUBLICATION` — publication of the resulting dataset has been reviewed and permitted.

This document is operational guidance for this project and is not legal advice.
