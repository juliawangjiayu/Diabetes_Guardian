-- db/init.sql
--
-- Database schema for the diabetes-guardian system.
-- Execute against the diabetes_guardian database to create all required tables.

CREATE TABLE IF NOT EXISTS users (
    user_id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(100),
    birth_year INT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_telemetry_log (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    recorded_at DATETIME NOT NULL,
    heart_rate INT,
    glucose DECIMAL(5, 2),
    gps_lat DECIMAL(10, 7),
    gps_lng DECIMAL(10, 7),
    INDEX idx_user_time (user_id, recorded_at)
);

CREATE TABLE IF NOT EXISTS user_weekly_patterns (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    day_of_week TINYINT,
    hour_of_day TINYINT,
    activity_type VARCHAR(50),
    probability DECIMAL(4, 3),
    avg_glucose_drop DECIMAL(5, 2),
    sample_count INT,
    INDEX idx_user_pattern (
        user_id,
        day_of_week,
        hour_of_day
    )
);

CREATE TABLE IF NOT EXISTS user_known_places (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    place_name VARCHAR(100),
    place_type VARCHAR(50),
    gps_lat DECIMAL(10, 7),
    gps_lng DECIMAL(10, 7),
    INDEX idx_user_places (user_id)
);

CREATE TABLE IF NOT EXISTS intervention_log (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    triggered_at DATETIME NOT NULL,
    trigger_type VARCHAR(50),
    agent_decision TEXT,
    message_sent TEXT,
    user_ack BOOLEAN DEFAULT FALSE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS error_log (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    service VARCHAR(50),
    error_msg TEXT,
    payload TEXT,
    ts DATETIME DEFAULT CURRENT_TIMESTAMP
);