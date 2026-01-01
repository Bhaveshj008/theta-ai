"""
Advanced Voice Input System - IMPROVED VERSION

Behavior:
- Uses audioop-based processing for speed
- Wake word and VAD tuned from real usage
- Once a command is captured and emitted, listening is stopped.
- After your task is done, you can start listening again explicitly.
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


# ===================== Fast Audio Processing (from Interview Copilot) =====================


def rms_int16_fast(raw_bytes: bytes) -> float:
    """Fast RMS calculation using audioop (much faster than numpy)"""
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
    
    # Ensure audio is 1D
    if audio.ndim > 1:
        audio = audio.flatten()
    
    # Convert float32 to int16
    audio_int16 = (audio * 32767).astype(np.int16)
    
    # Write WAV header
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


# ===================== Voice Command Data =====================


@dataclass
class VoiceCommand:
    """Recognized voice command with metadata"""
    text: str
    confidence: float
    audio_duration: float
    timestamp: float
    rms_level: float = 0.0


# ===================== Advanced Voice Input =====================


class AdvancedVoiceInput:
    """
    Real-time voice input with Interview Copilot techniques:
    - Fast audioop-based processing
    - Optimized RMS thresholds
    - Tuned segmentation parameters
    - Aggressive garbage collection
    - Wake word matching
    - Once a command is emitted, listening stops; you manually restart after task completion.
    """
    
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client
        self.sample_rate = 16000  # Fixed at 16kHz
        self.wake_word = settings.VOICE_WAKE_WORD.lower()
        
        # Wake word variations
        self.wake_word_variations = [
            "hey Theta",
            "hey, Theta.",
            "hey eTheta",
            "he Theta",
            "a Theta",
            "eTheta",
            "he Theta",
            "hay Theta",
            "hey tita",
            "hey, tita",
            " theta",
            "hey, teta"
        ]
        
        # State management
        self.is_listening = False
        self.is_processing = False
        self._listen_thread: Optional[threading.Thread] = None
        
        # Callback for recognized commands
        self._command_callback: Optional[Callable[[VoiceCommand], None]] = None
        
        # VAD and segmentation
        self.min_segment_ms = 600
        self.max_segment_ms = 12000
        self.silence_end_ms = 400
        self.speech_rms_threshold = 350
        
        # Processing throttle
        self._last_process_time = 0.0
        self._min_process_interval = 1.0
        
        # Command history
        self.command_history: deque[VoiceCommand] = deque(maxlen=50)
        
        # Wake word state
        self._wake_word_detected = False
        self._waiting_for_command = False
        self._wake_word_timestamp = 0.0
        self._wake_word_timeout = 15.0
    
    # ===================== Core Transcription =====================
    
    async def _transcribe_audio(self, audio_bytes: bytes, language: str = "en") -> str:
        """Transcribe audio using LLMClient/Whisper with error handling"""
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
    
    # ===================== Continuous Audio Processing =====================
    
    def _continuous_audio_loop(self):
        """Main audio capture loop"""
        try:
            logger.info(f"Starting audio capture at {self.sample_rate} Hz")
            
            raw_buffer = []
            target_rate = 16000
            samples_per_ms = target_rate // 1000
            
            min_segment_samples = self.min_segment_ms * samples_per_ms
            max_segment_samples = self.max_segment_ms * samples_per_ms
            silence_end_samples = self.silence_end_ms * samples_per_ms
            
            collected_samples = 0
            silent_samples = 0
            
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
                    else:
                        silent_samples += curr_samples
                    
                    should_process = (
                        (collected_samples >= min_segment_samples and
                         silent_samples >= silence_end_samples)
                        or collected_samples >= max_segment_samples
                    )
                    
                    if should_process and not self.is_processing:
                        current_time = time.time()
                        time_since_last = current_time - self._last_process_time
                        
                        if collected_samples >= min_segment_samples and time_since_last >= self._min_process_interval:
                            segment_bytes = b"".join(raw_buffer)
                            segment_rms = rms_int16_fast(segment_bytes)
                            
                            if segment_rms >= 80:
                                self.is_processing = True
                                self._last_process_time = current_time
                                
                                threading.Thread(
                                    target=self._process_audio_segment,
                                    args=(segment_bytes, segment_rms),
                                    daemon=True
                                ).start()
                            
                            raw_buffer.clear()
                            collected_samples = 0
                            silent_samples = 0
                    
                    gc_counter += 1
                    if gc_counter > 100:
                        gc.collect(generation=0)
                        gc_counter = 0
        
        except Exception as e:
            logger.error(f"Audio loop error: {e}")
        finally:
            logger.info("Audio capture stopped")
    
    def _process_audio_segment(self, audio_bytes: bytes, rms_level: float):
        """Process audio segment with int16 bytes"""
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
                logger.error(f"Transcription error: {e}")
                return
            
            text = self._filter_hallucinations(text)
            if not text:
                return
            
            logger.info(f"Transcribed: '{text}' (RMS={rms_level:.0f})")
            
            text_lower = text.lower()
            
            if self.wake_word and not self._waiting_for_command:
                matched, matched_text = self._match_wake_word(text)
                if matched:
                    logger.info(f"Wake word matched: '{matched_text}'")
                    self._wake_word_detected = True
                    self._wake_word_timestamp = time.time()
                    
                    idx = text_lower.find(matched_text)
                    command_text = text[idx + len(matched_text):].strip()
                    command_text = command_text.strip(".,!?;: ")
                    
                    if command_text and len(command_text) >= 5:
                        logger.info(f"Immediate command: '{command_text}'")
                        self._emit_command(command_text, rms_level)
                        self._waiting_for_command = False
                        self._wake_word_detected = False
                    else:
                        logger.info("Waiting for command after wake word")
                        print("\nSAY YOUR COMMAND NOW\n")
                        self._waiting_for_command = True
                else:
                    return
            
            elif self._waiting_for_command:
                elapsed = time.time() - self._wake_word_timestamp
                if elapsed > self._wake_word_timeout:
                    logger.warning("Wake word timeout, resetting state")
                    self._waiting_for_command = False
                    self._wake_word_detected = False
                    return
                
                logger.info(f"Command after wake word: '{text}'")
                self._emit_command(text, rms_level)
                self._waiting_for_command = False
                self._wake_word_detected = False
            
            elif not self.wake_word:
                self._emit_command(text, rms_level)
        
        except Exception as e:
            logger.error(f"Processing error: {e}")
        finally:
            self.is_processing = False
    
    def _emit_command(self, text: str, rms_level: float):
        """
        Emit voice command to callback.
        Important: This stops listening once a command is emitted.
        """
        command = VoiceCommand(
            text=text,
            confidence=1.0,
            audio_duration=0.0,
            timestamp=time.time(),
            rms_level=rms_level
        )
        
        self.command_history.append(command)
        
        logger.info(f"Stopping listener after command: '{text}'")
        self.stop_listening()
        
        if self._command_callback:
            try:
                self._command_callback(command)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    # ===================== Public Interface =====================
    
    def _match_wake_word(self, text: str) -> tuple[bool, str]:
        """Check if text contains wake word or variation"""
        text_lower = text.lower()
        
        if self.wake_word and self.wake_word in text_lower:
            return True, self.wake_word
        
        for variation in self.wake_word_variations:
            if variation in text_lower:
                return True, variation
        
        return False, ""
    
    def start_listening(
        self,
        callback: Callable[[VoiceCommand], None],
        wake_word_enabled: bool = True
    ):
        """Start continuous listening mode"""
        if self.is_listening:
            logger.warning("Already listening")
            return
        
        self._command_callback = callback
        
        if not wake_word_enabled:
            self.wake_word = None
        
        self.is_listening = True
        self._listen_thread = threading.Thread(
            target=self._continuous_audio_loop,
            daemon=True
        )
        self._listen_thread.start()
        
        mode = f"wake word '{self.wake_word}'" if self.wake_word else "direct mode"
        logger.info(f"Listening started with {mode}")
        print(f"\nVoice active - {mode}")
        print(f"   RMS threshold: {self.speech_rms_threshold}")
        if self.wake_word:
            print(f"   Say: '{self.wake_word.upper()}'\n")
    
    async def listen_continuous(self, callback: Callable[[VoiceCommand], None], wake_word_required: bool = True):
        """Async compatibility wrapper"""
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
        """Stop continuous listening"""
        if not self.is_listening:
            return
        
        self.is_listening = False
        self._waiting_for_command = False
        self._wake_word_detected = False
        
        if self._listen_thread:
            self._listen_thread.join(timeout=2.0)
        
        logger.info("Listening stopped")
        print("\nVoice stopped\n")
    
    async def listen_once(
        self,
        duration: float = 5.0,
        language: str = "en"
    ) -> VoiceCommand:
        """Record and transcribe a single command"""
        logger.info(f"Recording {duration} seconds")
        
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
        
        command = VoiceCommand(
            text=text,
            confidence=1.0,
            audio_duration=duration,
            timestamp=start_time,
            rms_level=rms_level
        )
        
        self.command_history.append(command)
        return command
    
    async def test_microphone(self) -> bool:
        """Test microphone"""
        try:
            logger.info("Testing microphone")
            print("\nSpeak now...")
            command = await self.listen_once(duration=3.0)
            
            if command.text:
                logger.info(f"Microphone test success: '{command.text}'")
                print(f"Captured: '{command.text}'\n")
                return True
            else:
                logger.warning("No speech detected in mic test")
                print("No speech detected, speak louder\n")
                return False
        except Exception as e:
            logger.error(f"Microphone test failed: {e}")
            print(f"Microphone test failed: {e}\n")
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
        logger.info(f"Sensitivity set to {level} (RMS={self.speech_rms_threshold})")
        print(f"\nSensitivity: {level.upper()} (RMS threshold: {self.speech_rms_threshold})\n")
    
    def get_last_command(self) -> Optional[VoiceCommand]:
        """Get last command"""
        return self.command_history[-1] if self.command_history else None


# Backwards compatibility
VoiceInput = AdvancedVoiceInput


# ===================== Command Processor =====================


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


# ===================== Example Usage =====================


async def main():
    """Demo"""
    async with LLMClient() as client:
        voice = AdvancedVoiceInput(client)
        
        voice.set_sensitivity("medium")
        
        print("\nTesting microphone...")
        if await voice.test_microphone():
            print("Microphone OK\n")
        
        processor = VoiceCommandProcessor(voice)
        
        def handle_command(cmd: VoiceCommand):
            print(f"\nCommand: '{cmd.text}' (RMS={cmd.rms_level:.0f})")
            
            if processor.is_confirmation(cmd.text):
                print("   -> Confirmed")
            elif processor.is_cancellation(cmd.text):
                print("   -> Cancelled")
            elif processor.is_pause_command(cmd.text):
                print("   -> Pausing (already stopped after command)")
            else:
                print("   -> Here you run your task for this command")
            
            # When your task is finished, you can restart listening:
            # voice.start_listening(callback=handle_command, wake_word_enabled=True)
            # Or keep it stopped if you want one-shot behavior.
        
        print(f"Say '{voice.wake_word}' plus your command...")
        print("Press Ctrl+C to stop\n")
        
        voice.start_listening(
            callback=handle_command,
            wake_word_enabled=True
        )
        
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping...")
            voice.stop_listening()


if __name__ == "__main__":
    asyncio.run(main())
