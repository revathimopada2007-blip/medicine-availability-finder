from datetime import datetime
from database import get_db_connection

def save_search_query(user_id, search_query):
    if not user_id or not search_query or not search_query.strip():
        return
    conn = get_db_connection()
    try:
        # Prevent immediate duplicates
        latest = conn.execute("SELECT search_query FROM search_history WHERE user_id = ? ORDER BY searched_at DESC LIMIT 1", (user_id,)).fetchone()
        if not latest or latest['search_query'].strip().lower() != search_query.strip().lower():
            now_iso = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            conn.execute("INSERT INTO search_history (user_id, search_query, searched_at) VALUES (?, ?, ?)", (user_id, search_query.strip(), now_iso))
            conn.commit()
    except Exception:
        conn.rollback()
    finally:
        conn.close()

def get_user_search_history(user_id, limit=20):
    conn = get_db_connection()
    rows = conn.execute("SELECT id, search_query, searched_at FROM search_history WHERE user_id = ? ORDER BY searched_at DESC LIMIT ?", (user_id, limit)).fetchall()
    conn.close()
    
    results = []
    for r in rows:
        d = dict(r)
        try:
            dt = datetime.strptime(str(d['searched_at']).split('.')[0], '%Y-%m-%d %H:%M:%S')
            d['formatted_time'] = dt.strftime('%d %b %Y, %I:%M %p')
        except Exception:
            d['formatted_time'] = str(d['searched_at'])
        results.append(d)
    return results

def clear_user_search_history(user_id):
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM search_history WHERE user_id = ?", (user_id,))
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()
