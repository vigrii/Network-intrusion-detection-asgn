import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from xgboost import XGBClassifier
from imblearn.over_sampling import SMOTE

# ==============================================================
# 1. LOAD DATA
# ==============================================================

train_url = "https://raw.githubusercontent.com/defcom17/NSL_KDD/master/KDDTrain%2B.txt"
test_url = "https://raw.githubusercontent.com/defcom17/NSL_KDD/master/KDDTest%2B.txt"

columns = [
    'duration', 'protocol_type', 'service', 'flag', 'src_bytes', 'dst_bytes',
    'land', 'wrong_fragment', 'urgent', 'hot', 'num_failed_logins', 'logged_in',
    'num_compromised', 'root_shell', 'su_attempted', 'num_root', 'num_file_creations',
    'num_shells', 'num_access_files', 'num_outbound_cmds', 'is_host_login',
    'is_guest_login', 'count', 'srv_count', 'serror_rate', 'srv_serror_rate',
    'rerror_rate', 'srv_rerror_rate', 'same_srv_rate', 'diff_srv_rate',
    'srv_diff_host_rate', 'dst_host_count', 'dst_host_srv_count',
    'dst_host_same_srv_rate', 'dst_host_diff_srv_rate',
    'dst_host_same_src_port_rate', 'dst_host_srv_diff_host_rate',
    'dst_host_serror_rate', 'dst_host_srv_serror_rate', 'dst_host_rerror_rate',
    'dst_host_srv_rerror_rate', 'class', 'level'
]

print("Loading data...")
df_train = pd.read_csv(train_url, names=columns)
df_test = pd.read_csv(test_url, names=columns)

# Drop difficulty level column (not a feature)
df_train.drop(columns=['level'], inplace=True)
df_test.drop(columns=['level'], inplace=True)

print(f"Training set: {df_train.shape[0]} records, {df_train.shape[1]} columns")
print(f"Test set:     {df_test.shape[0]} records, {df_test.shape[1]} columns")

# ==============================================================
# 2. ENCODE CATEGORICAL FEATURES
# ==============================================================

# Merge temporarily to ensure consistent encoding across train and test
df_full = pd.concat([df_train, df_test])

# Encode categorical columns as integers
cat_cols = ['protocol_type', 'service', 'flag']
label_encoders = {}

for col in cat_cols:
    le = LabelEncoder()
    df_full[col] = le.fit_transform(df_full[col])
    label_encoders[col] = le

# ==============================================================
# 3. MAP ATTACKS TO 5 CATEGORIES
# ==============================================================

category_map = {
    'normal': 'Normal',
    # DoS
    'neptune': 'DoS', 'back': 'DoS', 'land': 'DoS', 'pod': 'DoS',
    'smurf': 'DoS', 'teardrop': 'DoS', 'mailbomb': 'DoS', 'apache2': 'DoS',
    'processtable': 'DoS', 'udpstorm': 'DoS', 'worm': 'DoS',
    # Probe
    'satan': 'Probe', 'ipsweep': 'Probe', 'nmap': 'Probe', 'portsweep': 'Probe',
    'mscan': 'Probe', 'saint': 'Probe',
    # R2L
    'warezclient': 'R2L', 'guess_passwd': 'R2L', 'ftp_write': 'R2L',
    'imap': 'R2L', 'phf': 'R2L', 'multihop': 'R2L', 'warezmaster': 'R2L',
    'spy': 'R2L', 'xlock': 'R2L', 'xsnoop': 'R2L', 'snmpguess': 'R2L',
    'snmpgetattack': 'R2L', 'httptunnel': 'R2L', 'sendmail': 'R2L', 'named': 'R2L',
    # U2R
    'buffer_overflow': 'U2R', 'loadmodule': 'U2R', 'rootkit': 'U2R',
    'perl': 'U2R', 'sqlattack': 'U2R', 'xterm': 'U2R', 'ps': 'U2R'
}

df_full['category'] = df_full['class'].map(category_map).fillna('Other')

# ==============================================================
# 4. PREPARE FEATURES AND LABELS
# ==============================================================

# Drop constant column and original class labels
df_full.drop(columns=['num_outbound_cmds', 'class'], inplace=True)

# Split back into train and test
train_len = len(df_train)
df_train_processed = df_full.iloc[:train_len].copy()
df_test_processed = df_full.iloc[train_len:].copy()

X_train = df_train_processed.drop(columns=['category'])
y_train = df_train_processed['category']

X_test = df_test_processed.drop(columns=['category'])
y_test = df_test_processed['category']

print(f"\nFeatures: {X_train.shape[1]}")
print(f"\nTraining set class distribution:")
print(y_train.value_counts())
print(f"\nTest set class distribution:")
print(y_test.value_counts())

# ==============================================================
# YOUR WORK STARTS HERE
# ==============================================================


# 5. encoding labels
le = LabelEncoder()
y_train_enc = le.fit_transform(y_train)


# 6. building the model with specific parameters
def make_model():
    return XGBClassifier(
        n_estimators=150,
        max_depth=4,
        learning_rate=0.1,
        objective="multi:softmax",
        num_class=len(le.classes_),
        random_state=339
    )


# 7. cross validation
skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=339)
cv_scores = []

for train_idx, val_idx in skf.split(X_train, y_train_enc):
    X_tr, X_val = X_train.iloc[train_idx], X_train.iloc[val_idx]
    y_tr, y_val = y_train_enc[train_idx], y_train_enc[val_idx]

    smote = SMOTE(random_state=339)

    X_tr_resampled, y_tr_resampled = smote.fit_resample(X_tr, y_tr)

    model = make_model()
    model.fit(X_tr_resampled, y_tr_resampled)

    y_val_pred = model.predict(X_val)
    cv_scores.append(f1_score(y_val, y_val_pred, average="macro"))

print(f"Cross validation macro F1: {np.mean(cv_scores):.4f} ± {np.std(cv_scores):.4f}")


# 8. applying smote to last dataset and training model
smote = SMOTE(random_state=339)

X_train_smote, y_train_smote = smote.fit_resample( X_train, y_train_enc)

final_model = make_model()
final_model.fit(X_train_smote, y_train_smote)


# 9. predict on the test set
y_pred_enc = final_model.predict(X_test)
y_pred = le.inverse_transform(y_pred_enc)


# 10. evaluate results
print("\nClassification Report:")
print(classification_report(y_test, y_pred, digits=4))

print(f"Macro F1 score: {f1_score(y_test, y_pred, average='macro'):.4f}")


# 11. confusion matrix
labels = list(le.classes_)
cm = confusion_matrix(y_test, y_pred, labels=labels)

plt.figure(figsize=(8, 6))
sns.heatmap(
    cm,
    annot=True,
    fmt="d",
    cmap="Blues",
    xticklabels=labels,
    yticklabels=labels
)
plt.xlabel("Predicted")
plt.ylabel("Actual")
plt.title("Confusion Matrix")
plt.tight_layout()
plt.savefig("confusion_matrix.png", dpi=150)
plt.show()
