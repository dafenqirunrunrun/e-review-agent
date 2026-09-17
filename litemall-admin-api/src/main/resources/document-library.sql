CREATE TABLE IF NOT EXISTS litemall_document_job (
  id varchar(36) NOT NULL PRIMARY KEY,
  dedup_key char(64) NOT NULL,
  file_name varchar(255) NOT NULL,
  file_hash char(64) NOT NULL,
  size_bytes bigint NOT NULL,
  source_name varchar(255) NOT NULL,
  source_url varchar(2048) NOT NULL,
  usage_type varchar(32) NOT NULL,
  pipeline_version varchar(100) NOT NULL,
  input_path varchar(255) NOT NULL,
  status varchar(20) NOT NULL DEFAULT 'queued',
  attempts int NOT NULL DEFAULT 0,
  lease_token varchar(36) NULL,
  lease_until datetime NULL,
  available_at datetime NOT NULL,
  result_path varchar(255) NULL,
  error_code varchar(100) NULL,
  operator_name varchar(100) NOT NULL,
  created_at datetime NOT NULL,
  updated_at datetime NOT NULL,
  UNIQUE KEY uq_document_dedup (dedup_key),
  KEY ix_document_queue (status, available_at),
  KEY ix_document_lease (status, lease_until)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS litemall_document_index_release (
  id varchar(36) NOT NULL PRIMARY KEY,
  version varchar(64) NOT NULL,
  status varchar(20) NOT NULL DEFAULT 'queued',
  document_count int NOT NULL DEFAULT 0,
  chunk_count int NOT NULL DEFAULT 0,
  dense_status varchar(20) NOT NULL DEFAULT 'pending',
  quality_gate varchar(20) NOT NULL DEFAULT 'pending',
  request_path varchar(255) NOT NULL,
  result_path varchar(255) NULL,
  error_code varchar(100) NULL,
  attempts int NOT NULL DEFAULT 0,
  lease_token varchar(36) NULL,
  lease_until datetime NULL,
  requested_by varchar(100) NOT NULL,
  published_by varchar(100) NULL,
  published_at datetime NULL,
  created_at datetime NOT NULL,
  updated_at datetime NOT NULL,
  UNIQUE KEY uq_document_index_version (version),
  KEY ix_document_index_queue (status, created_at),
  KEY ix_document_index_lease (status, lease_until)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS litemall_document_index_item (
  release_id varchar(36) NOT NULL,
  document_id varchar(36) NOT NULL,
  PRIMARY KEY (release_id, document_id),
  KEY ix_document_index_item_document (document_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
