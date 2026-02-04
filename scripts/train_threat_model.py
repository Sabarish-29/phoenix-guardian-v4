"""Train RoBERTa-based threat detection model."""
from transformers import (
    RobertaTokenizer, 
    RobertaForSequenceClassification, 
    Trainer, 
    TrainingArguments,
    EarlyStoppingCallback
)
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, roc_auc_score
import pandas as pd
import torch
import json
import os
from scipy.special import softmax

class ThreatDataset(torch.utils.data.Dataset):
    """Dataset for threat detection."""
    def __init__(self, encodings, labels):
        self.encodings = encodings
        self.labels = labels
    
    def __len__(self):
        return len(self.labels)
    
    def __getitem__(self, idx):
        item = {key: torch.tensor(val[idx]) for key, val in self.encodings.items()}
        item['labels'] = torch.tensor(self.labels[idx])
        return item

def compute_metrics(eval_pred):
    """Compute metrics during training."""
    logits, labels = eval_pred
    predictions = logits.argmax(axis=-1)
    precision, recall, f1, _ = precision_recall_fscore_support(
        labels, predictions, average='binary'
    )
    acc = accuracy_score(labels, predictions)
    return {
        'accuracy': acc,
        'f1': f1,
        'precision': precision,
        'recall': recall
    }

def compute_final_metrics(predictions, labels):
    """Compute final metrics with AUC."""
    logits = predictions.predictions
    preds = logits.argmax(axis=-1)
    probs = softmax(logits, axis=-1)[:, 1]
    
    precision, recall, f1, _ = precision_recall_fscore_support(
        labels, preds, average='binary'
    )
    acc = accuracy_score(labels, preds)
    auc = roc_auc_score(labels, probs)
    
    return {
        "accuracy": float(acc),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "auc": float(auc),
        "num_samples": len(labels)
    }

def train_threat_detector():
    """Train RoBERTa-based threat detection model."""
    print("Loading data...")
    df = pd.read_csv("data/threat_detection_dataset.csv")
    train_df, val_df = train_test_split(df, test_size=0.2, random_state=42, stratify=df['label'])
    
    print(f"Train samples: {len(train_df)}")
    print(f"Validation samples: {len(val_df)}")
    
    print("Loading tokenizer and model...")
    tokenizer = RobertaTokenizer.from_pretrained("roberta-base")
    model = RobertaForSequenceClassification.from_pretrained(
        "roberta-base", 
        num_labels=2
    )
    
    print("Tokenizing data...")
    train_encodings = tokenizer(
        train_df['text'].tolist(), 
        truncation=True, 
        padding=True, 
        max_length=128
    )
    val_encodings = tokenizer(
        val_df['text'].tolist(), 
        truncation=True, 
        padding=True, 
        max_length=128
    )
    
    train_dataset = ThreatDataset(train_encodings, train_df['label'].tolist())
    val_dataset = ThreatDataset(val_encodings, val_df['label'].tolist())
    
    # Training arguments
    training_args = TrainingArguments(
        output_dir='./models/threat_detector_checkpoints',
        num_train_epochs=3,
        per_device_train_batch_size=16,
        per_device_eval_batch_size=16,
        warmup_steps=100,
        weight_decay=0.01,
        logging_dir='./logs/threat_detector',
        logging_steps=50,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="f1",
        save_total_limit=2,
    )
    
    print("Starting training...")
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        compute_metrics=compute_metrics,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=2)]
    )
    
    trainer.train()
    
    print("Saving model...")
    os.makedirs("models/threat_detector_roberta", exist_ok=True)
    model.save_pretrained("models/threat_detector_roberta")
    tokenizer.save_pretrained("models/threat_detector_roberta")
    
    print("Computing final metrics...")
    predictions = trainer.predict(val_dataset)
    metrics = compute_final_metrics(predictions, val_df['label'].values)
    
    # Save metrics
    with open("models/threat_detector_metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)
    
    print(f"\n✅ Training complete!")
    print(f"   Accuracy: {metrics['accuracy']:.4f}")
    print(f"   Precision: {metrics['precision']:.4f}")
    print(f"   Recall: {metrics['recall']:.4f}")
    print(f"   F1 Score: {metrics['f1']:.4f}")
    print(f"   AUC: {metrics['auc']:.4f}")
    
    return metrics

if __name__ == "__main__":
    train_threat_detector()
