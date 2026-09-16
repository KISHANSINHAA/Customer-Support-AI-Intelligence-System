import argparse
import sys
import uvicorn
from src.config import settings
from src.database import db

def main():
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="Run DOTMappers AI Support Intelligence System")
    parser.add_argument("--host", default=settings.HOST, help="Host to bind")
    parser.add_argument("--port", type=int, default=settings.PORT, help="Port to bind")
    parser.add_argument("--reload", action="store_true", default=settings.DEBUG, help="Enable auto-reload")
    args = parser.parse_args()

    # Pre-flight check & database initialization
    print("\n" + "=" * 70)
    print(f">> Starting {settings.APP_NAME} (v{settings.APP_VERSION})")
    print("=" * 70)
    
    db.init_database()
    stats = db.get_stats()
    print(f"[*] Database Ready: {stats['total_tickets']} tickets loaded from {settings.CSV_PATH}")
    print(f"[*] Web UI Dashboard : http://localhost:{args.port}")
    print(f"[*] API Documentation: http://localhost:{args.port}/docs")
    print(f"[*] Health Endpoint  : http://localhost:{args.port}/health")
    print("=" * 70 + "\n")

    uvicorn.run(
        "src.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload
    )

if __name__ == "__main__":
    main()
