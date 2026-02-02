#!/usr/bin/env python3
"""
V2.1 Acceptance Tests - Basic functionality validation
Universal Agent Ruleset: ASCII-only, no placeholders, no behavior changes
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from integrated_multi_downloader import TokenBucketRateLimiter, IntegratedMultiDownloader
import json


def test_token_bucket_exists():
    """V2.1.1: TokenBucketRateLimiter class exists and instantiates"""
    limiter = TokenBucketRateLimiter(1.0)
    assert limiter is not None


def test_config_loading():
    """V2.1.2: Configuration loads without errors"""
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config.json')
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    # Validate expected config keys exist
    assert 'enable_bandwidth_limiting' in config
    assert 'global_bandwidth_limit_mbps' in config
    assert config['enable_bandwidth_limiting'] == False  # Default OFF


def test_downloader_instantiation():
    """V2.1.3: IntegratedMultiDownloader instantiates without errors"""
    downloader = IntegratedMultiDownloader()
    assert downloader is not None


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])