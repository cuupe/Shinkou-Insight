CREATE TABLE IF NOT EXISTS users(
    id SERIAL PRIMARY KEY,
    user_name VARCHAR(20) NOT NULL,
    phone_number VARCHAR(11) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    login_at DATE,
    create_at DATE NOT NULL,
    status INTEGER NOT NULL
);

ALTER TABLE users
    ALTER COLUMN password TYPE VARCHAR(255);
