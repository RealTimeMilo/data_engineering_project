"""
Instacart Dataset Preprocessing Script

This script performs comprehensive preprocessing of the Instacart Market Basket
Analysis dataset including:
- Data loading with memory optimization
- Data quality assessment
- Feature engineering
- Aggregation for ML tasks
- Export of processed datasets

Author: [Your Name]
Date: [Current Date]
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple, Optional
import time
import warnings

from config import *
from utils import *

warnings.filterwarnings("ignore")


class InstacartPreprocessor:
    """
    Class for preprocessing the Instacart dataset.
    """
    
    def __init__(self, raw_dir: Path = RAW_DATA_DIR, processed_dir: Path = PROCESSED_DATA_DIR, 
                 debug_mode: bool = False, sample_size: Optional[int] = None):
        """
        Initialize preprocessor.
        
        Args:
            raw_dir: Directory containing raw CSV files
            processed_dir: Directory to save processed files
            debug_mode: If True, use smaller sample for faster testing
            sample_size: Number of rows to sample in debug mode
        """
        self.raw_dir = raw_dir
        self.processed_dir = processed_dir
        self.debug_mode = debug_mode
        self.sample_size = sample_size or 100000
        
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        
        # Data containers
        self.aisles = None
        self.departments = None
        self.products = None
        self.orders = None
        self.order_products_prior = None
        self.order_products_train = None
        
        # Enriched data
        self.products_enriched = None
        self.orders_enriched = None
        self.user_features = None
        self.product_features = None
        self.user_product_features = None
        
        # Quality reports
        self.quality_reports = []
    
    # =========================================================================
    # DATA LOADING
    # =========================================================================
    
    def load_all_data(self) -> None:
        """Load all raw CSV files."""
        logger.info("=" * 60)
        logger.info("LOADING RAW DATA")
        logger.info("=" * 60)
        
        self.aisles = load_data(
            self.raw_dir / RAW_FILES["aisles"],
            DTYPES["aisles"]
        )
        
        self.departments = load_data(
            self.raw_dir / RAW_FILES["departments"],
            DTYPES["departments"]
        )
        
        self.products = load_data(
            self.raw_dir / RAW_FILES["products"],
            DTYPES["products"]
        )
        
        self.orders = load_data(
            self.raw_dir / RAW_FILES["orders"],
            DTYPES["orders"]
        )
        
        self.order_products_prior = load_data(
            self.raw_dir / RAW_FILES["order_products_prior"],
            DTYPES["order_products_prior"]
        )
        
        self.order_products_train = load_data(
            self.raw_dir / RAW_FILES["order_products_train"],
            DTYPES["order_products_train"]
        )
        
        # Apply debug sampling if needed
        if self.debug_mode:
            self._apply_debug_sampling()
        
        garbage_collect()
    
    def _apply_debug_sampling(self) -> None:
        """Sample data for debug mode."""
        logger.warning(f"DEBUG MODE: Sampling {self.sample_size:,} rows from prior orders")
        
        # Sample orders from prior set
        sample_orders = self.order_products_prior[ORDER_ID].sample(
            n=self.sample_size, random_state=42
        ).unique()
        
        self.order_products_prior = self.order_products_prior[
            self.order_products_prior[ORDER_ID].isin(sample_orders)
        ]
        
        # Get corresponding orders
        sample_order_ids = self.order_products_prior[ORDER_ID].unique()
        self.orders = self.orders[self.orders[ORDER_ID].isin(sample_order_ids)]
    
    # =========================================================================
    # DATA QUALITY CHECKS
    # =========================================================================
    
    def run_quality_checks(self) -> pd.DataFrame:
        """Run data quality checks on all datasets."""
        logger.info("=" * 60)
        logger.info("DATA QUALITY CHECKS")
        logger.info("=" * 60)
        
        datasets = {
            "aisles": self.aisles,
            "departments": self.departments,
            "products": self.products,
            "orders": self.orders,
            "order_products_prior": self.order_products_prior,
            "order_products_train": self.order_products_train,
        }
        
        reports = []
        for name, df in datasets.items():
            report = data_quality_report(df, name)
            reports.append(report)
            self.quality_reports.append(report)
        
        # Check referential integrity
        self._check_referential_integrity()
        
        combined_report = pd.concat(reports, ignore_index=True)
        save_data(combined_report, self.processed_dir / "data_quality_report.csv", format="csv")
        
        return combined_report
    
    def _check_referential_integrity(self) -> None:
        """Check referential integrity between tables."""
        logger.info("\nReferential Integrity Checks:")
        
        # Products -> Aisles
        orphan_products = ~self.products[AISLE_ID].isin(self.aisles[AISLE_ID])
        logger.info(f"  Products without valid aisle: {orphan_products.sum()}")
        
        # Products -> Departments
        orphan_products = ~self.products[DEPARTMENT_ID].isin(self.departments[DEPARTMENT_ID])
        logger.info(f"  Products without valid department: {orphan_products.sum()}")
        
        # Order products -> Products
        orphan_prior = ~self.order_products_prior[PRODUCT_ID].isin(self.products[PRODUCT_ID])
        logger.info(f"  Prior order products without valid product: {orphan_prior.sum()}")
        
        orphan_train = ~self.order_products_train[PRODUCT_ID].isin(self.products[PRODUCT_ID])
        logger.info(f"  Train order products without valid product: {orphan_train.sum()}")
        
        # Order products -> Orders
        orphan_prior = ~self.order_products_prior[ORDER_ID].isin(self.orders[ORDER_ID])
        logger.info(f"  Prior order products without valid order: {orphan_prior.sum()}")
        
        orphan_train = ~self.order_products_train[ORDER_ID].isin(self.orders[ORDER_ID])
        logger.info(f"  Train order products without valid order: {orphan_train.sum()}")
    
    # =========================================================================
    # DATA CLEANING
    # =========================================================================
    
    def clean_data(self) -> None:
        """Clean and standardize all datasets."""
        logger.info("=" * 60)
        logger.info("DATA CLEANING")
        logger.info("=" * 60)
        
        # Clean products
        self._clean_products()
        
        # Clean orders
        self._clean_orders()
        
        # Clean order products
        self._clean_order_products()
        
        garbage_collect()
    
    def _clean_products(self) -> None:
        """Clean products dataframe."""
        logger.info("Cleaning products...")
        
        # Standardize product names
        self.products[PRODUCT_NAME] = (
            self.products[PRODUCT_NAME]
            .str.strip()
            .str.lower()
            .str.replace(r"\s+", " ", regex=True)
        )
        
        # Remove duplicates if any
        n_before = len(self.products)
        self.products = self.products.drop_duplicates(subset=[PRODUCT_ID], keep="first")
        n_after = len(self.products)
        
        if n_before != n_after:
            logger.warning(f"  Removed {n_before - n_after} duplicate products")
    
    def _clean_orders(self) -> None:
        """Clean orders dataframe."""
        logger.info("Cleaning orders...")
        
        # Handle missing days_since_prior_order (first orders)
        n_missing = self.orders[DAYS_SINCE_PRIOR_ORDER].isnull().sum()
        logger.info(f"  Missing days_since_prior_order: {n_missing:,} (expected for first orders)")
        
        # Fill with 0 for first orders (will be handled in feature engineering)
        # Create a flag for first orders
        self.orders["is_first_order"] = (
            self.orders[DAYS_SINCE_PRIOR_ORDER].isnull().astype("int8")
        )
        self.orders[DAYS_SINCE_PRIOR_ORDER] = self.orders[DAYS_SINCE_PRIOR_ORDER].fillna(0)
        
        # Ensure correct data types
        self.orders[ORDER_DOW] = self.orders[ORDER_DOW].astype("int8")
        self.orders[ORDER_HOUR_OF_DAY] = self.orders[ORDER_HOUR_OF_DAY].astype("int8")
    
    def _clean_order_products(self) -> None:
        """Clean order products dataframes."""
        logger.info("Cleaning order products...")
        
        for name, df in [("prior", self.order_products_prior), ("train", self.order_products_train)]:
            # Check for invalid reorder values
            invalid = ~df[REORDERED].isin([0, 1])
            if invalid.any():
                logger.warning(f"  {name}: Found {invalid.sum()} invalid reorder values")
                df = df[~invalid]
            
            # Ensure add_to_cart_order starts from 1
            min_cart_order = df[ADD_TO_CART_ORDER].min()
            if min_cart_order != 1:
                logger.info(f"  {name}: Adjusting add_to_cart_order (min was {min_cart_order})")
    
    # =========================================================================
    # FEATURE ENGINEERING - PRODUCTS
    # =========================================================================
    
    def create_product_features(self) -> pd.DataFrame:
        """
        Create product-level features from order data.
        
        Returns:
            DataFrame with product features
        """
        logger.info("=" * 60)
        logger.info("CREATING PRODUCT FEATURES")
        logger.info("=" * 60)
        
        # Combine prior and train for complete statistics
        all_order_products = pd.concat(
            [self.order_products_prior, self.order_products_train],
            ignore_index=True
        )
        
        # Basic product statistics
        logger.info("Calculating product order statistics...")
        product_stats = all_order_products.groupby(PRODUCT_ID).agg(
            n_orders=(ORDER_ID, "nunique"),
            n_times_ordered=(PRODUCT_ID, "count"),
            reorder_rate=(REORDERED, "mean"),
            avg_add_to_cart_order=(ADD_TO_CART_ORDER, "mean"),
            std_add_to_cart_order=(ADD_TO_CART_ORDER, "std"),
        ).reset_index()
        
        # Calculate products per order ratio
        product_stats["avg_products_per_order"] = (
            product_stats["n_times_ordered"] / product_stats["n_orders"]
        )
        
        # Fill NaN for std
        product_stats["std_add_to_cart_order"] = product_stats["std_add_to_cart_order"].fillna(0)
        
        logger.info("Calculating product popularity percentiles...")
        product_stats["order_percentile"] = product_stats["n_orders"].rank(pct=True)
        product_stats["popularity_tier"] = pd.qcut(
            product_stats["n_orders"],
            q=5,
            labels=["very_low", "low", "medium", "high", "very_high"],
            duplicates="drop"
        )
        
        # Enrich products with aisle and department info
        logger.info("Enriching product data...")
        self.products_enriched = self.products.merge(self.aisles, on=AISLE_ID, how="left")
        self.products_enriched = self.products_enriched.merge(
            self.departments, on=DEPARTMENT_ID, how="left"
        )
        
        # Add product statistics
        self.products_enriched = self.products_enriched.merge(
            product_stats, on=PRODUCT_ID, how="left"
        )
        
        # Fill NaN for products not in order data
        numeric_cols = ["n_orders", "n_times_ordered", "reorder_rate", 
                       "avg_add_to_cart_order", "std_add_to_cart_order",
                       "avg_products_per_order", "order_percentile"]
        self.products_enriched[numeric_cols] = self.products_enriched[numeric_cols].fillna(0)
        self.products_enriched["popularity_tier"] = self.products_enriched["popularity_tier"].cat.add_categories("unknown").fillna("unknown")
        
        # Department-level features
        logger.info("Creating department-level features...")
        dept_stats = self.products_enriched.groupby(DEPARTMENT).agg(
            n_products=(PRODUCT_ID, "count"),
            avg_reorder_rate=("reorder_rate", "mean"),
        ).reset_index()
        dept_stats.columns = [DEPARTMENT, "dept_n_products", "dept_avg_reorder_rate"]
        
        self.products_enriched = self.products_enriched.merge(dept_stats, on=DEPARTMENT, how="left")
        
        # Aisle-level features
        logger.info("Creating aisle-level features...")
        aisle_stats = self.products_enriched.groupby(AISLE).agg(
            n_products=(PRODUCT_ID, "count"),
            avg_reorder_rate=("reorder_rate", "mean"),
        ).reset_index()
        aisle_stats.columns = [AISLE, "aisle_n_products", "aisle_avg_reorder_rate"]
        
        self.products_enriched = self.products_enriched.merge(aisle_stats, on=AISLE, how="left")
        
        self.product_features = product_stats
        self.products_enriched = optimize_memory(self.products_enriched)
        
        logger.info(f"Products enriched shape: {self.products_enriched.shape}")
        
        del all_order_products
        garbage_collect()
        
        return self.products_enriched
    
    # =========================================================================
    # FEATURE ENGINEERING - ORDERS
    # =========================================================================
    
    def create_order_features(self) -> pd.DataFrame:
        """
        Create order-level temporal features.
        
        Returns:
            DataFrame with enriched order data
        """
        logger.info("=" * 60)
        logger.info("CREATING ORDER FEATURES")
        logger.info("=" * 60)
        
        self.orders_enriched = self.orders.copy()
        
        # Time of day feature
        logger.info("Creating time-based features...")
        self.orders_enriched["time_of_day"] = pd.cut(
            self.orders_enriched