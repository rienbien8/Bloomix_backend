#!/usr/bin/env python3
"""
Azure MySQL接続テスト用スクリプト
"""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# 環境変数の読み込み
load_dotenv()

def test_mysql_connection():
    """Azure MySQLへの接続をテストする"""
    
    # 環境変数の取得
    DB_USER = os.getenv('DB_USER')
    DB_PASSWORD = os.getenv('DB_PASSWORD')
    DB_HOST = os.getenv('DB_HOST')
    DB_PORT = os.getenv('DB_PORT')
    DB_NAME = os.getenv('DB_NAME')
    SSL_CA_PATH = os.getenv('SSL_CA_PATH')
    
    print("=" * 50)
    print("🔍 Azure MySQL 接続テスト")
    print("=" * 50)
    print(f"DB_USER: {DB_USER}")
    print(f"DB_PASSWORD: {'*' * len(DB_PASSWORD) if DB_PASSWORD else 'None'}")
    print(f"DB_HOST: {DB_HOST}")
    print(f"DB_PORT: {DB_PORT}")
    print(f"DB_NAME: {DB_NAME}")
    print(f"SSL_CA_PATH: {SSL_CA_PATH}")
    print("-" * 50)
    
    # 必須項目のチェック
    if not all([DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME]):
        print("❌ 環境変数が不足しています")
        return False
    
    # DATABASE_URLの構築
    DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    print(f"接続URL: {DATABASE_URL[:50]}...")
    print("-" * 50)
    
    try:
        print("🔄 接続テスト中...")
        
        # SSL設定
        connect_args = {}
        if SSL_CA_PATH and SSL_CA_PATH.strip():
            connect_args["ssl_ca"] = SSL_CA_PATH
            print(f"SSL証明書を使用: {SSL_CA_PATH}")
        else:
            connect_args["ssl_disabled"] = False
            print("SSL証明書なしで接続")
        
        # エンジン作成
        engine = create_engine(
            DATABASE_URL,
            echo=False,  # SQLを出力しない
            pool_pre_ping=True,
            connect_args=connect_args
        )
        
        # 接続テスト
        with engine.connect() as connection:
            # 基本的な接続テスト
            result = connection.execute(text("SELECT 1 as test"))
            test_result = result.fetchone()
            print(f"✅ 基本接続テスト成功: {test_result}")
            
            # MySQLバージョンの取得
            version_result = connection.execute(text("SELECT VERSION()"))
            version = version_result.fetchone()
            print(f"📊 MySQL バージョン: {version[0]}")
            
            # 現在のデータベース名の確認
            db_result = connection.execute(text("SELECT DATABASE()"))
            current_db = db_result.fetchone()
            print(f"🗄️  現在のデータベース: {current_db[0]}")
            
            # 現在のユーザーの確認
            user_result = connection.execute(text("SELECT USER()"))
            current_user = user_result.fetchone()
            print(f"👤 現在のユーザー: {current_user[0]}")
            
            # テーブル一覧の取得
            tables_result = connection.execute(text("SHOW TABLES"))
            tables = tables_result.fetchall()
            print(f"📋 テーブル数: {len(tables)}")
            if tables:
                print("テーブル一覧:")
                for table in tables:
                    print(f"  - {table[0]}")
            
            print("=" * 50)
            print("✅ Azure MySQL接続テスト完了！")
            print("=" * 50)
            return True
            
    except Exception as e:
        print(f"❌ 接続エラー: {e}")
        print(f"📝 エラータイプ: {type(e).__name__}")
        print("=" * 50)
        print("❌ Azure MySQL接続テスト失敗")
        print("=" * 50)
        return False

if __name__ == "__main__":
    test_mysql_connection() 