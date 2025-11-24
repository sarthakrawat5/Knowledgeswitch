-- Knowledge Switch Database Schema
-- User authentication and credentials management

-- Create the database
CREATE DATABASE IF NOT EXISTS knowledge_switch;
USE knowledge_switch;

-- Create users table for authentication
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_login TIMESTAMP NULL,
    is_active BOOLEAN DEFAULT TRUE,
    email_verified BOOLEAN DEFAULT FALSE,
    verification_token VARCHAR(255) NULL,
    reset_token VARCHAR(255) NULL,
    reset_token_expires TIMESTAMP NULL,
    INDEX idx_email (email),
    INDEX idx_created_at (created_at),
    INDEX idx_last_login (last_login)
);

-- Create user_skills table for storing user skills
CREATE TABLE IF NOT EXISTS user_skills (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    skill_name VARCHAR(255) NOT NULL,
    role ENUM('teach', 'learn') NOT NULL,
    portfolio_link VARCHAR(500) NULL,
    github_link VARCHAR(500) NULL,
    linkedin_link VARCHAR(500) NULL,
    upload_sample VARCHAR(500) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_id (user_id),
    INDEX idx_skill_name (skill_name),
    INDEX idx_role (role)
);

-- Optional: Create a sessions table for session management (if needed)
CREATE TABLE IF NOT EXISTS user_sessions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    session_token VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_session_token (session_token),
    INDEX idx_user_id (user_id),
    INDEX idx_expires_at (expires_at)
);

-- Optional: Create an audit log table for security tracking
CREATE TABLE IF NOT EXISTS user_audit_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NULL,
    action VARCHAR(100) NOT NULL,
    details TEXT,
    ip_address VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_user_id (user_id),
    INDEX idx_action (action),
    INDEX idx_created_at (created_at)
);

-- Insert a sample user (for testing - remove in production)
-- Password hash for 'password123' using bcrypt (cost factor 12)
-- Note: In production, always hash passwords server-side before insertion
INSERT INTO users (email, password_hash, email_verified) VALUES
('test@example.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPjYQmLx2wCKe', TRUE);
