# Test Fixtures

## `sample_audio.wav`

Synthetic, non-patient test audio for the transcription backend scaffold (`docs/build_plan.md` task 7). Generated offline via Windows SAPI text-to-speech (`pyttsx3`, not a runtime dependency — used once to create this file, then removed). Mono, 22.05kHz, ~6.3s.

Spoken text: "This is a synthetic test recording for the ADDT ingestion pipeline. It contains no real patient information."

To regenerate:

```python
import pyttsx3

engine = pyttsx3.init()
engine.save_to_file(
    "This is a synthetic test recording for the ADDT ingestion pipeline. "
    "It contains no real patient information.",
    "tests/fixtures/sample_audio.wav",
)
engine.runAndWait()
```
