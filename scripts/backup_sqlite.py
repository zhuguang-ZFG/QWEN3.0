#!/usr/bin/env python3
"""
LiMa SQLite 数据库备份脚本
支持每日备份、保留最近7天的备份
"""

import os
import shutil
import gzip
import json
from datetime import datetime, timedelta
from pathlib import Path

# 配置
BACKUP_DIR = '/opt/lima-backups/sqlite'
SOURCE_DIR = '/opt/lima-router'
RETENTION_DAYS = 7  # 保留最近7天的备份

# 需要备份的 SQLite 数据库文件
SQLITE_FILES = [
    'session_memory.db',
    'context_memory.db',
    'code_graph.db',
    'lima.db',
    'codegraph.db',
    'semantic_cache.db',
    'health_state.db',
    'quality_history.db',
    'budget_state.db',
    'admission_state.db',
    'sticky_session.db',
    'rate_limit.db',
]

def create_backup_dir():
    """创建备份目录"""
    today = datetime.now().strftime('%Y-%m-%d')
    backup_path = os.path.join(BACKUP_DIR, today)
    os.makedirs(backup_path, exist_ok=True)
    return backup_path

def backup_database(source_file, backup_path):
    """备份单个数据库文件"""
    if not os.path.exists(source_file):
        print(f"  ⚠ 文件不存在: {source_file}")
        return False
    
    filename = os.path.basename(source_file)
    backup_file = os.path.join(backup_path, f"{filename}.gz")
    
    try:
        # 使用 gzip 压缩备份
        with open(source_file, 'rb') as f_in:
            with gzip.open(backup_file, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        # 获取文件大小
        source_size = os.path.getsize(source_file)
        backup_size = os.path.getsize(backup_file)
        compression_ratio = (1 - backup_size / source_size) * 100 if source_size > 0 else 0
        
        print(f"  ✓ {filename}: {source_size/1024:.1f}KB → {backup_size/1024:.1f}KB ({compression_ratio:.1f}% 压缩)")
        return True
    except Exception as e:
        print(f"  ✗ {filename}: 备份失败 - {e}")
        return False

def cleanup_old_backups():
    """清理旧的备份文件"""
    cutoff_date = datetime.now() - timedelta(days=RETENTION_DAYS)
    
    if not os.path.exists(BACKUP_DIR):
        return
    
    for item in os.listdir(BACKUP_DIR):
        item_path = os.path.join(BACKUP_DIR, item)
        if os.path.isdir(item_path):
            try:
                dir_date = datetime.strptime(item, '%Y-%m-%d')
                if dir_date < cutoff_date:
                    shutil.rmtree(item_path)
                    print(f"  ✓ 清理旧备份: {item}")
            except ValueError:
                # 无效的日期格式，跳过
                pass

def create_backup_manifest(backup_path, results):
    """创建备份清单文件"""
    manifest = {
        'timestamp': datetime.now().isoformat(),
        'backup_path': backup_path,
        'databases': results,
        'total_files': len(results),
        'successful': sum(1 for r in results.values() if r),
        'failed': sum(1 for r in results.values() if not r),
    }
    
    manifest_file = os.path.join(backup_path, 'manifest.json')
    with open(manifest_file, 'w') as f:
        json.dump(manifest, f, indent=2)
    
    return manifest

def main():
    """主备份流程"""
    print(f"\n{'='*60}")
    print(f"LiMa SQLite 数据库备份 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    
    # 创建备份目录
    backup_path = create_backup_dir()
    print(f"\n备份目录: {backup_path}")
    
    # 备份数据库
    print("\n备份数据库:")
    results = {}
    
    for db_file in SQLITE_FILES:
        source_path = os.path.join(SOURCE_DIR, db_file)
        success = backup_database(source_path, backup_path)
        results[db_file] = success
    
    # 创建备份清单
    manifest = create_backup_manifest(backup_path, results)
    
    # 清理旧备份
    print("\n清理旧备份:")
    cleanup_old_backups()
    
    # 统计结果
    print(f"\n{'='*60}")
    print(f"备份完成")
    print(f"{'='*60}")
    print(f"成功: {manifest['successful']}/{manifest['total_files']}")
    print(f"失败: {manifest['failed']}/{manifest['total_files']}")
    
    if manifest['failed'] > 0:
        print(f"\n失败的文件:")
        for db_file, success in results.items():
            if not success:
                print(f"  - {db_file}")
    
    return 0 if manifest['failed'] == 0 else 1

if __name__ == '__main__':
    exit(main())
