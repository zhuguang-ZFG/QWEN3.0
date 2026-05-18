"""
Train sklearn classifier on extracted features from routing training data.
Outputs: trained model (joblib), feature names, label encoder.
"""
import json, sys, os
import pickle

# Add Desktop to path for feature extractor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from context_feature_extractor import ContextFeatureExtractor
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score, StratifiedKFold
from sklearn.preprocessing import LabelEncoder
import numpy as np


def main():
    # 1. Load training data
    data_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             'routing_training_data_v3.jsonl')
    with open(data_path, 'r', encoding='utf-8') as f:
        samples = [json.loads(line) for line in f if line.strip()]

    print(f"[1/5] Loaded {len(samples)} training samples")

    # 2. Extract features
    extractor = ContextFeatureExtractor()
    X_list, y_raw = [], []
    feature_names = None

    for sample in samples:
        vec, names = extractor.extract_vector(sample['text'])
        X_list.append(vec)
        y_raw.append(sample['label'])
        if feature_names is None:
            feature_names = names

    X = np.array(X_list)
    print(f"[2/5] Extracted features: X.shape={X.shape}, dims={len(feature_names)}")

    # 3. Encode labels
    le = LabelEncoder()
    y = le.fit_transform(y_raw)
    print(f"[3/5] Labels: {dict(zip(le.classes_, range(len(le.classes_))))}")
    print(f"      {len(le.classes_)} classes: {list(le.classes_)}")

    # 4. Cross-validate
    clf = RandomForestClassifier(
        n_estimators=50, random_state=42, class_weight='balanced',
        max_depth=8  # Prevent overfitting with small dataset
    )
    min_per_class = min(np.bincount(y))
    n_splits = min(3, min_per_class)
    print(f"[4/5] Cross-validation: min_per_class={min_per_class}, n_splits={n_splits}")
    if n_splits >= 2:
        skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
        cv_scores = cross_val_score(clf, X, y, cv=skf, scoring='accuracy')
        cv_mean = cv_scores.mean()
        cv_std = cv_scores.std()
        print(f"      CV accuracy: {cv_mean:.1%} (+/- {cv_std:.1%})")
    else:
        cv_mean = 1.0
        cv_std = 0.0
        print(f"      Skipping CV (need >=2 samples per class)")

    # 5. Train final model on all data
    clf.fit(X, y)
    train_acc = clf.score(X, y)
    print(f"[5/5] Final model trained. Training accuracy: {train_acc:.1%}")

    # 6. Save artifacts
    base = os.path.dirname(os.path.abspath(__file__))
    artifacts = {
        'model': clf,
        'label_encoder': le,
        'feature_names': feature_names,
        'cv_accuracy': cv_mean,
    }

    with open(os.path.join(base, 'router_ml_model.pkl'), 'wb') as f:
        pickle.dump(artifacts, f)
    print(f"\nSaved: router_ml_model.pkl")

    # Also save feature names as text
    with open(os.path.join(base, 'feature_names.txt'), 'w') as f:
        for name in feature_names:
            f.write(name + '\n')
    print(f"Saved: feature_names.txt ({len(feature_names)} features)")

    # Print per-class training counts
    print(f"\nTraining set distribution:")
    for label in le.classes_:
        count = sum(1 for l in y_raw if l == label)
        print(f"  {label:15s}: {count}")

    return clf, le, feature_names, cv_mean


if __name__ == "__main__":
    main()
