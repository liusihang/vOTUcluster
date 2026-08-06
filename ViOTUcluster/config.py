#!/usr/bin/env python3
"""
Central configuration for ViOTUcluster.

This module provides default values and constants used throughout
the ViOTUcluster pipeline components.
"""

import os
import multiprocessing

# =============================================================================
# Version Information
# =============================================================================
VERSION = "0.6.0"

# =============================================================================
# Default Processing Parameters
# =============================================================================

# Minimum sequence length for filtering (in base pairs)
DEFAULT_MIN_LENGTH = 2500

# Thread configuration
DEFAULT_THREADS = 0  # 0 = auto-detect (use all available)

# Concurrency controls
DEFAULT_MAX_PREDICTION_TASKS = 30  # Max concurrent prediction jobs
DEFAULT_TPM_TASKS = 15             # Max concurrent BAM/TPM processing samples
DEFAULT_ASSEMBLE_JOBS = 10         # Max concurrent assembly samples
DEFAULT_MODULE_TIMEOUT_SECONDS = 72 * 3600  # Kill a stage if it runs longer than 72h

# =============================================================================
# Database Subdirectory Names
# =============================================================================
DB_VIRSORTER = "db"               # VirSorter2 database
DB_VIRALVERIFY = "ViralVerify"    # ViralVerify database
DB_CHECKV = "checkv-db-v1.5"      # CheckV database
DB_GENOMAD = "genomad_db"         # geNomad database
DB_IPHOP = "Aug_2023_pub_rw"      # iPhop database
DB_DRAM = "DRAM"                  # DRAM database

# =============================================================================
# Clustering Parameters
# =============================================================================

# dRep clustering parameters
DREP_PRIMARY_ANI = 0.8       # Primary clustering ANI threshold
DREP_SECONDARY_ANI = 0.95    # Secondary clustering ANI threshold
DREP_COVERAGE = 0.85         # Minimum coverage for clustering

# ANI clustering parameters (for unbinned contigs)
ANI_THRESHOLD = 95           # Minimum ANI for clustering (%)
ANI_TCOV = 85                # Minimum target coverage (%)
ANI_QCOV = 0                 # Minimum query coverage (%)

# =============================================================================
# Viral Prediction Thresholds
# =============================================================================

# VirSorter2 thresholds
class VirSorter2Config:
    """VirSorter2 prediction thresholds."""
    MIN_SCORE = 0.5
    MIN_LENGTH = 300
    
    # Non-concentration mode (stricter thresholds)
    NON_CON_SCORE = 0.95
    NON_CON_HALLMARK = 1
    NON_CON_SCORE_NO_HALLMARK = 0.99
    NON_CON_SSDNA_SCORE = 0.995
    
    # Concentration mode (relaxed thresholds)
    CON_SCORE = 0.90
    CON_HALLMARK = 1

# Genomad thresholds
class GenomadConfig:
    """Genomad prediction thresholds."""
    MAX_FDR = 0.05
    MAX_USCG = 2
    
    # Concentration mode
    CON_MIN_SCORE = 0.7
    CON_MIN_GENES = 0
    CON_VIRUS_ENRICHMENT = 1.5
    CON_PLASMID_ENRICHMENT = 0
    CON_PLASMID_HALLMARKS = 1
    CON_PLASMID_HALLMARKS_SHORT = 0
    
    # Non-concentration mode
    NON_CON_MIN_SCORE = 0.8
    NON_CON_MIN_GENES = 1
    NON_CON_VIRUS_ENRICHMENT = 0
    NON_CON_PLASMID_ENRICHMENT = 1.5
    NON_CON_PLASMID_HALLMARKS = 1
    NON_CON_PLASMID_HALLMARKS_SHORT = 1

# =============================================================================
# File Extensions
# =============================================================================

FASTA_EXTENSIONS = ('.fasta', '.fa', '.fna')
FASTQ_EXTENSIONS = ('.fq', '.fastq', '.fq.gz', '.fastq.gz')

# =============================================================================
# Utility Functions
# =============================================================================

def get_threads(requested: int = 0) -> int:
    """
    Get the number of threads to use.
    
    Args:
        requested: Requested number of threads (0 = auto-detect)
        
    Returns:
        Number of threads to use
    """
    if requested <= 0:
        return multiprocessing.cpu_count()
    return min(requested, multiprocessing.cpu_count())


def get_database_path(base_path: str, db_name: str) -> str:
    """
    Get the full path to a database subdirectory.
    
    Args:
        base_path: Base database directory
        db_name: Database subdirectory name constant
        
    Returns:
        Full path to the database
    """
    return os.path.join(base_path, db_name)


def get_virsorter_groups(sample_type: str = "Mix") -> str:
    """
    Get VirSorter2 include-groups based on sample type.
    
    Args:
        sample_type: One of 'DNA', 'RNA', or 'Mix'
        
    Returns:
        Comma-separated list of groups
    """
    groups = {
        "DNA": "dsDNAphage, NCLDV, ssDNA, lavidaviridae",
        "RNA": "RNA, lavidaviridae",
        "Mix": "dsDNAphage, NCLDV, RNA, ssDNA, lavidaviridae",
    }
    return groups.get(sample_type, groups["Mix"])
