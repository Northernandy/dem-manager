"""
Brisbane Flood Forecasting Model

This module provides both rule-based and machine learning models for flood forecasting.
It uses time-lagged variables from rainfall, river levels, tide data, and dam releases.
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split

class FloodForecaster:
    """Base class for flood forecasting models."""
    
    def __init__(self):
        self.model = None
        self.trained = False
    
    def preprocess_data(self, data):
        """
        Preprocess input data for model training or prediction.
        
        Args:
            data (pd.DataFrame): Raw input data
            
        Returns:
            pd.DataFrame: Processed data ready for modeling
        """
        # This would be expanded with actual preprocessing steps
        return data
    
    def create_lagged_features(self, data, lag_variables, lag_periods=[1, 3, 6, 12, 24]):
        """
        Create time-lagged features for the specified variables.
        
        Args:
            data (pd.DataFrame): Time series data
            lag_variables (list): List of column names to create lags for
            lag_periods (list): List of lag periods in hours
            
        Returns:
            pd.DataFrame: DataFrame with additional lagged features
        """
        df = data.copy()
        
        for var in lag_variables:
            for lag in lag_periods:
                df[f"{var}_lag_{lag}h"] = df[var].shift(lag)
                
        # Drop rows with NaN values from the lag creation
        df = df.dropna()
        return df
    
    def predict(self, features):
        """
        Make predictions using the trained model.
        
        Args:
            features (pd.DataFrame): Input features
            
        Returns:
            np.array: Predicted flood levels
        """
        if not self.trained:
            raise ValueError("Model has not been trained yet")
        
        # Implement in subclasses
        pass


class RuleBasedForecaster(FloodForecaster):
    """Rule-based flood forecasting model."""
    
    def __init__(self, rules=None):
        super().__init__()
        self.rules = rules or {}
        self.trained = True  # Rule-based models don't need training
    
    def add_rule(self, condition_func, output_func):
        """
        Add a rule to the model.
        
        Args:
            condition_func (callable): Function that evaluates if a rule applies
            output_func (callable): Function that calculates the output if rule applies
        """
        rule_id = len(self.rules) + 1
        self.rules[rule_id] = {
            'condition': condition_func,
            'output': output_func
        }
    
    def predict(self, features):
        """
        Make predictions using the rule-based model.
        
        Args:
            features (pd.DataFrame): Input features
            
        Returns:
            np.array: Predicted flood levels
        """
        results = np.zeros(len(features))
        
        # Apply each rule in sequence
        for rule_id, rule in self.rules.items():
            # Find rows where the rule condition applies
            mask = rule['condition'](features)
            # Apply the rule output function to those rows
            results[mask] = rule['output'](features[mask])
            
        return results
    
    def create_default_rules(self):
        """Create a set of default rules based on domain knowledge."""
        # Example rule: If rainfall > 100mm in 24h and dam level > 90%, predict high flood
        self.add_rule(
            condition_func=lambda df: (df['rainfall_24h'] > 100) & (df['dam_level'] > 90),
            output_func=lambda df: 3.0  # High flood level (3 meters)
        )
        
        # Example rule: If rainfall > 50mm in 24h and tide is high, predict moderate flood
        self.add_rule(
            condition_func=lambda df: (df['rainfall_24h'] > 50) & (df['tide_height'] > 2.0),
            output_func=lambda df: 1.5  # Moderate flood level (1.5 meters)
        )
        
        # Default rule: Otherwise predict based on weighted factors
        self.add_rule(
            condition_func=lambda df: np.ones(len(df), dtype=bool),
            output_func=lambda df: 0.01 * df['rainfall_24h'] + 0.2 * df['river_height'] + 0.1 * df['tide_height']
        )


class MLForecaster(FloodForecaster):
    """Machine learning-based flood forecasting model using Random Forest."""
    
    def __init__(self, n_estimators=100, random_state=42):
        super().__init__()
        self.pipeline = Pipeline([
            ('scaler', StandardScaler()),
            ('model', RandomForestRegressor(n_estimators=n_estimators, random_state=random_state))
        ])
    
    def train(self, features, targets, test_size=0.2, random_state=42):
        """
        Train the ML model.
        
        Args:
            features (pd.DataFrame): Input features
            targets (pd.Series): Target values (flood levels)
            test_size (float): Proportion of data to use for testing
            random_state (int): Random seed for reproducibility
            
        Returns:
            dict: Training metrics
        """
        # Split data into training and testing sets
        X_train, X_test, y_train, y_test = train_test_split(
            features, targets, test_size=test_size, random_state=random_state
        )
        
        # Train the model
        self.pipeline.fit(X_train, y_train)
        
        # Evaluate the model
        train_score = self.pipeline.score(X_train, y_train)
        test_score = self.pipeline.score(X_test, y_test)
        
        self.trained = True
        
        return {
            'train_r2': train_score,
            'test_r2': test_score,
            'feature_importance': dict(zip(
                features.columns, 
                self.pipeline.named_steps['model'].feature_importances_
            ))
        }
    
    def predict(self, features):
        """
        Make predictions using the trained ML model.
        
        Args:
            features (pd.DataFrame): Input features
            
        Returns:
            np.array: Predicted flood levels
        """
        if not self.trained:
            raise ValueError("Model has not been trained yet")
        
        return self.pipeline.predict(features)


def create_combined_forecaster(ml_weight=0.7):
    """
    Create a combined forecaster that uses both rule-based and ML approaches.
    
    Args:
        ml_weight (float): Weight to give to the ML model (0-1)
        
    Returns:
        tuple: (RuleBasedForecaster, MLForecaster, combination_function)
    """
    rule_based = RuleBasedForecaster()
    rule_based.create_default_rules()
    
    ml_model = MLForecaster()
    
    def combined_predict(features, rule_model=rule_based, ml_model=ml_model, weight=ml_weight):
        """
        Combine predictions from both models.
        
        Args:
            features (pd.DataFrame): Input features
            rule_model (RuleBasedForecaster): Rule-based model
            ml_model (MLForecaster): ML model
            weight (float): Weight for ML model (1-weight for rule-based)
            
        Returns:
            np.array: Combined predictions
        """
        if not ml_model.trained:
            # If ML model isn't trained, use only rule-based
            return rule_model.predict(features)
        
        rule_preds = rule_model.predict(features)
        ml_preds = ml_model.predict(features)
        
        # Combine predictions with weighted average
        return (weight * ml_preds) + ((1 - weight) * rule_preds)
    
    return rule_based, ml_model, combined_predict
