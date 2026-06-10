-- 添加MiMo TTS供应器
delete from `ai_model_provider` where id = 'SYSTEM_TTS_MiMoTTS';
INSERT INTO `ai_model_provider` (`id`, `model_type`, `provider_code`, `name`, `fields`, `sort`, `creator`, `create_date`, `updater`, `update_date`) VALUES
('SYSTEM_TTS_MiMoTTS', 'TTS', 'mimo', 'MiMo语音合成', '[{"key":"api_key","label":"API密钥","type":"string"},{"key":"base_url","label":"API地址","type":"string"},{"key":"output_dir","label":"输出目录","type":"string"},{"key":"model","label":"模型","type":"string"},{"key":"voice","label":"音色","type":"string"},{"key":"format","label":"音频格式","type":"string"},{"key":"style","label":"风格指令","type":"string"}]', 23, 1, NOW(), 1, NOW());

-- 添加MiMo TTS模型配置
delete from `ai_model_config` where id = 'TTS_MiMoTTS';
INSERT INTO `ai_model_config` VALUES ('TTS_MiMoTTS', 'TTS', 'MiMoTTS', 'MiMo语音合成', 0, 1, '{\"type\": \"mimo\", \"api_key\": \"\", \"base_url\": \"https://api.xiaomimimo.com/v1\", \"output_dir\": \"tmp/\", \"model\": \"mimo-v2.5-tts\", \"voice\": \"冰糖\", \"format\": \"wav\", \"style\": \"\"}', NULL, NULL, 23, NULL, NULL, NULL, NULL);

-- 更新MiMo TTS配置说明
UPDATE `ai_model_config` SET
`doc_link` = 'https://platform.xiaomimimo.com/docs/zh-CN/usage-guide/speech-synthesis-v2.5',
`remark` = 'MiMo-V2.5-TTS语音合成配置说明：
1. 兼容OpenAI SDK，使用chat/completions接口
2. 需要在 https://platform.xiaomimimo.com 获取API密钥
3. 当前限时免费
4. api_key：API访问密钥
5. base_url：API地址，默认 https://api.xiaomimimo.com/v1
6. model：模型ID，可选 mimo-v2.5-tts（预置音色）、mimo-v2.5-tts-voicedesign（音色设计）、mimo-v2.5-tts-voiceclone（音色克隆）
7. voice：预置音色，可选 冰糖（女）、茉莉（女）、苏打（男）、白桦（男）、Mia（英文女）、Chloe（英文女）、Milo（英文男）、Dean（英文男）
8. format：音频格式，流式使用pcm16（24kHz mono），非流式使用wav
9. style：风格指令（可选），支持自然语言描述语音风格，如"用温柔慵懒的语调"
如需了解更多参数配置，请参考：https://platform.xiaomimimo.com/docs/zh-CN/usage-guide/speech-synthesis-v2.5
' WHERE `id` = 'TTS_MiMoTTS';

-- 添加MiMo TTS音色
delete from `ai_tts_voice` where tts_model_id = 'TTS_MiMoTTS';
INSERT INTO `ai_tts_voice` VALUES ('TTS_MiMoTTS_0001', 'TTS_MiMoTTS', '冰糖-默认女声', '冰糖', '中文', NULL, NULL, NULL, NULL, 1, NULL, NULL, NULL, NULL);
INSERT INTO `ai_tts_voice` VALUES ('TTS_MiMoTTS_0002', 'TTS_MiMoTTS', '茉莉-温柔女声', '茉莉', '中文', NULL, NULL, NULL, NULL, 2, NULL, NULL, NULL, NULL);
INSERT INTO `ai_tts_voice` VALUES ('TTS_MiMoTTS_0003', 'TTS_MiMoTTS', '苏打-青年男声', '苏打', '中文', NULL, NULL, NULL, NULL, 3, NULL, NULL, NULL, NULL);
INSERT INTO `ai_tts_voice` VALUES ('TTS_MiMoTTS_0004', 'TTS_MiMoTTS', '白桦-成熟男声', '白桦', '中文', NULL, NULL, NULL, NULL, 4, NULL, NULL, NULL, NULL);
INSERT INTO `ai_tts_voice` VALUES ('TTS_MiMoTTS_0005', 'TTS_MiMoTTS', 'Mia-英文女声', 'Mia', '英文', NULL, NULL, NULL, NULL, 5, NULL, NULL, NULL, NULL);
INSERT INTO `ai_tts_voice` VALUES ('TTS_MiMoTTS_0006', 'TTS_MiMoTTS', 'Chloe-英文女声', 'Chloe', '英文', NULL, NULL, NULL, NULL, 6, NULL, NULL, NULL, NULL);
INSERT INTO `ai_tts_voice` VALUES ('TTS_MiMoTTS_0007', 'TTS_MiMoTTS', 'Milo-英文男声', 'Milo', '英文', NULL, NULL, NULL, NULL, 7, NULL, NULL, NULL, NULL);
INSERT INTO `ai_tts_voice` VALUES ('TTS_MiMoTTS_0008', 'TTS_MiMoTTS', 'Dean-英文男声', 'Dean', '英文', NULL, NULL, NULL, NULL, 8, NULL, NULL, NULL, NULL);
