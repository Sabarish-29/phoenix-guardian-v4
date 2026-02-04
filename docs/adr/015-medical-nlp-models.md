# ADR-015: Medical NLP Model Selection

## Status
Accepted

## Date
Day 132 (Phase 3)

## Context

Phoenix Guardian requires NLP models for:
1. Medical transcription (speech-to-text)
2. SOAP note generation
3. ICD/CPT code suggestion
4. Threat/prompt injection detection
5. Multi-language support

We need to select models that balance accuracy, latency, and cost.

## Decision

We will use a tiered model architecture with specialized models for each task.

### Model Selection

| Task | Primary Model | Fallback | Rationale |
|------|---------------|----------|-----------|
| Transcription | Whisper Large-v3 | Azure Speech | Best accuracy for medical terms |
| SOAP Generation | GPT-4 Fine-tuned | Claude 3.5 | Fine-tuned on medical notes |
| ICD Coding | BioBERT + Custom | GPT-4 | Specialized medical BERT |
| Threat Detection | Custom Classifier | GPT-4 Analysis | Low latency requirement |
| Translation | DeepL + Medical | Azure Translate | Best medical terminology |

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Model Orchestration Layer                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                   Model Router                               │ │
│  │  - Task classification                                       │ │
│  │  - Load balancing                                           │ │
│  │  - Fallback handling                                        │ │
│  └─────────────────────────────────────────────────────────────┘ │
│         │              │              │              │           │
│         ▼              ▼              ▼              ▼           │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐    │
│  │ Whisper   │  │  GPT-4    │  │  BioBERT  │  │  Custom   │    │
│  │ (ASR)     │  │  (Gen)    │  │  (Code)   │  │ (Threat)  │    │
│  └───────────┘  └───────────┘  └───────────┘  └───────────┘    │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                   GPU Inference Pool                         │ │
│  │  - A100 GPUs for large models                               │ │
│  │  - T4 GPUs for smaller models                               │ │
│  │  - Auto-scaling based on queue depth                        │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Whisper Configuration

```python
import torch
import whisper
from typing import Optional

class MedicalTranscriber:
    def __init__(self):
        self.model = whisper.load_model("large-v3")
        self.medical_vocabulary = self._load_medical_vocab()
    
    def transcribe(
        self,
        audio_path: str,
        language: Optional[str] = None
    ) -> dict:
        result = self.model.transcribe(
            audio_path,
            language=language,
            task="transcribe",
            initial_prompt=self._get_medical_prompt(),
            word_timestamps=True,
            condition_on_previous_text=True,
            temperature=0.0,  # Greedy decoding for consistency
        )
        
        # Post-process with medical vocabulary
        result["text"] = self._apply_medical_corrections(result["text"])
        
        return result
    
    def _get_medical_prompt(self) -> str:
        return """
        Medical transcription of doctor-patient encounter.
        Common terms: hypertension, diabetes mellitus, myocardial infarction,
        echocardiogram, colonoscopy, metformin, lisinopril, omeprazole.
        """
```

### Fine-tuned GPT-4 for SOAP Notes

```python
from openai import AsyncOpenAI

class SOAPGenerator:
    def __init__(self):
        self.client = AsyncOpenAI()
        self.model = "gpt-4-turbo-2024-04-09"  # Fine-tuned version
        
    async def generate(
        self,
        transcription: str,
        patient_history: dict,
        language: str = "en"
    ) -> dict:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": self._get_soap_system_prompt(language)
                },
                {
                    "role": "user",
                    "content": f"""
                    Generate a SOAP note from this encounter transcription.
                    
                    Patient History: {json.dumps(patient_history)}
                    
                    Transcription:
                    {transcription}
                    """
                }
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=4000,
        )
        
        return json.loads(response.choices[0].message.content)
```

## Consequences

### Positive
- Best-in-class accuracy for each task
- Specialized models outperform general-purpose
- Fallback ensures availability
- Fine-tuning improves medical domain performance

### Negative
- Multiple models increase complexity
- Higher infrastructure costs
- Need expertise for each model type
- Vendor dependencies

## Alternatives Considered

### Single Large Model (GPT-4 for Everything)
**Rejected because:** Higher latency for simple tasks, no specialization for medical terminology

### Open Source Only (Llama, Mistral)
**Rejected because:** Medical accuracy not yet competitive with proprietary models

### Build Custom Models
**Rejected because:** Insufficient training data and expertise for medical-grade accuracy

## References
- Whisper Paper: https://cdn.openai.com/papers/whisper.pdf
- BioBERT: https://arxiv.org/abs/1901.08746
- OpenAI Fine-tuning Guide
