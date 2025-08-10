from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

# 環境変数の読み込み
load_dotenv()

# データベース接続情報
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_HOST = os.getenv('DB_HOST')
DB_PORT = os.getenv('DB_PORT')
DB_NAME = os.getenv('DB_NAME')
SSL_CA_PATH = os.getenv('SSL_CA_PATH')

# MySQLのURL構築
DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# SSL設定
connect_args = {}
if SSL_CA_PATH and SSL_CA_PATH.strip():
    connect_args["ssl_ca"] = SSL_CA_PATH
else:
    # Azure MySQLの場合、SSL必須だがssl_caが空の場合の設定
    connect_args["ssl_disabled"] = False

# エンジンの作成
engine = create_engine(
    DATABASE_URL,
    echo=True,
    pool_pre_ping=True,
    pool_recycle=3600,
    connect_args=connect_args
)

# セッションメーカーの作成
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

print("----- ✅ 環境変数の読み込み確認 -----")
print("DB_USER:", DB_USER)
print("DB_PASSWORD:", "(非表示)" if DB_PASSWORD else "None")
print("DB_HOST:", DB_HOST)
print("DB_PORT:", DB_PORT)
print("DB_NAME:", DB_NAME)
print("SSL_CA_PATH:", SSL_CA_PATH)
print("DATABASE_URL:", DATABASE_URL[:50] + "..." if len(DATABASE_URL) > 50 else DATABASE_URL)
print("----------------------------------")

def test_connection():
    """データベース接続テスト関数"""
    try:
        print("🔄 データベース接続テスト中...")
        
        # 接続テスト
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1 as test"))
            test_result = result.fetchone()
            print(f"✅ データベース接続テスト成功: {test_result}")
            
            # データベース情報の取得
            db_version = connection.execute(text("SELECT VERSION()")).fetchone()
            print(f"📊 MySQL バージョン: {db_version[0]}")
            
            # 現在のデータベース名の確認
            current_db = connection.execute(text("SELECT DATABASE()")).fetchone()
            print(f"🗄️  現在のデータベース: {current_db[0]}")
            
            return True
            
    except Exception as e:
        print(f"❌ データベース接続テストエラー: {e}")
        print(f"📝 エラーの詳細: {type(e).__name__}")
        return False

def init_db():
    """データベース初期化関数"""
    try:
        print("🔄 データベース初期化中...")
        
        # まず接続テストを実行
        if not test_connection():
            print("⚠️  データベース接続に失敗したため、初期化をスキップします")
            return
        
        # インスペクターを作成
        inspector = inspect(engine)
        
        # 既存のテーブルを取得
        existing_tables = inspector.get_table_names()
        print(f"📋 既存のテーブル: {existing_tables}")
        
        print("✅ データベース初期化完了")
        
    except Exception as e:
        print(f"⚠️  データベース初期化エラー（アプリケーションは継続起動）: {e}")
        print("💡 データベースサーバーが起動していない可能性があります")

def get_session():
    """データベースセッション取得"""
    try:
        session = SessionLocal()
        yield session
    finally:
        session.close()
