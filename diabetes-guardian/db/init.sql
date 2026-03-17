-- db/init.sql
-- Diabetes Guardian — full schema (spec v2, PostgreSQL)
-- Usage: psql -U guardian -d diabetes_guardian -f db/init.sql

-- Drop legacy tables from spec v1
DROP TABLE IF EXISTS user_telemetry_log CASCADE;

-- Drop all tables (reverse dependency order) for clean rebuild
DROP TABLE IF EXISTS user_glucose_weekly_profile CASCADE;
DROP TABLE IF EXISTS user_glucose_daily_stats CASCADE;
DROP TABLE IF EXISTS reward_log CASCADE;
DROP TABLE IF EXISTS routine_task_log CASCADE;
DROP TABLE IF EXISTS dynamic_task_rule CASCADE;
DROP TABLE IF EXISTS dynamic_task_log CASCADE;
DROP TABLE IF EXISTS user_emergency_contacts CASCADE;
DROP TABLE IF EXISTS user_food_log CASCADE;
DROP TABLE IF EXISTS user_emotion_summary CASCADE;
DROP TABLE IF EXISTS user_emotion_log CASCADE;
DROP TABLE IF EXISTS user_exercise_log CASCADE;
DROP TABLE IF EXISTS user_hr_log CASCADE;
DROP TABLE IF EXISTS user_cgm_log CASCADE;
DROP TABLE IF EXISTS user_weekly_patterns CASCADE;
DROP TABLE IF EXISTS user_known_places CASCADE;
DROP TABLE IF EXISTS intervention_log CASCADE;
DROP TABLE IF EXISTS error_log CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- ─────────────────────────────────────────
-- User profile (user self-reported, overwrite on update)
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    user_id       VARCHAR(36) PRIMARY KEY,
    name          VARCHAR(100),
    birth_year    INT,
    gender        VARCHAR(10) CHECK (gender IN ('male', 'female', 'other')),
    waist_cm      NUMERIC(5,1),
    weight_kg     NUMERIC(5,1),
    height_cm     NUMERIC(5,1),
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ─────────────────────────────────────────
-- CGM blood glucose log (simulated, ~10 min interval)
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_cgm_log (
    id            BIGSERIAL PRIMARY KEY,
    user_id       VARCHAR(36) NOT NULL,
    recorded_at   TIMESTAMP NOT NULL,
    glucose       NUMERIC(5,2) NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cgm_user_time ON user_cgm_log (user_id, recorded_at);

-- ─────────────────────────────────────────
-- Heart rate log (simulated from Apple Watch)
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_hr_log (
    id            BIGSERIAL PRIMARY KEY,
    user_id       VARCHAR(36) NOT NULL,
    recorded_at   TIMESTAMP NOT NULL,
    heart_rate    INT NOT NULL,
    gps_lat       NUMERIC(10,7),
    gps_lng       NUMERIC(10,7)
);
CREATE INDEX IF NOT EXISTS idx_hr_user_time ON user_hr_log (user_id, recorded_at);

-- ─────────────────────────────────────────
-- Exercise log (one row per session, from Apple Watch)
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_exercise_log (
    id              BIGSERIAL PRIMARY KEY,
    user_id         VARCHAR(36) NOT NULL,
    exercise_type   VARCHAR(50) CHECK (exercise_type IN ('resistance_training', 'cardio', 'hiit')) NOT NULL,
    started_at      TIMESTAMP NOT NULL,
    ended_at        TIMESTAMP NOT NULL,
    avg_heart_rate  INT,
    calories_burned NUMERIC(7,1)
);
CREATE INDEX IF NOT EXISTS idx_ex_user_time ON user_exercise_log (user_id, started_at);

-- ─────────────────────────────────────────
-- Weekly activity patterns (user self-configured)
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_weekly_patterns (
    id              BIGSERIAL PRIMARY KEY,
    user_id         VARCHAR(36) NOT NULL,
    day_of_week     SMALLINT NOT NULL,
    start_time      TIME NOT NULL,
    end_time        TIME NOT NULL,
    activity_type   VARCHAR(50) CHECK (activity_type IN ('resistance_training', 'cardio', 'hiit')) NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pattern_user ON user_weekly_patterns (user_id, day_of_week);

-- ─────────────────────────────────────────
-- Known locations (user self-configured)
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_known_places (
    id           BIGSERIAL PRIMARY KEY,
    user_id      VARCHAR(36) NOT NULL,
    place_name   VARCHAR(100),
    place_type   VARCHAR(50),
    gps_lat      NUMERIC(10,7),
    gps_lng      NUMERIC(10,7)
);
CREATE INDEX IF NOT EXISTS idx_places_user ON user_known_places (user_id);

-- ─────────────────────────────────────────
-- Emotion log (MERaLiON acoustic/tonal emotion detection)
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_emotion_log (
    id              BIGSERIAL PRIMARY KEY,
    user_id         VARCHAR(36) NOT NULL,
    recorded_at     TIMESTAMP NOT NULL,
    user_input      TEXT NOT NULL,
    emotion_label   VARCHAR(50) NOT NULL,
    source          VARCHAR(50) DEFAULT 'meralion'
);
CREATE INDEX IF NOT EXISTS idx_emotion_user_time ON user_emotion_log (user_id, recorded_at);

-- ─────────────────────────────────────────
-- Emotion summary (daily semantic summary, LLM-generated)
-- Owned by companion agent codebase — do NOT write from gateway/agent/pipeline
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_emotion_summary (
    id              BIGSERIAL PRIMARY KEY,
    user_id         VARCHAR(36) NOT NULL,
    summary_date    DATE NOT NULL,
    summary_text    TEXT NOT NULL,
    primary_emotion VARCHAR(50),
    CONSTRAINT uq_emotion_summary_user_date UNIQUE (user_id, summary_date)
);
CREATE INDEX IF NOT EXISTS idx_emotion_summary_user ON user_emotion_summary (user_id, summary_date);

-- ═════════════════════════════════════════
-- EXTERNAL SYSTEM TABLES
-- Write logic owned by separate codebases.
-- gateway / agent / pipeline must NOT write to these tables.
-- ═════════════════════════════════════════

-- ─────────────────────────────────────────
-- Food intake log (from vision agent recognition)
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_food_log (
    id              BIGSERIAL PRIMARY KEY,
    user_id         VARCHAR(36) NOT NULL,
    recorded_at     TIMESTAMP NOT NULL,
    food_name       VARCHAR(100) NOT NULL,
    meal_type       VARCHAR(10) NOT NULL,
    gi_level        VARCHAR(10) NOT NULL,
    total_calories  NUMERIC(6,1) NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_food_user_time ON user_food_log (user_id, recorded_at);

-- ─────────────────────────────────────────
-- Dynamic task log (location- or context-triggered tasks)
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dynamic_task_log (
    task_id         BIGSERIAL PRIMARY KEY,
    user_id         VARCHAR(36) NOT NULL,
    task_content    TEXT NOT NULL,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    task_status     VARCHAR(20) NOT NULL DEFAULT 'pending',
    target_lat      NUMERIC(10,7),
    target_lng      NUMERIC(10,7),
    completed_at    TIMESTAMP,
    expired_at      TIMESTAMP,
    reward_points   INT DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_dynamic_task_user ON dynamic_task_log (user_id, created_at);

-- ─────────────────────────────────────────
-- Dynamic task rule (configurable thresholds for task generation)
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dynamic_task_rule (
    rule_id             SERIAL PRIMARY KEY,
    base_calorie        INT NOT NULL DEFAULT 300,
    trigger_threshold   NUMERIC(3,2) NOT NULL DEFAULT 0.60,
    is_active           SMALLINT NOT NULL DEFAULT 1
);

-- ─────────────────────────────────────────
-- Routine task log (recurring scheduled tasks)
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS routine_task_log (
    task_id         BIGSERIAL PRIMARY KEY,
    user_id         VARCHAR(36) NOT NULL,
    task_type       VARCHAR(50) NOT NULL,
    period          VARCHAR(20) NOT NULL,
    task_status     VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at    TIMESTAMP,
    expired_at      TIMESTAMP,
    reward_points   INT DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_routine_task_user ON routine_task_log (user_id, period);

-- ─────────────────────────────────────────
-- Reward ledger (one row per user)
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS reward_log (
    user_id             VARCHAR(36) PRIMARY KEY,
    total_points        INT NOT NULL DEFAULT 0,
    accumulated_points  INT NOT NULL DEFAULT 0,
    consumed_points     INT NOT NULL DEFAULT 0,
    updated_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ─────────────────────────────────────────
-- Emergency contacts (user self-configured)
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_emergency_contacts (
    id              BIGSERIAL PRIMARY KEY,
    user_id         VARCHAR(36) NOT NULL,
    contact_name    VARCHAR(100) NOT NULL,
    phone_number    VARCHAR(20) NOT NULL,
    relationship    VARCHAR(50),
    notify_on       JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_contacts_user ON user_emergency_contacts (user_id);

-- ─────────────────────────────────────────
-- Intervention log
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS intervention_log (
    id              BIGSERIAL PRIMARY KEY,
    user_id         VARCHAR(36) NOT NULL,
    triggered_at    TIMESTAMP NOT NULL,
    trigger_type    VARCHAR(50),
    display_label   VARCHAR(50),
    agent_decision  TEXT,
    message_sent    TEXT,
    user_ack        BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ─────────────────────────────────────────
-- Error log
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS error_log (
    id          BIGSERIAL PRIMARY KEY,
    service     VARCHAR(50),
    error_msg   TEXT,
    payload     TEXT,
    ts          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ═════════════════════════════════════════
-- PIPELINE LAYER TABLES
-- Populated exclusively by pipeline/analytics.py
-- ═════════════════════════════════════════

-- ─────────────────────────────────────────
-- Daily glucose summary (rolling 1-day window)
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_glucose_daily_stats (
    id               BIGSERIAL PRIMARY KEY,
    user_id          VARCHAR(36) NOT NULL,
    stat_date        DATE NOT NULL,
    avg_glucose      NUMERIC(5,2),
    peak_glucose     NUMERIC(5,2),
    nadir_glucose    NUMERIC(5,2),
    glucose_sd       NUMERIC(5,2),
    tir_percent      NUMERIC(5,1),
    tbr_percent      NUMERIC(5,1),
    tar_percent      NUMERIC(5,1),
    data_points      INT,
    is_realtime      BOOLEAN DEFAULT FALSE,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uk_daily_user_date UNIQUE (user_id, stat_date)
);
CREATE INDEX IF NOT EXISTS idx_daily_user_date ON user_glucose_daily_stats (user_id, stat_date);

-- ─────────────────────────────────────────
-- 7-day sliding window glucose profile
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_glucose_weekly_profile (
    id                    BIGSERIAL PRIMARY KEY,
    user_id               VARCHAR(36) NOT NULL,
    profile_date          DATE NOT NULL,
    window_start          DATE NOT NULL,
    avg_glucose           NUMERIC(5,2),
    peak_glucose          NUMERIC(5,2),
    nadir_glucose         NUMERIC(5,2),
    glucose_sd            NUMERIC(5,2),
    cv_percent            NUMERIC(5,1),
    tir_percent           NUMERIC(5,1),
    tbr_percent           NUMERIC(5,1),
    tar_percent           NUMERIC(5,1),
    avg_delta_vs_prior_7d NUMERIC(5,2),
    data_points           INT,
    coverage_percent      NUMERIC(5,1),
    created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uk_weekly_user_date UNIQUE (user_id, profile_date)
);
CREATE INDEX IF NOT EXISTS idx_weekly_user_date ON user_glucose_weekly_profile (user_id, profile_date);
