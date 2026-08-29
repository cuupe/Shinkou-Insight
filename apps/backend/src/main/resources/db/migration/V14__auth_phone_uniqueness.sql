-- Keep the account identifier unique even when the database predates V1's constraint.
CREATE UNIQUE INDEX IF NOT EXISTS uq_users_phone_number ON users (phone_number);
