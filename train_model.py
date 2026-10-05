import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import xgboost as xgb
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
import warnings
warnings.filterwarnings('ignore')

"""
Complete Training Script for YOUR Dataset Format
Simply pass your CSV file path and it handles everything!
"""

class InstagramFakeProfileTrainer:
    """
    Complete training pipeline for your Instagram fake profile dataset
    """
    
    def __init__(self):
        self.scaler = StandardScaler()
        self.model = None
        self.feature_names = None
    
    def load_data(self, csv_filepath):
        """
        Load your CSV dataset
        
        Args:
            csv_filepath: Path to your CSV file (e.g., 'Dataset/dataset.csv')
        """
        print("="*70)
        print("STEP 1: LOADING DATASET")
        print("="*70)
        
        # Column names matching YOUR dataset structure
        column_names = [
            'profile_pic',           # 1 or 0
            'nums_length_username',  # ratio (e.g., 0.27)
            'fullname_words',        # count (e.g., 0, 2, 4)
            'nums_length_fullname',  # ratio
            'name_equals_username',  # 1 or 0
            'description_length',    # count
            'external_url',          # 1 or 0
            'private',               # 1 or 0
            'posts',                 # 1 or  0
            'followers',             # count
            'follows',               # count
            'fake'                   # TARGET: 1=fake, 0=real
        ]
        
        # Read CSV file - try with header first
        try:
            # Try reading with header
            df_temp = pd.read_csv(csv_filepath)
            
            # Check if first column looks like a header
            first_col_name = str(df_temp.columns[0]).lower()
            
            if 'profile' in first_col_name or 'pic' in first_col_name or len(df_temp.columns) == 12:
                # Has headers, use them and rename
                df = pd.read_csv(csv_filepath, header=0)
                df.columns = column_names
                print("  (File has headers - renamed to standard names)")
            else:
                # No headers
                df = pd.read_csv(csv_filepath, names=column_names, header=None)
                print("  (File has no headers - assigned column names)")
        except:
            # Fallback: read without headers
            df = pd.read_csv(csv_filepath, names=column_names, header=None)
        
        # Convert all columns to numeric, handling any non-numeric values,if camnot be converted to number it converts to NaN
        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Drop rows with NaN (likely the header row if it wasn't skipped)
        rows_before = len(df)
        df = df.dropna()
        if rows_before > len(df):
            print(f"  (Removed {rows_before - len(df)} non-numeric rows)")
        
        # Ensure 'fake' column only has 0 or 1
        df = df[df['fake'].isin([0, 1])]
        
        print(f"✓ Dataset loaded successfully!")
        print(f"  File: {csv_filepath}")
        print(f"  Total samples: {len(df)}")
        print(f"  Total features: {len(df.columns) - 1}")
        
        # Show first few rows
        print("\nFirst 3 rows of your data:")
        print(df.head(3).to_string())
        
        # Class distribution
        print(f"\nClass Distribution:")
        fake_count = (df['fake'] == 1).sum()
        real_count = (df['fake'] == 0).sum()
        print(f"  Real accounts (0): {real_count} ({real_count/len(df)*100:.1f}%)")
        print(f"  Fake accounts (1): {fake_count} ({fake_count/len(df)*100:.1f}%)")
        
        return df
    
    #=============================================================================================
    
    def engineer_features(self, df):
        """
        Create additional features from existing columns
        """
        print("\n" + "="*70)
        print("STEP 2: FEATURE ENGINEERING")
        print("="*70)
        
        df_enhanced = df.copy()
        
        # 1. Follower-Following Ratio
        df_enhanced['follower_following_ratio'] = df_enhanced.apply(
            lambda row: row['follows'] / row['followers'] if row['followers'] > 0 else 100,
            axis=1
        )
        print("✓ Added: follower_following_ratio")
        
        # 2. Suspicious ratio flag
        df_enhanced['suspicious_ratio'] = (
            (df_enhanced['follower_following_ratio'] > 10) | 
            (df_enhanced['follower_following_ratio'] < 0.01)
        ).astype(int)
        print("✓ Added: suspicious_ratio")
        
        # 3. Has followers/following indicators
        df_enhanced['has_followers'] = (df_enhanced['followers'] > 0).astype(int)
        df_enhanced['has_following'] = (df_enhanced['follows'] > 0).astype(int)
        print("✓ Added: has_followers, has_following")
        
        # 4. Has posts indicator
        df_enhanced['has_posts'] = (df_enhanced['posts'] > 0).astype(int)
        print("✓ Added: has_posts")
        
        # 5. Engagement score
        df_enhanced['engagement_score'] = df_enhanced.apply(
            lambda row: row['posts'] / row['followers'] if row['followers'] > 0 else 0,
            axis=1
        )
        print("✓ Added: engagement_score")
        
        # 6. Profile completeness
        df_enhanced['profile_completeness'] = (
            df_enhanced['profile_pic'] +
            (df_enhanced['description_length'] > 0).astype(int) +
            df_enhanced['external_url'] +
            (df_enhanced['fullname_words'] > 0).astype(int)
        ) / 4.0
        print("✓ Added: profile_completeness")
        
        # 7. Username quality
        df_enhanced['username_quality'] = 1 - df_enhanced['nums_length_username']
        print("✓ Added: username_quality")
        
        # 8. Has description
        df_enhanced['has_description'] = (df_enhanced['description_length'] > 0).astype(int)
        print("✓ Added: has_description")
        
        print(f"\n✓ Feature engineering complete!")
        print(f"  Original features: {df.shape[1] - 1}")
        print(f"  Engineered features: 8")
        print(f"  Total features: {df_enhanced.shape[1] - 1}")
        
        return df_enhanced
    
    #=============================================================================================
    
    def preprocess(self, df):
        """
        Clean and prepare data
        """
        print("\n" + "="*70)
        print("STEP 3: DATA PREPROCESSING")
        print("="*70)
        
        # Handle infinite values
        df = df.replace([np.inf, -np.inf], 100)
        print("✓ Handled infinite values")
        
        # Handle missing values
        if df.isnull().sum().sum() > 0:
            print(f"  Found {df.isnull().sum().sum()} missing values")
            df = df.fillna(0)
            print("✓ Filled missing values with 0")
        else:
            print("✓ No missing values found")
        
        # Cap extreme outliers
        if 'follower_following_ratio' in df.columns:
            df['follower_following_ratio'] = df['follower_following_ratio'].clip(upper=100) #sets max value to 100
            print("✓ Capped extreme outliers")
        
        print("✓ Preprocessing complete")
        
        return df
    #=============================================================================================
    
    def split_data(self, df, test_size=0.2, random_state=42): #self is used to get the current object
        """
        Split data into train and test sets
        """
        print("\n" + "="*70)
        print("STEP 4: TRAIN-TEST SPLIT")
        print("="*70)
        
        # Separate features and target
        X = df.drop('fake', axis=1) #drorps the col name fake and operates on horizontal axis (axis=1)
        y = df['fake']
        
        self.feature_names = X.columns.tolist()
        
        # Split with stratification
        #stratification splits the test data and train data equally such that accuracy is maintained
        X_train, X_test, y_train, y_test = train_test_split(
            X, y,
            test_size=test_size,
            random_state=random_state,
            stratify=y
        )
        
        print(f"✓ Data split complete")
        print(f"  Training samples: {len(X_train)} ({(1-test_size)*100:.0f}%)")
        print(f"  Testing samples: {len(X_test)} ({test_size*100:.0f}%)")
        print(f"  Features: {X_train.shape[1]}") #takes the output as a 1-D array
        
        return X_train, X_test, y_train, y_test
    
    def scale_features(self, X_train, X_test):
        """
        Normalize features
        """
        print("\n" + "="*70)
        print("STEP 5: FEATURE SCALING")
        print("="*70)
        
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        print("✓ Features scaled using StandardScaler")
        
        return X_train_scaled, X_test_scaled
    
    def train_model(self, X_train, X_test, y_train, y_test):
        """
        Train XGBoost model
        """
        print("\n" + "="*70)
        print("STEP 6: TRAINING XGBOOST MODEL")
        print("="*70)
        
        # Initialize XGBoost
        self.model = xgb.XGBClassifier(
            n_estimators=100, #num of decision trees
            max_depth=6,
            learning_rate=0.1, #slow and steady ->stable
            random_state=42,
            eval_metric='logloss' #finds error
        )
        
        print("Training model...")
        self.model.fit(X_train, y_train)
        print("✓ Training complete")
        
        # Predictions
        y_pred_train = self.model.predict(X_train)
        y_pred_test = self.model.predict(X_test)
        
        # Accuracy
        train_acc = accuracy_score(y_train, y_pred_train)
        test_acc = accuracy_score(y_test, y_pred_test)
        
        print(f"\n📊 MODEL PERFORMANCE:")
        print(f"  Training Accuracy: {train_acc*100:.2f}%")
        print(f"  Testing Accuracy:  {test_acc*100:.2f}%")
        
        # Classification report
        print(f"\n📋 CLASSIFICATION REPORT (Test Set):")
        print(classification_report(y_test, y_pred_test, target_names=['Real', 'Fake']))
        
        # Confusion Matrix
        cm = confusion_matrix(y_test, y_pred_test)
        print(f"🔢 CONFUSION MATRIX:")
        print(f"              Predicted")
        print(f"            Real    Fake")
        print(f"Actual Real  {cm[0][0]:<6}  {cm[0][1]:<6}")
        print(f"       Fake  {cm[1][0]:<6}  {cm[1][1]:<6}")
        
        return test_acc
    
    def show_feature_importance(self):
        """
        Display feature importance
        """
        print("\n" + "="*70)
        print("FEATURE IMPORTANCE")
        print("="*70)
        
        importance = self.model.feature_importances_
        feature_importance_df = pd.DataFrame({
            'Feature': self.feature_names,
            'Importance': importance
        }).sort_values('Importance', ascending=False)
        
        print("\nTop 10 Most Important Features:")
        for idx, row in feature_importance_df.head(10).iterrows():
            bar = '█' * int(row['Importance'] * 50)
            print(f"  {row['Feature']:<30} {bar} {row['Importance']:.4f}")
        
        return feature_importance_df
    
    def save_model(self, model_path='fake_profile_model.pkl', scaler_path='scaler.pkl'):
        """
        Save trained model and scaler
        """
        import pickle
        
        with open(model_path, 'wb') as f:
            pickle.dump(self.model, f)
        
        with open(scaler_path, 'wb') as f:
            pickle.dump(self.scaler, f)
        
        print(f"\n💾 Model saved:")
        print(f"  - {model_path}")
        print(f"  - {scaler_path}")


# ============================================================================
# MAIN EXECUTION - JUST PASS YOUR CSV FILE PATH HERE!
# ============================================================================

if __name__ == "__main__":
    
    print("""
╔══════════════════════════════════════════════════════════════════╗
║       INSTAGRAM FAKE PROFILE DETECTION - TRAINING PIPELINE       ║
╚══════════════════════════════════════════════════════════════════╝
    """)
    
    # ========================================
    # CHANGE THIS TO YOUR CSV FILE PATH
    # ========================================
    CSV_FILE_PATH = 'train_dataset.csv'  # ← CHANGE THIS!
    # ========================================
    
    try:
        # Initialize trainer
        trainer = InstagramFakeProfileTrainer()
        
        # Step 1: Load data
        df = trainer.load_data(CSV_FILE_PATH)
        
        # Step 2: Engineer features
        df_enhanced = trainer.engineer_features(df)
        
        # Step 3: Preprocess
        df_clean = trainer.preprocess(df_enhanced)
        
        # Step 4: Split data
        X_train, X_test, y_train, y_test = trainer.split_data(df_clean)
        
        # Step 5: Scale features
        X_train_scaled, X_test_scaled = trainer.scale_features(X_train, X_test)
        
        # Step 6: Train model
        accuracy = trainer.train_model(X_train_scaled, X_test_scaled, y_train, y_test)
        
        # Show feature importance
        feature_importance = trainer.show_feature_importance()
        
        # Save model
        trainer.save_model()
        
        # Final summary
        print("\n" + "="*70)
        print("✅ TRAINING COMPLETE!")
        print("="*70)
        print(f"Final Test Accuracy: {accuracy*100:.2f}%")
        print(f"Model is ready for predictions!")
        print("="*70)
        
    except FileNotFoundError:
        print(f"\n❌ ERROR: Could not find file '{CSV_FILE_PATH}'")
        print("\n📝 To fix this:")
        print("  1. Make sure your CSV file exists")
        print("  2. Check the file path is correct")
        print("  3. Update CSV_FILE_PATH variable in the code")
        #print(f"\nCurrent working directory: {pd.os.getcwd()}")
        print(f"Looking for: {CSV_FILE_PATH}")
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()