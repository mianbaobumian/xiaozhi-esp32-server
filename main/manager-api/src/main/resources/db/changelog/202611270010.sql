-- 添加MiMo ASR供应器
delete from `ai_model_provider` where id = 'SYSTEM_ASR_MiMoASR';
INSERT INTO `ai_model_provider` (`id`, `model_type`, `provider_code`, `name`, `fields`, `sort`, `creator`, `create_date`, `updater`, `update_date`) VALUES
('SYSTEM_ASR_MiMoASR', 'ASR', 'mimo', 'MiMo语音识别', '[{"key":"api_key","label":"API密钥","type":"string"},{"key":"base_url","label":"API地址","type":"string"},{"key":"model_name","label":"模型","type":"string"},{"key":"language","label":"识别语种","type":"string"},{"key":"output_dir","label":"输出目录","type":"string"}]', 22, 1, NOW(), 1, NOW());

-- 添加MiMo ASR模型配置
delete from `ai_model_config` where id = 'ASR_MiMoASR';
INSERT INTO `ai_model_config` VALUES ('ASR_MiMoASR', 'ASR', 'MiMoASR', 'MiMo语音识别', 0, 1, '{\"type\": \"mimo\", \"api_key\": \"\", \"base_url\": \"https://api.xiaomimimo.com/v1\", \"model_name\": \"mimo-v2.5-asr\", \"language\": \"auto\", \"output_dir\": \"tmp/\"}', NULL, NULL, 22, NULL, NULL, NULL, NULL);

-- 更新MiMo ASR配置说明
UPDATE `ai_model_config` SET
`doc_link` = 'https://platform.xiaomimimo.com/docs/zh-CN/usage-guide/speech-recognition-v2.5',
`remark` = 'MiMo-V2.5-ASR语音识别配置说明：
1. 接口是OpenAI Chat Completions风格（不是Whisper的/v1/audio/transcriptions），音频以base64放进messages
2. 需要在 https://platform.xiaomimimo.com 获取API密钥；Token Plan用户把base_url换成 https://token-plan-cn.xiaomimimo.com/v1
3. api_key：API访问密钥
4. base_url：API地址，填到 /v1 即可，默认 https://api.xiaomimimo.com/v1
5. model_name：模型ID，目前只支持 mimo-v2.5-asr
6. language：识别语种，auto 自动检测 / zh 中文 / en 英文，已确定语种时手动指定更准
7. output_dir：临时音频目录
如需了解更多参数配置，请参考：https://platform.xiaomimimo.com/docs/zh-CN/usage-guide/speech-recognition-v2.5
' WHERE `id` = 'ASR_MiMoASR';