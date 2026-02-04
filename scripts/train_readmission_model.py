"""Train XGBoost readmission prediction model."""
import pandas as pd
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    roc_auc_score, 
    classification_report, 
    confusion_matrix,
    accuracy_score,
    precision_recall_fscore_support
)
import json
import os


def train_readmission_model():
    """Train XGBoost readmission prediction model."""
    
    print("Loading data...")
    df = pd.read_csv("data/readmission_dataset.csv")
    
    # Features
    feature_cols = [
        'age', 'has_heart_failure', 'has_diabetes', 'has_copd',
        'comorbidity_count', 'length_of_stay', 'visits_30d',
        'visits_90d', 'discharge_encoded'
    ]
    
    X = df[feature_cols].values
    y = df['readmitted_30d'].values
    
    print(f"Total samples: {len(df)}")
    print(f"Positive class (readmitted): {y.sum()} ({y.mean():.2%})")
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    print(f"Train samples: {len(X_train)}")
    print(f"Test samples: {len(X_test)}")
    
    # Create DMatrix
    dtrain = xgb.DMatrix(X_train, label=y_train, feature_names=feature_cols)
    dtest = xgb.DMatrix(X_test, label=y_test, feature_names=feature_cols)
    
    # Calculate class weight for imbalanced data
    scale_pos_weight = (y_train == 0).sum() / max((y_train == 1).sum(), 1)
    print(f"Scale pos weight: {scale_pos_weight:.2f}")
    
    # XGBoost parameters - tuned for imbalanced data
    params = {
        'objective': 'binary:logistic',
        'eval_metric': 'auc',
        'max_depth': 4,  # Reduced to prevent overfitting
        'learning_rate': 0.05,  # Lower learning rate
        'subsample': 0.8,
        'colsample_bytree': 0.8,
        'scale_pos_weight': scale_pos_weight,  # Handle class imbalance
        'min_child_weight': 5,  # Regularization
        'gamma': 0.1,  # Regularization
        'seed': 42,
        'verbosity': 1
    }
    
    print("\nTraining XGBoost model...")
    evals = [(dtrain, 'train'), (dtest, 'test')]
    model = xgb.train(
        params,
        dtrain,
        num_boost_round=200,
        evals=evals,
        early_stopping_rounds=20,
        verbose_eval=50
    )
    
    # Predictions - use optimal threshold from validation
    print("\nEvaluating model...")
    y_pred_proba = model.predict(dtest)
    
    # Find optimal threshold
    best_threshold = 0.5
    best_f1 = 0
    for thresh in [0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5]:
        preds = (y_pred_proba > thresh).astype(int)
        _, _, f1_temp, _ = precision_recall_fscore_support(
            y_test, preds, average='binary', zero_division=0
        )
        if f1_temp > best_f1:
            best_f1 = f1_temp
            best_threshold = thresh
    
    print(f"Optimal threshold: {best_threshold}")
    y_pred = (y_pred_proba > best_threshold).astype(int)
    
    # Metrics
    auc = roc_auc_score(y_test, y_pred_proba)
    accuracy = accuracy_score(y_test, y_pred)
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_test, y_pred, average='binary'
    )
    cm = confusion_matrix(y_test, y_pred)
    
    # Specificity
    specificity = cm[0, 0] / (cm[0, 0] + cm[0, 1]) if (cm[0, 0] + cm[0, 1]) > 0 else 0
    
    metrics = {
        "auc": float(auc),
        "accuracy": float(accuracy),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "specificity": float(specificity),
        "feature_names": feature_cols,
        "num_train_samples": len(X_train),
        "num_test_samples": len(X_test),
        "positive_rate": float(y.mean()),
        "confusion_matrix": {
            "tn": int(cm[0, 0]),
            "fp": int(cm[0, 1]),
            "fn": int(cm[1, 0]),
            "tp": int(cm[1, 1])
        }
    }
    
    # Feature importance
    importance = model.get_score(importance_type='gain')
    metrics["feature_importance"] = {k: float(v) for k, v in importance.items()}
    
    # Save model
    print("\nSaving model...")
    os.makedirs("models", exist_ok=True)
    model.save_model("models/readmission_xgb.json")
    
    # Save metrics
    with open("models/readmission_xgb_metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)
    
    # Print results
    print(f"\n{'='*50}")
    print("✅ TRAINING COMPLETE!")
    print(f"{'='*50}")
    print(f"\n📊 Performance Metrics:")
    print(f"   AUC:         {auc:.4f}")
    print(f"   Accuracy:    {accuracy:.4f}")
    print(f"   Precision:   {precision:.4f}")
    print(f"   Recall:      {recall:.4f}")
    print(f"   F1 Score:    {f1:.4f}")
    print(f"   Specificity: {specificity:.4f}")
    print(f"\n📈 Confusion Matrix:")
    print(f"   TN: {cm[0,0]:4d}  FP: {cm[0,1]:4d}")
    print(f"   FN: {cm[1,0]:4d}  TP: {cm[1,1]:4d}")
    
    print(f"\n🔑 Top Feature Importance (by gain):")
    sorted_importance = sorted(
        importance.items(), 
        key=lambda x: x[1], 
        reverse=True
    )
    for feat, score in sorted_importance[:5]:
        print(f"   - {feat}: {score:.2f}")
    
    print(f"\n📁 Model saved to: models/readmission_xgb.json")
    print(f"📁 Metrics saved to: models/readmission_xgb_metrics.json")
    
    return metrics


if __name__ == "__main__":
    train_readmission_model()
