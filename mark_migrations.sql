INSERT INTO django_migrations (app, name, applied) VALUES
('resources', '0013_drop_legacy_corpus_file_format_column', NOW()),
('resources', '0014_merge_0012_0013_resources_branches', NOW()),
('resources', '0015_nlptool_github_url', NOW()),
('resources', '0016_alter_corpus_options_remove_document_file_format_and_more', NOW()),
('resources', '0017_domain_model_indexes', NOW()),
('resources', '0018_alter_corpus_options_remove_document_file_format_and_more', NOW()),
('resources', '0018_coursecomment', NOW()),
('resources', '0018_merge_20260325_1814', NOW()),
('resources', '0018_merge_20260326_2136', NOW()),
('resources', '0019_corpus_rejection_reason_course_rejection_reason_and_more', NOW()),
('resources', '0019_resource_entities', NOW()),
('resources', '0019_resource_soft_delete_fields', NOW()),
('resources', '0020_alter_corpus_options_remove_document_file_format_and_more', NOW()),
('resources', '0020_merge_20260330_1105', NOW()),
('resources', '0021_merge', NOW()),
('resources', '0021_merge_resources_leafs', NOW()),
('resources', '0022_merge_0021_merge_0021_merge_resources_leafs', NOW())
ON CONFLICT DO NOTHING;