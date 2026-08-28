#!/bin/sh
set -eu

: "${VOICE_LLM_MODEL:?VOICE_LLM_MODEL is required}"
: "${VOICE_LLM_BASE_URL:?VOICE_LLM_BASE_URL is required}"
: "${VOICE_LLM_API_KEY:?VOICE_LLM_API_KEY is required}"

VOICE_AGENT_PORT="${VOICE_AGENT_PORT:-8765}"
VOICE_STT_BACKEND="${VOICE_STT_BACKEND:-faster-whisper}"
VOICE_STT_MODEL="${VOICE_STT_MODEL:-small}"
VOICE_STT_DEVICE="${VOICE_STT_DEVICE:-auto}"
VOICE_STT_COMPUTE_TYPE="${VOICE_STT_COMPUTE_TYPE:-auto}"
VOICE_STT_LANGUAGE="${VOICE_STT_LANGUAGE:-th}"
VOICE_TTS_BACKEND="${VOICE_TTS_BACKEND:-qwen3}"
VOICE_TTS_MODEL="${VOICE_TTS_MODEL:-Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice}"
VOICE_TTS_SPEAKER="${VOICE_TTS_SPEAKER:-Aiden}"
VOICE_TTS_LANGUAGE="${VOICE_TTS_LANGUAGE:-auto}"
VOICE_TTS_DEVICE="${VOICE_TTS_DEVICE:-cpu}"
VOICE_TTS_BACKEND_ENGINE="${VOICE_TTS_BACKEND_ENGINE:-ggml}"
VOICE_TTS_QUANTIZATION="${VOICE_TTS_QUANTIZATION:-Q4_K_M}"
VOICE_NUM_PIPELINES="${VOICE_NUM_PIPELINES:-1}"
VOICE_VAD_THRESHOLD="${VOICE_VAD_THRESHOLD:-0.6}"
VOICE_MIN_SPEECH_MS="${VOICE_MIN_SPEECH_MS:-250}"
VOICE_MIN_SILENCE_MS="${VOICE_MIN_SILENCE_MS:-500}"
VOICE_CHAT_SIZE="${VOICE_CHAT_SIZE:-30}"
VOICE_LOG_LEVEL="${VOICE_LOG_LEVEL:-info}"
VOICE_REASONING_EFFORT="${VOICE_REASONING_EFFORT:-none}"
VOICE_QWEN3_NON_STREAMING="${VOICE_QWEN3_NON_STREAMING:-True}"

set -- speech-to-speech \
  --mode realtime \
  --ws_host 0.0.0.0 \
  --ws_port "${VOICE_AGENT_PORT}" \
  --stt "${VOICE_STT_BACKEND}" \
  --llm_backend chat-completions \
  --tts "${VOICE_TTS_BACKEND}" \
  --model_name "${VOICE_LLM_MODEL}" \
  --responses_api_base_url "${VOICE_LLM_BASE_URL}" \
  --responses_api_api_key "${VOICE_LLM_API_KEY}" \
  --responses_api_reasoning_effort "${VOICE_REASONING_EFFORT}" \
  --chat_size "${VOICE_CHAT_SIZE}" \
  --thresh "${VOICE_VAD_THRESHOLD}" \
  --min_speech_ms "${VOICE_MIN_SPEECH_MS}" \
  --min_silence_ms "${VOICE_MIN_SILENCE_MS}" \
  --num_pipelines "${VOICE_NUM_PIPELINES}" \
  --log_level "${VOICE_LOG_LEVEL}"

if [ "${VOICE_STT_BACKEND}" = "faster-whisper" ]; then
  set -- "$@" \
    --faster_whisper_stt_model_name "${VOICE_STT_MODEL}" \
    --faster_whisper_stt_device "${VOICE_STT_DEVICE}" \
    --faster_whisper_stt_compute_type "${VOICE_STT_COMPUTE_TYPE}" \
    --faster_whisper_stt_gen_language "${VOICE_STT_LANGUAGE}"
elif [ "${VOICE_STT_BACKEND}" = "whisper" ]; then
  set -- "$@" --whisper_stt_model_name "${VOICE_STT_MODEL}"
fi

if [ "${VOICE_TTS_BACKEND}" = "qwen3" ]; then
  set -- "$@" \
    --qwen3_tts_model_name "${VOICE_TTS_MODEL}" \
    --qwen3_tts_speaker "${VOICE_TTS_SPEAKER}" \
    --qwen3_tts_language "${VOICE_TTS_LANGUAGE}" \
    --qwen3_tts_device "${VOICE_TTS_DEVICE}" \
    --qwen3_tts_backend "${VOICE_TTS_BACKEND_ENGINE}" \
    --qwen3_tts_ggml_quantization "${VOICE_TTS_QUANTIZATION}" \
    --qwen3_tts_non_streaming_mode "${VOICE_QWEN3_NON_STREAMING}"
fi

exec "$@"
