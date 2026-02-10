#!/usr/bin/env python3
"""
STEP 5: Download Policy & Guardrails Engine
NGK's Download Manager V2.0 - Policy Layer Only
Universal Agent Ruleset: ASCII-only, no engine modification, policy gates only
"""

import json
import os
import time
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import urlparse
from dataclasses import dataclass, asdict


@dataclass
class PolicyDecision:
    """Policy decision result"""
    action: str  # ALLOW, DENY, MODIFY
    reason: str
    annotations: Dict[str, Any] = None
    code: str = ""  # structured denial code (e.g. DENY_HOST_DENYLIST)
    
    def __post_init__(self):
        if self.annotations is None:
            self.annotations = {}


class PolicyEngine:
    """
    Step 5 Policy Engine - Interceptive Layer Only
    
    CRITICAL: This engine NEVER modifies core behavior
    It only makes policy decisions and logs them
    """
    
    def __init__(self, policy_config_path: str = "config/policy.json"):
        self.policy_config_path = policy_config_path
        self.policies = {}
        self.version = None
        self.logger = logging.getLogger("policy")
        
        # Load policies at startup
        self.load_policies()
    
    def load_policies(self) -> bool:
        """Load policy configuration from disk"""
        try:
            if not os.path.exists(self.policy_config_path):
                # Create default policy if none exists
                self._create_default_policy()
                return True
            
            with open(self.policy_config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # Validate policy schema
            if not self._validate_policy_schema(config):
                raise ValueError("Invalid policy schema")
            
            self.policies = config.get('policies', {})
            self.version = config.get('version', '1.0')
            
            self.logger.info(f"POLICY | LOAD_OK | version={self.version} | path={self.policy_config_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"POLICY | LOAD_FAIL | error={str(e)}")
            # Fall back to permissive defaults
            self.policies = self._get_permissive_defaults()
            return False
    
    def _create_default_policy(self):
        """Create default policy configuration"""
        os.makedirs(os.path.dirname(self.policy_config_path), exist_ok=True)
        
        default_config = {
            "version": "1.0",
            "schema_version": 1,
            "last_updated": datetime.now().isoformat(),
            "policies": {
                "global": {
                    "safe_mode": False,
                    "offline_mode": False,
                    "metered_network_restrictions": False
                },
                "per_task": {
                    "max_speed_bps": None,  # None = unlimited
                    "max_retries": None,    # None = use engine default
                    "timeout_seconds": 300  # 5 minutes default
                },
                "per_host": {
                    "allowlist": [],        # Empty = allow all
                    "denylist": ["localhost", "127.0.0.1", "::1"],  # Block local by default
                    "max_connections_per_host": 2,
                    "rate_limit_requests_per_minute": None
                },
                "file_type": {
                    "allowed_extensions": [],  # Empty = allow all
                    "blocked_extensions": [".exe", ".bat", ".cmd", ".scr"],
                    "max_file_size_mb": None   # None = unlimited
                },
                "network": {
                    "tls_only": False,
                    "retries": 3,
                    "backoff_ms": 1000,
                    "honor_proxy_env": True
                }
            }
        }
        
        with open(self.policy_config_path, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=2)
        
        self.policies = default_config['policies']
        self.version = default_config['version']
        
        self.logger.info(f"POLICY | CREATE_DEFAULT | path={self.policy_config_path}")
    
    def _validate_policy_schema(self, config: Dict[str, Any]) -> bool:
        """Validate policy configuration schema"""
        required_keys = ['version', 'policies']
        for key in required_keys:
            if key not in config:
                return False
        
        required_policy_sections = ['global', 'per_task', 'per_host', 'file_type']
        policies = config['policies']
        for section in required_policy_sections:
            if section not in policies:
                return False
        
        return True
    
    def _get_permissive_defaults(self) -> Dict[str, Any]:
        """Get permissive policy defaults for fallback"""
        return {
            "global": {"safe_mode": False, "offline_mode": False},
            "per_task": {"max_speed_bps": None, "max_retries": None, "timeout_seconds": 600},
            "per_host": {"allowlist": [], "denylist": [], "max_connections_per_host": 4},
            "file_type": {"allowed_extensions": [], "blocked_extensions": [], "max_file_size_mb": None},
            "network": {"tls_only": False, "retries": 3, "backoff_ms": 1000, "honor_proxy_env": True}
        }
    
    def check_enqueue_policy(self, task_id: str, url: str, destination: str, **options) -> PolicyDecision:
        """
        Policy check at task enqueue time
        NEVER modifies engine behavior - only makes decisions
        """
        self.logger.info(f"POLICY | CHECK | scope=task | rule=enqueue | task_id={task_id}")
        
        # Extract host from URL (hostname only — strips port)
        try:
            parsed_url = urlparse(url)
            host = (parsed_url.hostname or "").lower() or "unknown"
        except Exception:
            host = "unknown"
        
        # Check global policies first
        global_policies = self.policies.get('global', {})
        if global_policies.get('safe_mode', False):
            return PolicyDecision('DENY', "safe_mode enabled", code="DENY_SAFE_MODE")
        
        # Check host allowlist/denylist
        host_policies = self.policies.get('per_host', {})
        allowlist = host_policies.get('allowlist', [])
        denylist = host_policies.get('denylist', [])
        
        if allowlist and host not in allowlist:
            decision = PolicyDecision('DENY', f"host {host} not in allowlist",
                                       code="DENY_HOST_ALLOWLIST")
            if self._consume_exception("host", host):
                self.logger.info(f"POLICY | EXCEPTION_USED | type=host | value={host} | task_id={task_id}")
                return PolicyDecision('ALLOW', f"host {host} allowed via one-time exception",
                                       code="ALLOW_EXCEPTION")
            return decision
        
        if denylist and host in denylist:
            decision = PolicyDecision('DENY', f"host {host} in denylist",
                                       code="DENY_HOST_DENYLIST")
            if self._consume_exception("host", host):
                self.logger.info(f"POLICY | EXCEPTION_USED | type=host | value={host} | task_id={task_id}")
                return PolicyDecision('ALLOW', f"host {host} allowed via one-time exception",
                                       code="ALLOW_EXCEPTION")
            return decision
        
        # Check file type policies
        file_policies = self.policies.get('file_type', {})
        if destination:
            file_ext = os.path.splitext(destination)[1].lower()
            blocked_exts = file_policies.get('blocked_extensions', [])
            if file_ext in blocked_exts:
                return PolicyDecision('DENY', f"file extension {file_ext} blocked",
                                       code="DENY_EXTENSION_BLOCKED")
            
            allowed_exts = file_policies.get('allowed_extensions', [])
            if allowed_exts and file_ext not in allowed_exts:
                return PolicyDecision('DENY', f"file extension {file_ext} not in allowed list",
                                       code="DENY_EXTENSION_NOT_ALLOWED")
        
        # Check per-task policies for annotations
        task_policies = self.policies.get('per_task', {})
        annotations = {}
        
        if task_policies.get('max_speed_bps'):
            annotations['max_speed_bps'] = task_policies['max_speed_bps']
        
        if task_policies.get('max_retries'):
            annotations['max_retries'] = task_policies['max_retries']
        
        if task_policies.get('timeout_seconds'):
            annotations['timeout_seconds'] = task_policies['timeout_seconds']
        
        if annotations:
            return PolicyDecision('MODIFY', "task policies applied", annotations)
        
        return PolicyDecision('ALLOW', "all policies passed")
    
    def check_network_policy(self, url: str, task_id: str = "") -> PolicyDecision:
        """F15: Check network-level policy knobs (tls_only, retries, backoff, proxy)."""
        self.logger.info(f"POLICY | CHECK | scope=network | task_id={task_id}")
        net = self.policies.get("network", {})

        # tls_only: reject non-https URLs
        tls_only = net.get("tls_only", False)
        if tls_only:
            try:
                scheme = urlparse(url).scheme.lower()
            except Exception:
                scheme = ""
            if scheme != "https":
                return PolicyDecision("DENY",
                                       f"tls_only: scheme {scheme!r} not allowed",
                                       code="DENY_SCHEME_NOT_TLS")

        # Expose retry / backoff / proxy as annotations
        annotations: Dict[str, Any] = {}
        retries = net.get("retries")
        if retries is not None:
            annotations["retries"] = int(retries)
        backoff = net.get("backoff_ms")
        if backoff is not None:
            annotations["backoff_ms"] = int(backoff)
        honor_proxy = net.get("honor_proxy_env", True)
        annotations["honor_proxy_env"] = honor_proxy

        if annotations:
            return PolicyDecision("MODIFY", "network policies applied", annotations)
        return PolicyDecision("ALLOW", "network policy passed")

    def check_start_policy(self, task_id: str, url: str) -> PolicyDecision:
        """Policy check at task start time"""
        self.logger.info(f"POLICY | CHECK | scope=task | rule=start | task_id={task_id}")
        
        # Check host connection limits
        host_policies = self.policies.get('per_host', {})
        max_connections = host_policies.get('max_connections_per_host', 2)
        
        # This is annotation only - we don't actually count active connections
        # That would require engine modification which is forbidden
        annotations = {'max_connections_per_host': max_connections}
        
        return PolicyDecision('MODIFY', "start policies applied", annotations)
    
    def check_retry_policy(self, task_id: str, attempt: int, max_attempts: int, error: str) -> PolicyDecision:
        """Policy check at retry attempt time"""
        self.logger.info(f"POLICY | CHECK | scope=task | rule=retry | task_id={task_id}")
        
        task_policies = self.policies.get('per_task', {})
        policy_max_retries = task_policies.get('max_retries')
        
        # If policy sets a stricter limit than engine, annotate it
        if policy_max_retries and attempt >= policy_max_retries:
            return PolicyDecision('DENY', f"policy retry limit {policy_max_retries} exceeded",
                                   code="DENY_RETRY_LIMIT")
        
        return PolicyDecision('ALLOW', "retry policy passed")
    
    def check_resume_policy(self, task_id: str, url: str, file_path: str, 
                           current_size: int = 0) -> PolicyDecision:
        """Policy check at resume time"""
        self.logger.info(f"POLICY | CHECK | scope=task | rule=resume | task_id={task_id} | size={current_size}")
        
        # Check if resume is globally enabled
        global_policies = self.policies.get('global', {})
        resume_enabled = global_policies.get('allow_resume', True)
        
        if not resume_enabled:
            return PolicyDecision('DENY', 'resume_disabled_globally')
        
        # Check host-specific resume policies
        host = self._extract_host(url) if url else "unknown"
        host_policies = self.policies.get('per_host', {})
        host_resume = host_policies.get('allow_resume', True)
        
        if not host_resume:
            return PolicyDecision('DENY', f'resume_disabled_for_host_{host}')
        
        # Check minimum resume size threshold
        min_resume_size = global_policies.get('min_resume_size_mb', 0) * 1024 * 1024  # Convert MB to bytes
        if current_size < min_resume_size:
            return PolicyDecision('DENY', f'file_too_small_for_resume ({current_size} < {min_resume_size})')
        
        return PolicyDecision('ALLOW', 'resume_policy_passed')
    
    # ---- F14: Allow-once exception store ----
    _EXCEPTION_PATH = os.path.join("data", "runtime", "policy_exceptions.json")

    def _load_exceptions(self) -> List[Dict[str, Any]]:
        """Load the allow-once exception list from disk."""
        try:
            if os.path.exists(self._EXCEPTION_PATH):
                with open(self._EXCEPTION_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception:
            pass
        return []

    def _save_exceptions(self, exceptions: List[Dict[str, Any]]) -> None:
        os.makedirs(os.path.dirname(self._EXCEPTION_PATH), exist_ok=True)
        with open(self._EXCEPTION_PATH, "w", encoding="utf-8") as f:
            json.dump(exceptions, f, indent=2)

    def add_exception(self, exc_type: str, value: str) -> None:
        """Add a one-time policy exception (e.g. type='host', value='evil.com').
        The exception is consumed on first matching check_enqueue_policy call."""
        exceptions = self._load_exceptions()
        exceptions.append({"type": exc_type, "value": value, "used": False})
        self._save_exceptions(exceptions)
        self.logger.info(f"POLICY | EXCEPTION_ADDED | type={exc_type} | value={value}")

    def _consume_exception(self, exc_type: str, value: str) -> bool:
        """Check for a matching unused exception; if found, mark it used and return True."""
        exceptions = self._load_exceptions()
        for exc in exceptions:
            if exc.get("type") == exc_type and exc.get("value") == value and not exc.get("used"):
                exc["used"] = True
                self._save_exceptions(exceptions)
                return True
        return False

    def _extract_host(self, url: str) -> str:
        """Extract hostname from URL (strips port)"""
        try:
            parsed_url = urlparse(url)
            return (parsed_url.hostname or "").lower() or "unknown"
        except Exception:
            return "unknown"
    
    def apply_policy_decision(self, decision: PolicyDecision, task_id: str) -> None:
        """
        Apply policy decision by logging it
        NEVER modifies engine behavior - logging only
        """
        code_tag = f" | code={decision.code}" if decision.code else ""
        if decision.action == 'ALLOW':
            self.logger.info(f"POLICY | ALLOW | task_id={task_id} | reason={decision.reason}{code_tag}")
        elif decision.action == 'DENY':
            self.logger.info(f"POLICY | DENY | task_id={task_id} | reason={decision.reason}{code_tag}")
        elif decision.action == 'MODIFY':
            annotations = ', '.join(f"{k}={v}" for k, v in decision.annotations.items())
            self.logger.info(f"POLICY | MODIFY | task_id={task_id} | annotation={annotations}{code_tag}")
    
    def reload_policies(self) -> bool:
        """Reload policies from disk (hot reload)"""
        self.logger.info("POLICY | RELOAD | triggered")
        
        old_version = self.version
        success = self.load_policies()
        
        if success:
            self.logger.info(f"POLICY | RELOAD | success | old_version={old_version} | new_version={self.version}")
        else:
            self.logger.error("POLICY | RELOAD | failed | using_fallback_defaults")
        
        return success
    
    def get_policy_summary(self) -> Dict[str, Any]:
        """Get current policy summary for UI display"""
        return {
            'version': self.version,
            'loaded_at': datetime.now().isoformat(),
            'policies': self.policies.copy()
        }


# Global policy engine instance
_policy_engine_instance = None

def get_policy_engine() -> PolicyEngine:
    """Get global policy engine instance (singleton)"""
    global _policy_engine_instance
    
    if _policy_engine_instance is None:
        _policy_engine_instance = PolicyEngine()
    
    return _policy_engine_instance