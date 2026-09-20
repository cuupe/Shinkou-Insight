ALTER TABLE agent_messages
    ADD COLUMN IF NOT EXISTS model_name VARCHAR(300);
