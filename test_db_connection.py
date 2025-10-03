"""
Quick database connection test
Run this to verify PostgreSQL connectivity before running Alembic
"""

import asyncio
import asyncpg
from dotenv import load_dotenv
import os

load_dotenv()

async def test_connection():
    """Test PostgreSQL connection with current .env settings"""
    
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "com_ai_v3")
    user = os.getenv("POSTGRES_USER", "comai")
    password = os.getenv("POSTGRES_PASSWORD", "change_me")
    
    print(f"Testing connection to:")
    print(f"  Host: {host}")
    print(f"  Port: {port}")
    print(f"  Database: {db}")
    print(f"  User: {user}")
    print(f"  Password: {'*' * len(password)}")
    print()
    
    try:
        conn = await asyncpg.connect(
            host=host,
            port=int(port),
            database=db,
            user=user,
            password=password,
            timeout=5
        )
        print("✅ Connection successful!")
        
        # Test query
        result = await conn.fetchval("SELECT current_user, current_database()")
        print(f"✅ Query successful: {result}")
        
        await conn.close()
        return True
        
    except asyncpg.InvalidCatalogNameError:
        print(f"❌ Database '{db}' does not exist")
        return False
    except asyncpg.InvalidPasswordError:
        print(f"❌ Invalid password for user '{user}'")
        return False
    except ConnectionRefusedError:
        print(f"❌ Connection refused - PostgreSQL not running on {host}:{port}")
        print("   Run: Get-Service postgresql* to check service status")
        return False
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_connection())
    exit(0 if success else 1)