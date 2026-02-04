"""Generate synthetic patient readmission data."""
import pandas as pd
import numpy as np
from faker import Faker

fake = Faker()
Faker.seed(42)
np.random.seed(42)


def generate_readmission_dataset(n_patients=2000):
    """Generate synthetic patient encounter data with readmission outcomes."""
    
    print(f"Generating {n_patients} patient records...")
    data = []
    
    for i in range(n_patients):
        # Patient demographics
        age = np.random.normal(65, 15)
        age = max(18, min(100, age))
        
        # Comorbidities (more comorbidities = higher readmission risk)
        has_hf = np.random.random() < 0.15  # Heart failure
        has_diabetes = np.random.random() < 0.20
        has_copd = np.random.random() < 0.12
        comorbidity_count = sum([has_hf, has_diabetes, has_copd])
        
        # Hospital stay length (longer stays often = sicker patients)
        los = max(1, int(np.random.exponential(3.5 + comorbidity_count)))
        
        # Recent healthcare utilization
        visits_30d = np.random.poisson(0.5 + comorbidity_count * 0.3)
        visits_90d = visits_30d + np.random.poisson(0.8)
        
        # Discharge destination (correlates with readmission)
        if comorbidity_count > 1:
            discharge = np.random.choice(
                ['home', 'snf', 'rehab'], 
                p=[0.5, 0.3, 0.2]
            )
        else:
            discharge = np.random.choice(
                ['home', 'snf', 'rehab'], 
                p=[0.8, 0.1, 0.1]
            )
        
        # Calculate readmission probability based on risk factors
        # More pronounced effects for better ML signal
        base_risk = 0.05
        if has_hf: base_risk += 0.18
        if has_diabetes: base_risk += 0.08
        if has_copd: base_risk += 0.12
        if los > 7: base_risk += 0.12
        if discharge == 'snf': base_risk += 0.15
        if visits_30d > 1: base_risk += 0.10
        if age > 75: base_risk += 0.08
        
        # Cap maximum risk
        base_risk = min(base_risk, 0.70)
        
        # Determine readmission outcome
        readmitted = np.random.random() < base_risk
        
        data.append({
            'patient_id': f'PAT{i:05d}',
            'age': round(age, 1),
            'has_heart_failure': int(has_hf),
            'has_diabetes': int(has_diabetes),
            'has_copd': int(has_copd),
            'comorbidity_count': comorbidity_count,
            'length_of_stay': los,
            'visits_30d': visits_30d,
            'visits_90d': visits_90d,
            'discharge_disposition': discharge,
            'readmitted_30d': int(readmitted)
        })
    
    df = pd.DataFrame(data)
    
    # Encode categorical variable
    df['discharge_encoded'] = df['discharge_disposition'].map({
        'home': 0, 'snf': 1, 'rehab': 2
    })
    
    # Save dataset
    df.to_csv("data/readmission_dataset.csv", index=False)
    
    print(f"\n{'='*50}")
    print("✅ DATASET GENERATED!")
    print(f"{'='*50}")
    print(f"\n📊 Dataset Statistics:")
    print(f"   Total records: {len(df)}")
    print(f"   Readmission rate: {df['readmitted_30d'].mean():.2%}")
    print(f"   Age range: {df['age'].min():.1f} - {df['age'].max():.1f}")
    print(f"   Mean age: {df['age'].mean():.1f}")
    print(f"   Mean LOS: {df['length_of_stay'].mean():.1f} days")
    print(f"\n📋 Comorbidities:")
    print(f"   Heart failure: {df['has_heart_failure'].sum()} ({df['has_heart_failure'].mean():.1%})")
    print(f"   Diabetes: {df['has_diabetes'].sum()} ({df['has_diabetes'].mean():.1%})")
    print(f"   COPD: {df['has_copd'].sum()} ({df['has_copd'].mean():.1%})")
    print(f"\n🏥 Discharge Disposition:")
    print(f"   {df['discharge_disposition'].value_counts().to_dict()}")
    print(f"\n📁 Saved to: data/readmission_dataset.csv")
    
    return df


if __name__ == "__main__":
    generate_readmission_dataset()
