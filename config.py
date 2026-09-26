import os
import tempfile

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

def get_database_path():
    if os.environ.get('DATABASE_PATH'):
        return os.environ.get('DATABASE_PATH')
    
    # On Vercel / serverless environment, the only writable directory is /tmp
    is_serverless = bool(os.environ.get('VERCEL') or os.environ.get('AWS_LAMBDA_FUNCTION_NAME') or os.environ.get('VERCEL_ENV'))
    if is_serverless:
        return os.path.join(tempfile.gettempdir(), 'medicine_finder.db')
    
    return os.path.join(BASE_DIR, 'instance', 'medicine_finder.db')

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'med-finder-secure-btech-key-2026-xyz')
    DATABASE_PATH = get_database_path()
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
