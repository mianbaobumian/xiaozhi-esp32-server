-- 为现有数据库添加软删除支持
USE xiaozhi_agent;

-- reminders 表
ALTER TABLE reminders
  CHANGE created_at created_time DATE NOT NULL,
  ADD COLUMN updated_time DATE DEFAULT NULL AFTER created_time,
  ADD COLUMN is_deleted TINYINT(1) DEFAULT 0 AFTER status;

-- broadcast_queue 表
ALTER TABLE broadcast_queue
  CHANGE created_at created_time DATE NOT NULL,
  ADD COLUMN updated_time DATE DEFAULT NULL AFTER created_time,
  ADD COLUMN is_deleted TINYINT(1) DEFAULT 0 AFTER status;

-- agent_memory 表
ALTER TABLE agent_memory
  CHANGE created_at created_time DATE NOT NULL,
  ADD COLUMN updated_time DATE DEFAULT NULL AFTER created_time,
  ADD COLUMN is_deleted TINYINT(1) DEFAULT 0 AFTER content;
