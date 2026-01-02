"""
Enhanced Voice Input System with Smart Wake Word Detection

Features:
- Levenshtein distance for fuzzy wake word matching
- Volume-based confidence scoring
- Multi-factor confidence calculation
"""

import io
import gc
import time
import struct
import asyncio
import threading
from typing import Optional, Callable
from dataclasses import dataclass
from collections import deque
import audioop

import sounddevice as sd
import numpy as np
import logging

from agent.config import settings
from agent.core.llm_client import LLMClient

logger = logging.getLogger(__name__)


def levenshtein_distance(s1: str, s2: str) -> int:
    """Calculate Levenshtein distance between two strings."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    
    if len(s2) == 0:
        return len(s1)
    
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    
    return previous_row[-1]


def levenshtein_similarity(s1: str, s2: str) -> float:
    """Convert Levenshtein distance to similarity ratio (0.0 to 1.0)."""
    distance = levenshtein_distance(s1.lower(), s2.lower())
    max_len = max(len(s1), len(s2))
    if max_len == 0:
        return 1.0
    return 1.0 - (distance / max_len)


def fuzzy_contains(target: str, text: str, threshold: float = 0.75) -> tuple[bool, float, str]:
    """Check if text contains target phrase with fuzzy matching."""
    target_lower = target.lower()
    text_lower = text.lower()
    target_words = target_lower.split()
    target_len = len(target_lower)
    
    best_similarity = 0.0
    best_match = ""
    
    words = text_lower.split()
    for i in range(len(words)):
        for j in range(i + 1, min(i + len(target_words) + 2, len(words) + 1)):
            candidate = " ".join(words[i:j])
            similarity = levenshtein_similarity(target_lower, candidate)
            
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = " ".join(text.split()[i:j])
    
    for i in range(len(text_lower) - target_len + 1):
        candidate = text_lower[i:i + target_len]
        similarity = levenshtein_similarity(target_lower, candidate)
        if similarity > best_similarity:
            best_similarity = similarity
            best_match = text[i:i + target_len]
    
    match_found = best_similarity >= threshold
    return match_found, best_similarity, best_match


def calculate_volume_confidence(rms_level: float, baseline_rms: float = 350) -> float:
    """Calculate confidence based on volume level."""
    if rms_level < baseline_rms * 0.3:
        return 0.0
    elif rms_level < baseline_rms * 0.6:
        return 0.3
    elif rms_level < baseline_rms:
        return 0.6
    elif rms_level < baseline_rms * 2:
        return 0.85
    else:
        return 1.0


def calculate_snr_estimate(audio_bytes: bytes, speech_threshold: float = 350) -> float:
    """Estimate signal-to-noise ratio by analyzing RMS variation."""
    audio_array = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32)
    
    chunk_size = 1600
    chunks = [audio_array[i:i+chunk_size] for i in range(0, len(audio_array), chunk_size)]
    
    rms_values = [np.sqrt(np.mean(chunk**2)) for chunk in chunks if len(chunk) > 0]
    
    if len(rms_values) < 2:
        return 0.5
    
    mean_rms = np.mean(rms_values)
    std_rms = np.std(rms_values)
    
    if mean_rms < speech_threshold * 0.5:
        return 0.2
    
    snr_ratio = std_rms / (mean_rms + 1e-6)
    snr_confidence = min(snr_ratio * 2, 1.0)
    
    return snr_confidence


def rms_int16_fast(raw_bytes: bytes) -> float:
    """Fast RMS calculation using audioop"""
    return audioop.rms(raw_bytes, 2) if raw_bytes else 0.0


def to_mono16k_optimized(raw_bytes: bytes, src_rate: int, src_channels: int) -> bytes:
    """Optimized conversion to mono 16kHz using audioop"""
    if src_channels > 1:
        raw_bytes = audioop.tomono(raw_bytes, 2, 0.5, 0.5)
    if src_rate != 16000:
        raw_bytes, _ = audioop.ratecv(raw_bytes, 2, 1, src_rate, 16000, None)
    return raw_bytes


def rms_float32(audio: np.ndarray) -> float:
    """Calculate RMS for float32 numpy arrays"""
    if len(audio) == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(audio))))


def to_wav_bytes(audio: np.ndarray, sample_rate: int) -> bytes:
    """Convert numpy audio array to WAV bytes"""
    buffer = io.BytesIO()
    
    if audio.ndim > 1:
        audio = audio.flatten()
    
    audio_int16 = (audio * 32767).astype(np.int16)
    
    num_channels = 1
    bytes_per_sample = 2
    byte_rate = sample_rate * num_channels * bytes_per_sample
    block_align = num_channels * bytes_per_sample
    
    subchunk2_size = len(audio_int16) * bytes_per_sample
    chunk_size = 36 + subchunk2_size
    
    buffer.write(b"RIFF")
    buffer.write(struct.pack("<I", chunk_size))
    buffer.write(b"WAVE")
    buffer.write(b"fmt ")
    buffer.write(struct.pack("<I", 16))
    buffer.write(struct.pack("<H", 1))
    buffer.write(struct.pack("<H", num_channels))
    buffer.write(struct.pack("<I", sample_rate))
    buffer.write(struct.pack("<I", byte_rate))
    buffer.write(struct.pack("<H", block_align))
    buffer.write(struct.pack("<H", 16))
    buffer.write(b"data")
    buffer.write(struct.pack("<I", subchunk2_size))
    buffer.write(audio_int16.tobytes())
    
    buffer.seek(0)
    return buffer.getvalue()


def raw_int16_to_wav(audio_bytes: bytes, sample_rate: int) -> bytes:
    """Convert raw int16 PCM bytes to WAV format"""
    num_channels = 1
    bytes_per_sample = 2
    byte_rate = sample_rate * num_channels * bytes_per_sample
    block_align = num_channels * bytes_per_sample
    
    subchunk2_size = len(audio_bytes)
    chunk_size = 36 + subchunk2_size
    
    wav_header = io.BytesIO()
    wav_header.write(b"RIFF")
    wav_header.write(struct.pack("<I", chunk_size))
    wav_header.write(b"WAVE")
    wav_header.write(b"fmt ")
    wav_header.write(struct.pack("<I", 16))
    wav_header.write(struct.pack("<H", 1))
    wav_header.write(struct.pack("<H", num_channels))
    wav_header.write(struct.pack("<I", sample_rate))
    wav_header.write(struct.pack("<I", byte_rate))
    wav_header.write(struct.pack("<H", block_align))
    wav_header.write(struct.pack("<H", 16))
    wav_header.write(b"data")
    wav_header.write(struct.pack("<I", subchunk2_size))
    
    return wav_header.getvalue() + audio_bytes


@dataclass
class VoiceCommand:
    """Recognized voice command with metadata"""
    text: str
    confidence: float
    audio_duration: float
    timestamp: float
    rms_level: float = 0.0
    fuzzy_match_score: float = 0.0
    volume_confidence: float = 0.0
    snr_confidence: float = 0.0


class AdvancedVoiceInput:
    """Enhanced voice input with smart wake word detection"""
    
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client
        self.sample_rate = 16000
        self.wake_word = settings.VOICE_WAKE_WORD.lower()
        
        self.wake_word_variations = [
            "hey theta",
            "hey, theta.",
            "hey etheta",
            "he theta",
            "a theta",
            "etheta",
            "hay theta",
            "hey tita",
            "hey, tita",
            " theta",
            "hey, teta",
            "hey data",
            "hey theda",
            "hi theta",
            "hai theta",
            "hey teeta"
        ]
        
        self.is_listening = False
        self.is_processing = False
        self._listen_thread: Optional[threading.Thread] = None
        self._command_callback: Optional[Callable[[VoiceCommand], None]] = None
        
        self.wake_word_detection_segment_ms = 1500
        self.command_min_segment_ms = 1500
        self.command_max_segment_ms = 30000
        self.command_silence_end_ms = 3000
        self.speech_rms_threshold = 350
        
        self._last_process_time = 0.0
        self._min_process_interval = 0.3
        
        self.command_history: deque[VoiceCommand] = deque(maxlen=50)
        
        self._wake_word_detected = False
        self._waiting_for_command = False
        self._wake_word_timestamp = 0.0
        self._wake_word_timeout = 20.0
        self._command_buffer = []
        
        self.wake_word_fuzzy_threshold = 0.75
        self.wake_word_confidence_threshold = 0.65
        self.volume_weight = 0.25
        self.fuzzy_weight = 0.50
        self.snr_weight = 0.25
        
        self._reference_wake_word_audio = None
        self._ambient_noise_level = 0.0
    
    async def _transcribe_audio(self, audio_bytes: bytes, language: str = "en", context: str = "") -> str:
        """Transcribe audio with optional contextual biasing"""
        if not self.llm_client:
            raise ValueError("LLM client not initialized")
        
        try:
            text = await self.llm_client.transcribe_audio(audio_bytes, language)
            return text.strip()
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return ""
    
    def _filter_hallucinations(self, text: str) -> str:
        """Enhanced hallucination filtering"""
        if not text:
            return ""
        
        text = text.strip()
        text_lower = text.lower()
        text_normalized = text_lower.rstrip(".,!?;:")
        
        blocked_phrases = {
            "thank you", "thanks", "you're welcome", "thank you very much",
            "okay", "ok", "sure", "yes", "no", "hmm", "um", "uh", "ah", "ahem",
            "[silence]", "[background noise]", "[inaudible]", "[blank_audio]",
            "hello", "hi", "hey", "wow", "awesome", "great", "nice", "good",
            "morning", "evening", "afternoon", "night",
            "huh", "huh?", "huh.", "eh", "eh?", "ahhh", "uhhh",
            "you", "me", "i", "we", "he", "she", "it", "a", "an", "the",
            "what are we talking about", "what's that", "what is that",
            "can you", "could you", "would you", "do you", "did you",
            "music playing", "background music",
            "what happened", "what's happening",
            ".", "..", "...", "?", "!",
        }
        
        if text_normalized in blocked_phrases:
            return ""
        
        if len(text) < 6:
            return ""
        
        if len(text) > 0 and text.count(text[0]) > len(text) * 0.7:
            return ""
        
        return text
    
    def _calculate_wake_word_confidence(
        self, 
        text: str, 
        audio_bytes: bytes, 
        rms_level: float
    ) -> tuple[bool, float, dict]:
        """Multi-factor confidence calculation for wake word detection."""
        fuzzy_match, fuzzy_score, matched_text = fuzzy_contains(
            self.wake_word, 
            text, 
            threshold=self.wake_word_fuzzy_threshold
        )
        
        best_variation_score = 0.0
        best_variation = ""
        for variation in self.wake_word_variations:
            match, score, _ = fuzzy_contains(variation, text, threshold=self.wake_word_fuzzy_threshold)
            if score > best_variation_score:
                best_variation_score = score
                best_variation = variation
        
        if best_variation_score > fuzzy_score:
            fuzzy_score = best_variation_score
            matched_text = best_variation
            fuzzy_match = best_variation_score >= self.wake_word_fuzzy_threshold
        
        volume_conf = calculate_volume_confidence(rms_level, self.speech_rms_threshold)
        snr_conf = calculate_snr_estimate(audio_bytes, self.speech_rms_threshold)
        
        combined_confidence = (
            fuzzy_score * self.fuzzy_weight +
            volume_conf * self.volume_weight +
            snr_conf * self.snr_weight
        )
        
        is_detected = (
            fuzzy_match and 
            combined_confidence >= self.wake_word_confidence_threshold and
            volume_conf > 0.3
        )
        
        details = {
            "fuzzy_score": fuzzy_score,
            "volume_confidence": volume_conf,
            "snr_confidence": snr_conf,
            "combined_confidence": combined_confidence,
            "matched_text": matched_text,
            "rms_level": rms_level,
            "transcribed_text": text
        }
        
        return is_detected, combined_confidence, details
    
    def _continuous_audio_loop(self):
        """Main audio capture loop with enhanced wake word detection"""
        try:
            logger.info(f"Starting audio capture at {self.sample_rate} Hz")
            
            raw_buffer = []
            target_rate = 16000
            samples_per_ms = target_rate // 1000
            
            wake_segment_samples = self.wake_word_detection_segment_ms * samples_per_ms
            wake_silence_samples = 500 * samples_per_ms
            
            cmd_min_samples = self.command_min_segment_ms * samples_per_ms
            cmd_max_samples = self.command_max_segment_ms * samples_per_ms
            cmd_silence_samples = self.command_silence_end_ms * samples_per_ms
            
            collected_samples = 0
            silent_samples = 0
            speech_detected_in_buffer = False
            
            chunk_size = 512
            gc_counter = 0
            
            with sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype=np.int16,
                blocksize=chunk_size
            ) as stream:
                
                while self.is_listening:
                    audio_chunk, overflowed = stream.read(chunk_size)
                    
                    if overflowed:
                        logger.warning("Audio overflow in InputStream")
                    
                    chunk_bytes = audio_chunk.tobytes()
                    curr_rms = rms_int16_fast(chunk_bytes)
                    
                    raw_buffer.append(chunk_bytes)
                    curr_samples = len(chunk_bytes) // 2
                    collected_samples += curr_samples
                    
                    if curr_rms >= self.speech_rms_threshold:
                        silent_samples = 0
                        speech_detected_in_buffer = True
                    else:
                        silent_samples += curr_samples
                    
                    if not self._waiting_for_command and not self.is_processing:
                        should_check_wake = (
                            (collected_samples >= wake_segment_samples and silent_samples >= wake_silence_samples)
                            or collected_samples >= wake_segment_samples * 2.5
                        )
                        
                        if should_check_wake and speech_detected_in_buffer:
                            segment_bytes = b"".join(raw_buffer)
                            segment_rms = rms_int16_fast(segment_bytes)
                            
                            if segment_rms >= 80:
                                self.is_processing = True
                                
                                threading.Thread(
                                    target=self._detect_wake_word_enhanced,
                                    args=(segment_bytes, segment_rms),
                                    daemon=True
                                ).start()
                            
                            raw_buffer.clear()
                            collected_samples = 0
                            silent_samples = 0
                            speech_detected_in_buffer = False
                    
                    elif self._waiting_for_command and not self.is_processing:
                        elapsed = time.time() - self._wake_word_timestamp
                        if elapsed > self._wake_word_timeout:
                            logger.warning("Command timeout after wake word")
                            self._waiting_for_command = False
                            self._command_buffer.clear()
                            raw_buffer.clear()
                            collected_samples = 0
                            silent_samples = 0
                            speech_detected_in_buffer = False
                            continue
                        
                        should_process_command = (
                            (collected_samples >= cmd_min_samples and 
                             silent_samples >= cmd_silence_samples and
                             speech_detected_in_buffer)
                            or collected_samples >= cmd_max_samples
                        )
                        
                        if should_process_command:
                            segment_bytes = b"".join(raw_buffer)
                            segment_rms = rms_int16_fast(segment_bytes)
                            
                            if segment_rms >= 80:
                                duration_sec = collected_samples / target_rate
                                logger.info(f"Command segment: {duration_sec:.1f}s, RMS={segment_rms:.0f}")
                                
                                self.is_processing = True
                                
                                threading.Thread(
                                    target=self._process_full_command,
                                    args=(segment_bytes, segment_rms),
                                    daemon=True
                                ).start()
                            
                            raw_buffer.clear()
                            collected_samples = 0
                            silent_samples = 0
                            speech_detected_in_buffer = False
                    
                    gc_counter += 1
                    if gc_counter > 100:
                        gc.collect(generation=0)
                        gc_counter = 0
        
        except Exception as e:
            logger.error(f"Audio loop error: {e}")
        finally:
            logger.info("Audio capture stopped")
    
    def _detect_wake_word_enhanced(self, audio_bytes: bytes, rms_level: float):
        """Enhanced wake word detection with fuzzy matching and confidence scoring"""
        try:
            wav_bytes = raw_int16_to_wav(audio_bytes, self.sample_rate)
            
            text = ""
            try:
                client_loop = getattr(self.llm_client, "_loop", None)
                if client_loop and client_loop.is_running():
                    fut = asyncio.run_coroutine_threadsafe(
                        self._transcribe_audio(wav_bytes),
                        client_loop
                    )
                    text = fut.result(timeout=30)
                else:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        text = loop.run_until_complete(self._transcribe_audio(wav_bytes))
                    finally:
                        loop.close()
            except Exception as e:
                logger.error(f"Wake word transcription error: {e}")
                return
            
            text = self._filter_hallucinations(text)
            if not text:
                return
            
            is_detected, confidence, details = self._calculate_wake_word_confidence(
                text, audio_bytes, rms_level
            )
            
            logger.info(
                f"Wake word check: '{text}' | "
                f"Detected={is_detected} | "
                f"Fuzzy={details['fuzzy_score']:.2f} | "
                f"Vol={details['volume_confidence']:.2f} | "
                f"SNR={details['snr_confidence']:.2f} | "
                f"Combined={confidence:.2f}"
            )
            
            if is_detected:
                logger.info(f"Wake word detected: confidence={confidence:.2f}")
                
                self._wake_word_detected = True
                self._wake_word_timestamp = time.time()
                self._waiting_for_command = True
                self._command_buffer.clear()
                
                matched_text = details['matched_text'].lower()
                idx = text.lower().find(matched_text)
                if idx >= 0:
                    command_text = text[idx + len(matched_text):].strip()
                    command_text = command_text.strip(".,!?;: ")
                    
                    if command_text and len(command_text) >= 10:
                        logger.info(f"Command in same segment: '{command_text}'")
                        self._emit_command(
                            command_text, 
                            rms_level, 
                            fuzzy_score=details['fuzzy_score'],
                            volume_conf=details['volume_confidence'],
                            snr_conf=details['snr_confidence']
                        )
                        self._waiting_for_command = False
                        self._wake_word_detected = False
            else:
                logger.debug(
                    f"Wake word rejected: '{text}' | "
                    f"Confidence {confidence:.2f} < {self.wake_word_confidence_threshold:.2f}"
                )
        
        except Exception as e:
            logger.error(f"Wake word detection error: {e}")
        finally:
            self.is_processing = False
    
    def _process_full_command(self, audio_bytes: bytes, rms_level: float):
        """Process full command after wake word"""
        try:
            duration_sec = len(audio_bytes) / 2 / self.sample_rate
            logger.info(f"Processing command: {duration_sec:.1f}s")
            
            wav_bytes = raw_int16_to_wav(audio_bytes, self.sample_rate)
            
            text = ""
            try:
                client_loop = getattr(self.llm_client, "_loop", None)
                if client_loop and client_loop.is_running():
                    fut = asyncio.run_coroutine_threadsafe(
                        self._transcribe_audio(wav_bytes),
                        client_loop
                    )
                    text = fut.result(timeout=30)
                else:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        text = loop.run_until_complete(self._transcribe_audio(wav_bytes))
                    finally:
                        loop.close()
            except Exception as e:
                logger.error(f"Command transcription error: {e}")
                return
            
            text = self._filter_hallucinations(text)
            
            if text:
                logger.info(f"Command transcribed: '{text}'")
                
                volume_conf = calculate_volume_confidence(rms_level, self.speech_rms_threshold)
                snr_conf = calculate_snr_estimate(audio_bytes, self.speech_rms_threshold)
                
                self._emit_command(
                    text, 
                    rms_level,
                    volume_conf=volume_conf,
                    snr_conf=snr_conf
                )
            else:
                logger.warning("No valid text in command")
            
            self._waiting_for_command = False
            self._wake_word_detected = False
        
        except Exception as e:
            logger.error(f"Command processing error: {e}")
        finally:
            self.is_processing = False
    
    def _emit_command(
        self, 
        text: str, 
        rms_level: float,
        fuzzy_score: float = 0.0,
        volume_conf: float = 0.0,
        snr_conf: float = 0.0
    ):
        """Emit command with enhanced metadata"""
        combined_conf = (
            fuzzy_score * 0.4 + 
            volume_conf * 0.3 + 
            snr_conf * 0.3
        ) if fuzzy_score > 0 else volume_conf * 0.5 + snr_conf * 0.5
        
        command = VoiceCommand(
            text=text,
            confidence=combined_conf,
            audio_duration=0.0,
            timestamp=time.time(),
            rms_level=rms_level,
            fuzzy_match_score=fuzzy_score,
            volume_confidence=volume_conf,
            snr_confidence=snr_conf
        )
        
        self.command_history.append(command)
        logger.info(f"Command captured: '{text}', confidence={combined_conf:.2f}")
        
        self.stop_listening()
        
        if self._command_callback:
            try:
                self._command_callback(command)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    def start_listening(
        self,
        callback: Callable[[VoiceCommand], None],
        wake_word_enabled: bool = True
    ):
        """Start continuous listening"""
        if self.is_listening:
            logger.warning("Already listening")
            return
        
        self._command_callback = callback
        
        if not wake_word_enabled:
            self.wake_word = None
        
        self.is_listening = True
        self._waiting_for_command = False
        self._wake_word_detected = False
        self._command_buffer.clear()
        
        self._listen_thread = threading.Thread(
            target=self._continuous_audio_loop,
            daemon=True
        )
        self._listen_thread.start()
        
        mode = f"wake word '{self.wake_word}'" if self.wake_word else "direct mode"
        logger.info(f"Listening started: {mode}")
    
    async def listen_continuous(self, callback: Callable[[VoiceCommand], None], wake_word_required: bool = True):
        """Async wrapper"""
        loop = asyncio.get_event_loop()
        
        def cb_wrapper(cmd: VoiceCommand):
            try:
                loop.call_soon_threadsafe(callback, cmd)
            except Exception as e:
                logger.error(f"Callback error: {e}")
        
        self.start_listening(callback=cb_wrapper, wake_word_enabled=wake_word_required)
        
        try:
            while self.is_listening:
                await asyncio.sleep(0.2)
        finally:
            try:
                self.stop_listening()
            except Exception:
                pass
    
    def stop_listening(self):
        """Stop listening"""
        if not self.is_listening:
            return
        
        self.is_listening = False
        self._waiting_for_command = False
        self._wake_word_detected = False
        self._command_buffer.clear()
        
        if self._listen_thread:
            self._listen_thread.join(timeout=2.0)
        
        logger.info("Listening stopped")
    
    async def listen_once(self, duration: float = 5.0, language: str = "en") -> VoiceCommand:
        """Record single command"""
        logger.info(f"Recording {duration}s")
        
        start_time = time.time()
        
        recording = sd.rec(
            int(duration * self.sample_rate),
            samplerate=self.sample_rate,
            channels=1,
            dtype=np.int16
        )
        sd.wait()
        
        rec_bytes = recording.tobytes()
        rms_level = rms_int16_fast(rec_bytes)
        
        wav_bytes = raw_int16_to_wav(rec_bytes, self.sample_rate)
        text = await self._transcribe_audio(wav_bytes, language)
        text = self._filter_hallucinations(text)
        
        volume_conf = calculate_volume_confidence(rms_level, self.speech_rms_threshold)
        snr_conf = calculate_snr_estimate(rec_bytes, self.speech_rms_threshold)
        
        command = VoiceCommand(
            text=text,
            confidence=volume_conf * 0.5 + snr_conf * 0.5,
            audio_duration=duration,
            timestamp=start_time,
            rms_level=rms_level,
            volume_confidence=volume_conf,
            snr_confidence=snr_conf
        )
        
        self.command_history.append(command)
        return command
    
    async def test_microphone(self) -> bool:
        """Test microphone"""
        try:
            logger.info("Testing microphone")
            command = await self.listen_once(duration=3.0)
            
            if command.text:
                logger.info(f"Microphone test success: '{command.text}'")
                return True
            else:
                logger.warning("No speech detected in microphone test")
                return False
        except Exception as e:
            logger.error(f"Microphone test failed: {e}")
            return False
    
    def set_sensitivity(self, level: str):
        """Adjust sensitivity"""
        sensitivity_map = {
            "low": 200,
            "medium": 350,
            "high": 500,
            "max": 800,
        }
        
        self.speech_rms_threshold = sensitivity_map.get(level, 350)
        logger.info(f"Sensitivity set to {level}: RMS={self.speech_rms_threshold}")
    
    def set_fuzzy_threshold(self, threshold: float):
        """Adjust fuzzy matching threshold (0.0-1.0)"""
        self.wake_word_fuzzy_threshold = max(0.0, min(1.0, threshold))
        logger.info(f"Fuzzy threshold set to {self.wake_word_fuzzy_threshold:.2f}")
    
    def set_confidence_threshold(self, threshold: float):
        """Adjust minimum confidence threshold (0.0-1.0)"""
        self.wake_word_confidence_threshold = max(0.0, min(1.0, threshold))
        logger.info(f"Confidence threshold set to {self.wake_word_confidence_threshold:.2f}")
    
    def get_last_command(self) -> Optional[VoiceCommand]:
        """Get last command"""
        return self.command_history[-1] if self.command_history else None


VoiceInput = AdvancedVoiceInput


class VoiceCommandProcessor:
    """Process voice commands"""
    
    def __init__(self, voice_input: AdvancedVoiceInput):
        self.voice_input = voice_input
    
    def is_confirmation(self, text: str) -> bool:
        confirmations = [
            "yes", "yeah", "yep", "sure", "ok", "okay",
            "confirm", "proceed", "go ahead", "do it"
        ]
        text_lower = text.lower().strip()
        return any(word in text_lower for word in confirmations)
    
    def is_cancellation(self, text: str) -> bool:
        cancellations = [
            "no", "nope", "cancel", "stop", "abort",
            "nevermind", "never mind", "don't"
        ]
        text_lower = text.lower().strip()
        return any(word in text_lower for word in cancellations)
    
    def is_pause_command(self, text: str) -> bool:
        pause_words = ["pause", "wait", "hold on", "hold", "stop listening"]
        text_lower = text.lower().strip()
        return any(word in text_lower for word in pause_words)


async def main():
    """Demo with enhanced wake word detection"""
    async with LLMClient() as client:
        voice = AdvancedVoiceInput(client)
        
        voice.set_sensitivity("medium")
        voice.set_fuzzy_threshold(0.75)
        voice.set_confidence_threshold(0.65)
        
        logger.info("Testing microphone")
        await voice.test_microphone()
        
        processor = VoiceCommandProcessor(voice)
        
        def handle_command(cmd: VoiceCommand):
            logger.info(f"Command received: '{cmd.text}', confidence={cmd.confidence:.2f}")
            
            if processor.is_confirmation(cmd.text):
                logger.info("Confirmation detected")
            elif processor.is_cancellation(cmd.text):
                logger.info("Cancellation detected")
            else:
                logger.info(f"Executing command: {cmd.text}")
        
        voice.start_listening(
            callback=handle_command,
            wake_word_enabled=True
        )
        
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Stopping voice input")
            voice.stop_listening()


if __name__ == "__main__":
    asyncio.run(main())
