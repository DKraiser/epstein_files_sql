INSERT INTO enum_parse_statuses (status_code) VALUES 
    ('success'), ('partial'), ('null'), ('failed'), ('empty')
ON CONFLICT DO NOTHING;

INSERT INTO enum_match_statuses (status_code) VALUES 
    ('matched'), ('unresolved')
ON CONFLICT DO NOTHING;

INSERT INTO enum_run_statuses (status_code) VALUES 
    ('completed'), ('crashed'), ('interrupted')
ON CONFLICT DO NOTHING;

INSERT INTO enum_file_statuses (status_code) VALUES 
    ('success'), ('failed')
ON CONFLICT DO NOTHING;

INSERT INTO enum_curated_statuses (status_code) VALUES 
    ('gold')
ON CONFLICT DO NOTHING;

INSERT INTO enum_curated_tiers (tier) VALUES 
    ('nuclear'), ('critical'), ('high'), ('medium'), ('supporting')
ON CONFLICT DO NOTHING;

INSERT INTO enum_models (model_name) VALUES
    ('gemini-2.5-flash'),
    ('gemini-2.5-flash-lite'),
    ('gemini-3-flash-preview'),
    ('deepseek-chat'),
    ('gpt-4o-mini'),
    ('gpt-5-nano'),
    ('grok-2-vision-latest'),
    ('tesseract-community')
ON CONFLICT DO NOTHING;
