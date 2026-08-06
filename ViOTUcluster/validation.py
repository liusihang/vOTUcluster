#!/usr/bin/env python3
"""
Unified input validation utilities for ViOTUcluster scripts.

This module provides common validation functions to ensure consistent
input handling across all ViOTUcluster components.
"""

import os
import sys
from typing import Optional, List


def _virsorter_hmm_assets_ready(virsorter_dir: str) -> bool:
    """VirSorter2 needs either the source combined.hmm or a full pressed database."""
    combined_hmm = os.path.join(virsorter_dir, "hmm", "viral", "combined.hmm")
    pressed_paths = [
        os.path.join(virsorter_dir, "hmm", "viral", f"combined.{suffix}")
        for suffix in ("h3f", "h3i", "h3m", "h3p")
    ]
    return os.path.isfile(combined_hmm) or all(os.path.isfile(path) for path in pressed_paths)


def validate_file_exists(path: str, description: str = "File") -> bool:
    """
    Validate that a file exists and is readable.
    
    Args:
        path: Path to the file to validate
        description: Human-readable description for error messages
        
    Returns:
        True if validation passes
        
    Raises:
        FileNotFoundError: If file does not exist
        PermissionError: If file is not readable
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"{description} not found: {path}")
    if not os.path.isfile(path):
        raise ValueError(f"{description} is not a file: {path}")
    if not os.access(path, os.R_OK):
        raise PermissionError(f"{description} is not readable: {path}")
    return True


def validate_fasta(path: str) -> bool:
    """
    Validate a FASTA file exists, is readable, and is non-empty.
    
    Args:
        path: Path to the FASTA file
        
    Returns:
        True if validation passes
        
    Raises:
        FileNotFoundError: If file does not exist
        ValueError: If file is empty or has invalid extension
    """
    valid_extensions = ('.fasta', '.fa', '.fna')
    
    validate_file_exists(path, "FASTA file")
    
    if not path.lower().endswith(valid_extensions):
        raise ValueError(
            f"FASTA file has invalid extension: {path}. "
            f"Expected one of: {valid_extensions}"
        )
    
    if os.path.getsize(path) == 0:
        raise ValueError(f"FASTA file is empty: {path}")
    
    return True


def validate_directory(
    path: str, 
    create: bool = False, 
    description: str = "Directory"
) -> bool:
    """
    Validate that a directory exists or optionally create it.
    
    Args:
        path: Path to the directory
        create: If True, create the directory if it doesn't exist
        description: Human-readable description for error messages
        
    Returns:
        True if validation passes
        
    Raises:
        FileNotFoundError: If directory doesn't exist and create=False
        PermissionError: If directory is not accessible
    """
    if not os.path.exists(path):
        if create:
            try:
                os.makedirs(path, exist_ok=True)
                return True
            except OSError as e:
                raise PermissionError(f"Cannot create {description}: {path}. Error: {e}")
        else:
            raise FileNotFoundError(f"{description} not found: {path}")
    
    if not os.path.isdir(path):
        raise ValueError(f"{description} path is not a directory: {path}")
    
    if not os.access(path, os.R_OK | os.X_OK):
        raise PermissionError(f"{description} is not accessible: {path}")
    
    return True


def validate_database_structure(db_path: str) -> bool:
    """
    Validate that the database directory has the expected structure.
    
    Args:
        db_path: Path to the database directory
        
    Returns:
        True if all required subdirectories exist
        
    Raises:
        FileNotFoundError: If database or subdirectories are missing
    """
    from .config import (
        DB_VIRSORTER, DB_VIRALVERIFY, DB_CHECKV, DB_GENOMAD
    )
    
    required_dirs = {
        'VirSorter2': DB_VIRSORTER,
        'ViralVerify': DB_VIRALVERIFY,
        'CheckV': DB_CHECKV,
        'geNomad': DB_GENOMAD,
    }
    
    validate_directory(db_path, description="Database directory")
    
    missing = []
    for name, subdir in required_dirs.items():
        full_path = os.path.join(db_path, subdir)
        if not os.path.isdir(full_path):
            missing.append(f"{name} ({subdir})")
    
    if missing:
        raise FileNotFoundError(
            f"Database directory {db_path} is missing required subdirectories: "
            f"{', '.join(missing)}"
        )

    virsorter_dir = os.path.join(db_path, DB_VIRSORTER)
    virsorter_missing = []

    if not _virsorter_hmm_assets_ready(virsorter_dir):
        virsorter_missing.append(
            "VirSorter2 viral HMM database "
            f"({DB_VIRSORTER}/hmm/viral/combined.hmm or combined.h3f/h3i/h3m/h3p)"
        )

    ncldv_rbs = os.path.join(virsorter_dir, "group", "NCLDV", "rbs-prodigal-train.db")
    if not os.path.isfile(ncldv_rbs):
        virsorter_missing.append(
            f"VirSorter2 NCLDV prodigal training DB ({DB_VIRSORTER}/group/NCLDV/rbs-prodigal-train.db)"
        )

    if virsorter_missing:
        raise FileNotFoundError(
            f"Database directory {db_path} is missing required VirSorter2 assets: "
            f"{', '.join(virsorter_missing)}"
        )
    
    return True


def validate_positive_integer(
    value: str, 
    name: str = "Value",
    min_val: int = 1,
    max_val: Optional[int] = None
) -> int:
    """
    Validate and convert a string to a positive integer.
    
    Args:
        value: String value to validate
        name: Parameter name for error messages
        min_val: Minimum allowed value (inclusive)
        max_val: Maximum allowed value (inclusive), None for no limit
        
    Returns:
        Validated integer value
        
    Raises:
        ValueError: If validation fails
    """
    try:
        int_val = int(value)
    except (ValueError, TypeError):
        raise ValueError(f"{name} must be an integer, got: {value}")
    
    if int_val < min_val:
        raise ValueError(f"{name} must be >= {min_val}, got: {int_val}")
    
    if max_val is not None and int_val > max_val:
        raise ValueError(f"{name} must be <= {max_val}, got: {int_val}")
    
    return int_val


def find_paired_reads(
    directory: str, 
    sample_name: str
) -> tuple:
    """
    Find paired-end read files for a given sample.
    
    Args:
        directory: Directory to search for read files
        sample_name: Sample name prefix (e.g., 'sample1')
        
    Returns:
        Tuple of (r1_path, r2_path)
        
    Raises:
        FileNotFoundError: If paired files are not found
    """
    import glob
    
    patterns = [
        (f"{sample_name}_R1.fq.gz", f"{sample_name}_R2.fq.gz"),
        (f"{sample_name}_R1.fastq.gz", f"{sample_name}_R2.fastq.gz"),
        (f"{sample_name}_R1.fq", f"{sample_name}_R2.fq"),
        (f"{sample_name}_R1.fastq", f"{sample_name}_R2.fastq"),
    ]
    
    for r1_pattern, r2_pattern in patterns:
        r1_files = glob.glob(os.path.join(directory, r1_pattern))
        r2_files = glob.glob(os.path.join(directory, r2_pattern))
        
        if r1_files and r2_files:
            return (r1_files[0], r2_files[0])
    
    # Try more flexible matching
    r1_matches = glob.glob(os.path.join(directory, f"{sample_name}_R1*"))
    r2_matches = glob.glob(os.path.join(directory, f"{sample_name}_R2*"))
    
    if r1_matches and r2_matches:
        return (r1_matches[0], r2_matches[0])
    
    raise FileNotFoundError(
        f"Paired-end reads not found for sample '{sample_name}' in {directory}"
    )
