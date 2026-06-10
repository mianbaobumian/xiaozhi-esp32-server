CREATE DATABASE IF NOT EXISTS xiaozhi_agent DEFAULT CHARACTER SET utf8mb4;
USE xiaozhi_agent;

CREATE TABLE IF NOT EXISTS reminders (
    id VARCHAR(36) PRIMARY KEY,
    device_id VARCHAR(64) NOT NULL,
    trigger_type VARCHAR(16) NOT NULL,
    trigger_time VARCHAR(64),
    message TEXT NOT NULL,
    status VARCHAR(16) DEFAULT 'active',
    created_at DATETIME NOT NULL,
    fired_at DATETIME,
    INDEX idx_device_status (device_id, status)
);

CREATE TABLE IF NOT EXISTS broadcast_queue (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    source VARCHAR(32) NOT NULL,
    priority VARCHAR(16) NOT NULL,
    content TEXT NOT NULL,
    status VARCHAR(16) DEFAULT 'pending',
    retry_count INT DEFAULT 0,
    created_at DATETIME NOT NULL,
    delivered_at DATETIME,
    INDEX idx_status_priority (status, priority)
);

CREATE TABLE IF NOT EXISTS agent_memory (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    agent_name VARCHAR(64) NOT NULL,
    role VARCHAR(16) NOT NULL,
    content TEXT NOT NULL,
    summary TEXT,
    created_at DATETIME NOT NULL,
    INDEX idx_agent_time (agent_name, created_at)
);
