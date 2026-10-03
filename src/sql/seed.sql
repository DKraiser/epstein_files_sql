INSERT INTO enum_parse_statuses (status_code) VALUES 
    ('success'), ('partial'), ('null'), ('failed'), ('empty');
INSERT INTO enum_match_statuses (status_code) VALUES 
    ('matched'), ('unresolved');
INSERT INTO enum_run_statuses (status_code) VALUES 
    ('completed'), ('crashed'), ('interrupted');
INSERT INTO enum_file_statuses (status_code) VALUES 
    ('success'), ('failed');
INSERT INTO enum_curated_statuses (status_code) VALUES 
    ('gold');

INSERT INTO enum_curated_tiers (tier) VALUES 
    ('nuclear'), ('critical'), ('high'), ('medium'), ('supporting');
INSERT INTO enum_models (model_name) VALUES
    ('gemini-2.5-flash'),
    ('gemini-2.5-flash-lite'),
    ('gemini-3-flash-preview'),
    ('deepseek-chat'),
    ('gpt-4o-mini'),
    ('gpt-5-nano'),
    ('grok-2-vision-latest'),
    ('tesseract-community');