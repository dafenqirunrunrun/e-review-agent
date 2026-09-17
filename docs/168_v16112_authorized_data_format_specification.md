# V1.6.1.12 Authorized Data Format Specification

Supported text formats: CSV, JSONL, Parquet.

Supported image formats: JPEG, PNG, WebP.

Supported annotation formats: JSONL, CSV.

Minimum text fields:

- `source_record_id`
- `review_text`

Recommended fields:

- `rating`
- `product_category`
- `created_at`
- `image_ids`
- `language`
- `product_id_hash`
- `user_id_hash`
- `order_id_hash`

Providers should not submit plaintext names, phone numbers, addresses, order numbers, or user account identifiers. If business linkage is required, identifiers must be irreversibly hashed before delivery.

Images should be pre-redacted to remove shipping labels and personal information. Text and image associations, ratings, and product categories should be retained when allowed by the authorization manifest.
