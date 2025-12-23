from datetime import datetime, timedelta
from functools import wraps
from typing import Dict, Optional, Tuple
import threading
import json
from pathlib import Path

from flask import request, jsonify, current_app


class RateLimiter:
    
    def __init__(self, storage_path: Optional[Path] = None):
        self._lock = threading.Lock()
        self._requests: Dict[str, list] = {}
        self._storage_path = storage_path
        
        if self._storage_path and self._storage_path.exists():
            self._load_from_file()
    
    def _load_from_file(self) -> None:
        if not self._storage_path:
            return
        try:
            with open(self._storage_path, 'r') as f:
                data = json.load(f)
                self._requests = data.get('requests', {})
        except (json.JSONDecodeError, IOError):
            self._requests = {}
    
    def _save_to_file(self) -> None:
        if not self._storage_path:
            return
        try:
            with open(self._storage_path, 'w') as f:
                json.dump({'requests': self._requests}, f)
        except IOError:
            pass
    
    def _get_client_key(self) -> str:
        forwarded = request.headers.get('X-Forwarded-For')
        if forwarded:
            return forwarded.split(',')[0].strip()
        return request.remote_addr or 'unknown'
    
    def _cleanup_old_requests(self, key: str, window_seconds: int) -> None:
        if key not in self._requests:
            return
        
        cutoff = datetime.now() - timedelta(seconds=window_seconds)
        cutoff_str = cutoff.isoformat()
        
        self._requests[key] = [
            ts for ts in self._requests[key]
            if ts > cutoff_str
        ]
        
        if not self._requests[key]:
            del self._requests[key]
    
    def is_allowed(self, max_requests: int, window_seconds: int) -> Tuple[bool, int, int]:
        client_key = self._get_client_key()
        now = datetime.now()
        
        with self._lock:
            self._cleanup_old_requests(client_key, window_seconds)
            
            if client_key not in self._requests:
                self._requests[client_key] = []
            
            request_count = len(self._requests[client_key])
            remaining = max(0, max_requests - request_count)
            
            if request_count >= max_requests:
                oldest = self._requests[client_key][0]
                oldest_dt = datetime.fromisoformat(oldest)
                retry_after = window_seconds - int((now - oldest_dt).total_seconds())
                return False, remaining, max(1, retry_after)
            
            self._requests[client_key].append(now.isoformat())
            self._save_to_file()
            
            return True, remaining - 1, 0
    
    def reset(self, client_key: Optional[str] = None) -> None:
        with self._lock:
            if client_key:
                self._requests.pop(client_key, None)
            else:
                self._requests.clear()
            self._save_to_file()


_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        storage_path = Path('data/rate_limits.json')
        storage_path.parent.mkdir(parents=True, exist_ok=True)
        _rate_limiter = RateLimiter(storage_path)
    return _rate_limiter


def rate_limit(max_requests: int = 60, window_seconds: int = 60):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            limiter = get_rate_limiter()
            allowed, remaining, retry_after = limiter.is_allowed(max_requests, window_seconds)
            
            if not allowed:
                response = jsonify({
                    'success': False,
                    'message': f'Rate limit exceeded. Try again in {retry_after} seconds.',
                    'retry_after': retry_after
                })
                response.status_code = 429
                response.headers['X-RateLimit-Limit'] = str(max_requests)
                response.headers['X-RateLimit-Remaining'] = '0'
                response.headers['X-RateLimit-Reset'] = str(retry_after)
                response.headers['Retry-After'] = str(retry_after)
                return response
            
            response = f(*args, **kwargs)
            
            if hasattr(response, 'headers'):
                response.headers['X-RateLimit-Limit'] = str(max_requests)
                response.headers['X-RateLimit-Remaining'] = str(remaining)
            
            return response
        return wrapped
    return decorator


def rate_limit_strict(max_requests: int = 10, window_seconds: int = 60):
    return rate_limit(max_requests, window_seconds)


def rate_limit_relaxed(max_requests: int = 120, window_seconds: int = 60):
    return rate_limit(max_requests, window_seconds)
