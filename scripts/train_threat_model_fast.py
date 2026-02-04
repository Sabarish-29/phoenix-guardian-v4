"""Train TF-IDF + Logistic Regression threat detection model.

This is a fast, CPU-friendly alternative to the RoBERTa model.
Trains in seconds while still achieving high accuracy for threat detection.
"""
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, 
    precision_recall_fscore_support, 
    roc_auc_score,
    classification_report,
    confusion_matrix
)
import joblib
import json
import os


def train_threat_detector():
    """Train TF-IDF + Logistic Regression threat detection model."""
    
    print("Loading data...")
    df = pd.read_csv("data/threat_detection_dataset.csv")
    
    # Split data
    train_df, val_df = train_test_split(
        df, test_size=0.2, random_state=42, stratify=df['label']
    )
    
    print(f"Total samples: {len(df)}")
    print(f"Train samples: {len(train_df)}")
    print(f"Validation samples: {len(val_df)}")
    print(f"Positive class (threats): {df['label'].sum()} ({df['label'].mean():.2%})")
    
    # Create TF-IDF vectorizer
    print("\nCreating TF-IDF features...")
    vectorizer = TfidfVectorizer(
        max_features=5000,
        ngram_range=(1, 3),  # Capture SQL injection patterns like "DROP TABLE"
        analyzer='char_wb',  # Character n-grams for XSS patterns like "<script>"
        min_df=2,
        max_df=0.95
    )
    
    X_train = vectorizer.fit_transform(train_df['text'])
    X_val = vectorizer.transform(val_df['text'])
    y_train = train_df['label'].values
    y_val = val_df['label'].values
    
    print(f"Feature matrix shape: {X_train.shape}")
    
    # Train logistic regression
    print("\nTraining Logistic Regression model...")
    model = LogisticRegression(
        max_iter=1000,
        class_weight='balanced',
        random_state=42,
        C=1.0,
        solver='lbfgs'
    )
    model.fit(X_train, y_train)
    
    # Predictions
    print("\nEvaluating model...")
    y_pred = model.predict(X_val)
    y_pred_proba = model.predict_proba(X_val)[:, 1]
    
    # Calculate metrics
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_val, y_pred, average='binary'
    )
    accuracy = accuracy_score(y_val, y_pred)
    auc = roc_auc_score(y_val, y_pred_proba)
    cm = confusion_matrix(y_val, y_pred)
    
    metrics = {
        "accuracy": float(accuracy),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "auc": float(auc),
        "num_train_samples": len(train_df),
        "num_val_samples": len(val_df),
        "model_type": "TF-IDF + Logistic Regression",
        "confusion_matrix": {
            "tn": int(cm[0, 0]),
            "fp": int(cm[0, 1]),
            "fn": int(cm[1, 0]),
            "tp": int(cm[1, 1])
        }
    }
    
    # Save model and vectorizer
    print("\nSaving model...")
    os.makedirs("models/threat_detector", exist_ok=True)
    joblib.dump(model, "models/threat_detector/model.joblib")
    joblib.dump(vectorizer, "models/threat_detector/vectorizer.joblib")
    
    # Save metrics
    with open("models/threat_detector_metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)
    
    # Print results
    print(f"\n{'='*50}")
    print("✅ TRAINING COMPLETE!")
    print(f"{'='*50}")
    print(f"\n📊 Performance Metrics:")
    print(f"   Accuracy:  {accuracy:.4f}")
    print(f"   Precision: {precision:.4f}")
    print(f"   Recall:    {recall:.4f}")
    print(f"   F1 Score:  {f1:.4f}")
    print(f"   AUC:       {auc:.4f}")
    print(f"\n📈 Confusion Matrix:")
    print(f"   TN: {cm[0,0]:4d}  FP: {cm[0,1]:4d}")
    print(f"   FN: {cm[1,0]:4d}  TP: {cm[1,1]:4d}")
    print(f"\n📁 Model saved to: models/threat_detector/")
    print(f"📁 Metrics saved to: models/threat_detector_metrics.json")
    
    # Test a few examples
    print(f"\n🔍 Sample Predictions:")
    test_samples = [
        "Patient presents with chest pain",
        "'; DROP TABLE patients;--",
        "<script>alert(1)</script>",
        "Schedule follow-up for diabetes management",
        "../../etc/passwd"
    ]
    
    for sample in test_samples:
        vec = vectorizer.transform([sample])
        pred = model.predict(vec)[0]
        prob = model.predict_proba(vec)[0][1]
        label = "🚨 THREAT" if pred == 1 else "✅ SAFE"
        print(f"   {label} ({prob:.2%}): {sample[:50]}")
    
    return metrics


if __name__ == "__main__":
    train_threat_detector()
